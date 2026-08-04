from decimal import Decimal
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from ai_features import services
from ai_features.llm_provider import LlmProviderError, MeetingSummaryProvider, ProviderNotConfiguredError
from ai_features.models import SuspiciousTransactionFlag
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class PredictionAndInactiveMembersTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona)

    def test_prediction_with_no_history_says_so_honestly(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        result = services.predict_expected_collections(funeral)
        self.assertFalse(result["has_historical_data"])
        self.assertIsNone(result["predicted_collection_rate"])

    def test_prediction_uses_historical_collection_rate(self):
        # First funeral: half of what's expected gets collected, then closed.
        past_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Past Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-01-01", collection_start_date="2026-01-01",
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=past_funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("25"), method="cash")  # half of 50
        funeral_services.close_funeral_event(funeral=past_funeral, actor=self.admin)

        new_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="New Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        result = services.predict_expected_collections(new_funeral)
        self.assertTrue(result["has_historical_data"])
        self.assertAlmostEqual(result["predicted_collection_rate"], 0.5, places=2)

    def test_inactive_member_identified_with_no_recent_activity(self):
        inactive = services.find_inactive_members(community=self.bodi, inactive_days=180)
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0]["full_name"], "Kojo Mensah")

    def test_member_with_recent_payment_is_not_inactive(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        inactive = services.find_inactive_members(community=self.bodi, inactive_days=180)
        self.assertEqual(len(inactive), 0)


class FuzzySearchTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        member_services.register_member(community=self.bodi, full_name="Kwabena Owusu", gender="male", family=self.asona)
        member_services.register_member(community=self.bodi, full_name="Ama Serwaa", gender="female", family=self.asona)

    def test_exact_substring_match_ranks_first(self):
        results = services.fuzzy_search(community=self.bodi, query="Owusu")
        self.assertEqual(results[0]["full_name"], "Kwabena Owusu")

    def test_slightly_misspelled_name_still_matches(self):
        results = services.fuzzy_search(community=self.bodi, query="Kwabina Owusu")
        names = [r["full_name"] for r in results]
        self.assertIn("Kwabena Owusu", names)

    def test_empty_query_returns_nothing(self):
        self.assertEqual(services.fuzzy_search(community=self.bodi, query=""), [])


class SuspiciousTransactionTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.collector = User.objects.create_user(username="collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("500"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

    def test_no_flag_without_enough_history(self):
        member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("500"), method="cash", collector=self.collector)
        self.assertEqual(SuspiciousTransactionFlag.objects.count(), 0)

    def test_outlier_amount_flagged_once_a_baseline_exists(self):
        # Build up 5 similarly-sized (but not perfectly identical) payments
        # from this collector to establish a real "normal" with nonzero
        # variance — an all-identical history has zero standard deviation,
        # which correctly never flags anything (see services.py's guard),
        # so the baseline here needs a little natural spread to be realistic.
        for i, amount in enumerate([Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"), Decimal("12")]):
            member = member_services.register_member(community=self.bodi, full_name=f"Member {i}", gender="male", family=self.asona)
            funeral = funeral_services.create_funeral_event(
                community=self.bodi, deceased_name=f"Deceased {i}", deceased_gender="male",
                deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
                own_family_amount=amount,
            )
            from funerals.models import ContributionObligation
            obligation = ContributionObligation.objects.get(funeral_event=funeral, member=member)
            funeral_services.record_payment(obligation=obligation, amount=amount, method="cash", collector=self.collector)

        # Now a wildly different amount from the same collector.
        outlier_member = member_services.register_member(community=self.bodi, full_name="Outlier Member", gender="male", family=self.asona)
        outlier_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Outlier Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        from funerals.models import ContributionObligation
        outlier_obligation = ContributionObligation.objects.get(funeral_event=outlier_funeral, member=outlier_member)
        funeral_services.record_payment(obligation=outlier_obligation, amount=Decimal("500"), method="cash", collector=self.collector)

        self.assertTrue(
            SuspiciousTransactionFlag.objects.filter(reason=SuspiciousTransactionFlag.Reason.AMOUNT_OUTLIER).exists()
        )


class MeetingSummaryTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")

    def test_raises_when_not_configured(self):
        with self.assertRaises(ProviderNotConfiguredError):
            MeetingSummaryProvider().summarize("We discussed the funeral budget.")

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_summarize_meeting_stores_the_real_provider_response(self):
        import json
        mock_post = MagicMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"content": [{"text": json.dumps({
                "summary": "The committee approved the new catering budget.",
                "decisions": ["Approved GH₵2000 catering budget"],
                "action_items": ["Treasurer to disburse funds by Friday"],
            })}]},
        ))
        provider = MeetingSummaryProvider(http_post=mock_post)
        result = provider.summarize("We discussed the funeral budget.")
        self.assertIn("catering budget", result["summary"])
        self.assertEqual(len(result["decisions"]), 1)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_summarize_meeting_service_persists_a_meeting_summary_row(self):
        import json
        import unittest.mock as mock
        from ai_features.models import MeetingSummary

        mock_post = MagicMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"content": [{"text": json.dumps({
                "summary": "Short summary.", "decisions": [], "action_items": [],
            })}]},
        ))

        # summarize_meeting() does a local `from .llm_provider import
        # MeetingSummaryProvider` at call time, so patching the class on
        # the llm_provider module itself (not on ai_features.services,
        # which never imports it at module level) is what actually takes
        # effect here.
        with mock.patch("ai_features.llm_provider.MeetingSummaryProvider") as MockProvider:
            MockProvider.return_value.summarize.return_value = {"summary": "Short summary.", "decisions": [], "action_items": []}
            summary = services.summarize_meeting(community=self.bodi, transcript="We discussed the budget.")

        self.assertEqual(MeetingSummary.objects.count(), 1)
        self.assertEqual(summary.summary, "Short summary.")


class TributeDraftTests(TestCase):
    """'Add AI features to make it greater' — a genuine starting point for a grieving family's public tribute, never invented, never auto-published."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-tribute")

    def test_raises_when_not_configured(self):
        from ai_features.llm_provider import TributeDraftProvider
        with self.assertRaises(ProviderNotConfiguredError):
            TributeDraftProvider().draft(deceased_name="Yaw Asona", key_details="A devoted farmer and church elder.")

    def test_empty_key_details_is_rejected_even_when_configured(self):
        from ai_features.llm_provider import TributeDraftProvider
        with override_settings(ANTHROPIC_API_KEY="test-key"):
            with self.assertRaises(LlmProviderError):
                TributeDraftProvider().draft(deceased_name="Yaw Asona", key_details="   ")

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_draft_returns_the_real_provider_response(self):
        from ai_features.llm_provider import TributeDraftProvider
        mock_post = MagicMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"content": [{"text": "Yaw Asona was a devoted farmer and beloved church elder, remembered for his warmth and generosity."}]},
        ))
        provider = TributeDraftProvider(http_post=mock_post)
        result = provider.draft(deceased_name="Yaw Asona", key_details="A devoted farmer and church elder, known for his warmth.")
        self.assertIn("devoted farmer", result)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_draft_tribute_message_service_never_persists_anything(self):
        """This function only drafts — it must never write to MemorialPage itself, matching 'never automatically saved.'"""
        import unittest.mock as mock
        from families import services as family_services
        from funerals import services as funeral_services
        from funerals.models import MemorialPage

        admin = User.objects.create_user(username="tribute_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        asona = family_services.create_family(community=self.bodi, name="Asona", actor=admin)
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=admin, own_family_amount=Decimal("50"),
        )

        with mock.patch("ai_features.llm_provider.TributeDraftProvider") as MockProvider:
            MockProvider.return_value.draft.return_value = "A warm, dignified draft tribute."
            draft = services.draft_tribute_message(funeral=funeral, key_details="A kind and generous man.")

        self.assertEqual(draft, "A warm, dignified draft tribute.")
        self.assertFalse(MemorialPage.objects.filter(funeral_event=funeral).exists())

    def test_draft_tribute_http_endpoint_requires_authorization(self):
        from families import services as family_services
        from funerals import services as funeral_services

        admin = User.objects.create_user(username="tribute_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        outsider = User.objects.create_user(username="tribute_http_outsider", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        asona = family_services.create_family(community=self.bodi, name="Asona", actor=admin)
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=admin, own_family_amount=Decimal("50"),
        )

        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "tribute_http_outsider", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(f"/api/ai/funerals/{funeral.id}/draft-tribute/", {"key_details": "A kind man."})
        self.assertEqual(res.status_code, 403)

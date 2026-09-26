from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from contribution_rules import services
from families import services as family_services
from members.models import Member
from members import services as member_services
from tenants.models import Community


class ContributionRulesTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

    def test_update_general_rates_logs_history(self):
        services.update_general_rates(community=self.bodi, male_amount=Decimal("10"), female_amount=Decimal("6"), actor=self.admin)
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.default_general_male_amount, Decimal("10"))

        from contribution_rules.models import GeneralRateChangeLog
        log = GeneralRateChangeLog.objects.get(community=self.bodi)
        self.assertEqual(log.old_male_amount, Decimal("5"))
        self.assertEqual(log.new_male_amount, Decimal("10"))

    def test_general_rates_must_be_positive(self):
        with self.assertRaises(ValidationError):
            services.update_general_rates(community=self.bodi, male_amount=Decimal("0"), female_amount=Decimal("3"))

    def test_default_exempt_statuses_without_any_override(self):
        self.assertFalse(services.is_status_exempt(self.bodi, "active"))
        self.assertTrue(services.is_status_exempt(self.bodi, "inactive"))
        self.assertTrue(services.is_status_exempt(self.bodi, "deceased"))

    def test_inactive_member_excluded_from_eligible_members_by_default(self):
        active_member = member_services.register_member(community=self.bodi, full_name="Active One", gender="male", family=self.asona)
        inactive_member = member_services.register_member(community=self.bodi, full_name="Inactive One", gender="male", family=self.asona)
        inactive_member.status = Member.Status.INACTIVE
        inactive_member.save()

        eligible_ids = set(services.eligible_members_queryset(self.bodi).values_list("id", flat=True))
        self.assertIn(active_member.id, eligible_ids)
        self.assertNotIn(inactive_member.id, eligible_ids)

    def test_community_can_reconfigure_inactive_members_to_be_liable(self):
        services.set_status_exemption(community=self.bodi, status="inactive", is_exempt=False, actor=self.admin)
        inactive_member = member_services.register_member(community=self.bodi, full_name="Inactive One", gender="male", family=self.asona)
        inactive_member.status = Member.Status.INACTIVE
        inactive_member.save()

        eligible_ids = set(services.eligible_members_queryset(self.bodi).values_list("id", flat=True))
        self.assertIn(inactive_member.id, eligible_ids)

    def test_defaulter_threshold_ordering_enforced(self):
        with self.assertRaises(ValidationError):
            services.update_defaulter_thresholds(community=self.bodi, warning=3, high_warning=2, flag=1)

    def test_preview_obligations_matches_what_a_real_funeral_would_generate(self):
        member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        member_services.register_member(community=self.bodi, full_name="Outside Member", gender="female", family=bretuo)

        preview = services.preview_obligations(community=self.bodi, deceased_family=self.asona)
        self.assertEqual(Decimal(preview["own_family_amount"]), Decimal("50"))
        self.assertEqual(preview["own_family_member_count"], 1)
        self.assertEqual(preview["general_female_member_count"], 1)
        self.assertFalse(preview["requires_one_off_amount"])

    def test_preview_flags_when_family_has_no_approved_rate(self):
        no_rate_family = family_services.create_family(community=self.bodi, name="Aduana", actor=self.admin)
        preview = services.preview_obligations(community=self.bodi, deceased_family=no_rate_family)
        self.assertTrue(preview["requires_one_off_amount"])

    def test_list_rules_aggregates_everything_in_one_response(self):
        rules = services.list_rules(self.bodi)
        self.assertEqual(Decimal(rules["general_rates"]["male_amount"]), Decimal("5"))
        family_names = {f["family_name"] for f in rules["family_rates"]}
        self.assertIn("Asona", family_names)
        self.assertEqual(rules["defaulter_thresholds"], {"warning": 1, "high_warning": 2, "flag": 3})


class SecretaryCanManageGeneralRatesTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.ordinary_member = User.objects.create_user(username="member1", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_secretary_can_increase_general_rates(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "secretary", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post("/api/contribution-rules/general-rates/", {"male_amount": "10", "female_amount": "6"})
        self.assertEqual(res.status_code, 200)
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.default_general_male_amount, Decimal("10"))

    def test_ordinary_community_member_cannot_change_rates(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "member1", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post("/api/contribution-rules/general-rates/", {"male_amount": "10", "female_amount": "6"})
        self.assertEqual(res.status_code, 403)

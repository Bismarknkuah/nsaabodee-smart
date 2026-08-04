from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.collector = User.objects.create_user(username="collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.guest = User.objects.create_user(username="guest", password="x", community=self.bodi, role=Role.GUEST)
        self.community_member_user = User.objects.create_user(
            username="member_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER
        )

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        member_services.link_member_to_user(member=self.member, user=self.community_member_user, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_community_admin_sees_community_overview(self):
        result = build_dashboard(self.admin)
        self.assertIn("community_overview", result["sections"])
        overview = result["sections"]["community_overview"]
        self.assertEqual(overview["active_funerals"], 1)
        self.assertIn("today_collections", overview)
        self.assertIn("outstanding_members", overview)

    def test_treasurer_sees_financial_overview_not_community_overview(self):
        result = build_dashboard(self.treasurer)
        self.assertIn("financial_overview", result["sections"])
        self.assertNotIn("community_overview", result["sections"])
        self.assertIn("month_to_date", result["sections"]["financial_overview"])

    def test_collector_sees_their_own_performance(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector=self.collector)

        result = build_dashboard(self.collector)
        performance = result["sections"]["collector_performance"]["today_performance"]
        self.assertEqual(Decimal(performance["contributions"]["total"]), Decimal("50"))

    def test_community_member_sees_their_own_receipts_and_defaulter_status(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        result = build_dashboard(self.community_member_user)
        overview = result["sections"]["member_overview"]
        self.assertEqual(overview["membership_number"], self.member.membership_number)
        self.assertEqual(len(overview["recent_receipts"]), 1)

    def test_guest_sees_only_public_active_funerals(self):
        result = build_dashboard(self.guest)
        self.assertIn("public_overview", result["sections"])
        self.assertEqual(len(result["sections"]["public_overview"]["active_funerals"]), 1)
        # Guests never get financial breakdowns.
        self.assertNotIn("today_collections", result["sections"]["public_overview"])

    def test_dashboard_endpoint_is_reachable_and_role_scoped(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "treasurer", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/dashboard/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["role"], Role.TREASURER)
        self.assertIn("financial_overview", res.data["sections"])

    def test_community_overview_includes_a_real_seven_day_trend(self):
        """A real chart on the dashboard needs real data behind it — not a single day's snapshot pretending to be a trend."""
        result = build_dashboard(self.admin)
        trend = result["sections"]["community_overview"]["collections_trend"]
        self.assertEqual(len(trend), 7)
        # In chronological order, ending today — not shuffled, not reversed.
        from datetime import date
        self.assertEqual(trend[-1]["date"], date.today().isoformat())
        for day in trend:
            self.assertIn("total", day)

    def test_financial_officer_trend_never_includes_gift_cash(self):
        """Same 'the committee sees contributions, never donations' rule already enforced elsewhere — the trend chart is not an exception to it."""
        funeral_services.record_payment(
            obligation=self._obligation_for(self.funeral, self.member), amount=Decimal("50"), method="cash",
        )
        from gifts import services as gift_services
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("500"))
        result = build_dashboard(self.treasurer)
        trend = result["sections"]["financial_overview"]["collections_trend"]
        today_total = Decimal([d["total"] for d in trend if d["date"] == self._today_str()][0])
        self.assertEqual(today_total, Decimal("50"))  # the 500 gift must never appear here

    def _obligation_for(self, funeral, member):
        from funerals.models import ContributionObligation
        return ContributionObligation.objects.get(funeral_event=funeral, member=member)

    def _today_str(self):
        from datetime import date
        return date.today().isoformat()

    def test_platform_overview_includes_real_platform_wide_totals_not_just_a_community_count(self):
        """The dashboard used to show only a bare community count — now it surfaces real, already-computed data from features built elsewhere in this platform."""
        from accounts.models import Role, User
        from tenants import services as tenant_services
        from tenants.models import Community

        platform_admin = User.objects.create_user(username="dashboard_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        # A temporary community, to prove the permanent/temporary split is real.
        tenant_services.set_community_access_expiration(community=Community.objects.create(name="Temp Co", slug="temp-co-dash"), days_from_now=5)

        result = build_dashboard(platform_admin)
        overview = result["sections"]["platform_overview"]
        self.assertIn("permanent_community_count", overview)
        self.assertIn("temporary_community_count", overview)
        self.assertEqual(overview["temporary_community_count"], 1)
        self.assertIn("total_members_platform_wide", overview)
        self.assertIn("pending_announcements_count", overview)
        self.assertIn("uncontacted_plan_interest_count", overview)

    def test_financial_officer_view_includes_real_pending_approval_counts(self):
        """'Pending approvals' — real counts from the two approval workflows this platform already has, not a placeholder."""
        from funerals import services as funeral_services
        result = build_dashboard(self.treasurer)
        overview = result["sections"]["financial_overview"]
        self.assertIn("pending_funeral_openings_count", overview)
        self.assertIn("pending_payment_reversals_count", overview)

        payment = funeral_services.record_payment(obligation=self._obligation_for(self.funeral, self.member), amount=Decimal("20"), method="cash")
        funeral_services.request_payment_reversal(payment=payment, reason="Wrong amount", actor=self.treasurer)
        result = build_dashboard(self.treasurer)
        self.assertEqual(result["sections"]["financial_overview"]["pending_payment_reversals_count"], 1)

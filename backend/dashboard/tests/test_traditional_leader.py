from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from members.models import Member
from tenants import services as tenant_services
from tenants.models import Community


class TraditionalLeaderDashboardTests(TestCase):
    """
    'The Traditional Leader is the highest authority within that
    community... should have a dedicated Executive Dashboard that
    provides a strategic overview... must NOT collect payments, edit
    financial records, modify transactions, manage individual members
    directly, approve or reject personal donations, or access sensitive
    personal financial information unless explicitly authorized.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-chief",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="chief_test_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="the_chief", password="a-real-password-123", community=self.bodi, role=Role.TRADITIONAL_LEADER)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = Member.objects.create(community=self.bodi, family=self.asona, full_name="A Member", gender="male")
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_the_chief_gets_a_real_strategic_overview_of_the_community(self):
        result = build_dashboard(self.chief)
        overview = result["sections"]["traditional_leader_overview"]
        self.assertIn("family_count", overview)
        self.assertIn("active_member_count", overview)
        self.assertIn("active_funerals", overview)
        self.assertIn("outstanding_summary", overview)
        self.assertIn("collections_trend", overview)
        self.assertIn("recent_announcements", overview)
        self.assertIn("welfare_fund_summary", overview)
        self.assertIn("executive_performance_summary", overview)
        self.assertIn("audit_summary", overview)
        self.assertIn("upcoming_meetings", overview)

    def test_outstanding_contributions_are_aggregate_only_never_naming_a_member(self):
        """'Must not access sensitive personal financial information unless explicitly authorized' — a real, named individual member's debt must never appear on this dashboard."""
        result = build_dashboard(self.chief)
        overview = result["sections"]["traditional_leader_overview"]
        self.assertNotIn("outstanding_members", overview)
        self.assertIn("member_count", overview["outstanding_summary"])
        self.assertIn("total_owed", overview["outstanding_summary"])
        # The raw dict must never contain the member's own name anywhere.
        self.assertNotIn("A Member", str(overview["outstanding_summary"]))

    def test_the_chiefs_overview_never_includes_gift_donation_detail(self):
        """'Must not access sensitive personal financial information' — same restraint the finance committee already has."""
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("500"))
        result = build_dashboard(self.chief)
        overview = result["sections"]["traditional_leader_overview"]
        self.assertNotIn("gift_cash", overview["today_collections"])

    def test_approved_announcements_show_on_the_chiefs_dashboard(self):
        announcement = tenant_services.submit_announcement(community=self.bodi, title="Meeting", content="Sunday", actor=self.admin)
        platform_admin = User.objects.create_user(username="chief_test_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        tenant_services.approve_announcement(announcement=announcement, actor=platform_admin)

        result = build_dashboard(self.chief)
        titles = [a["title"] for a in result["sections"]["traditional_leader_overview"]["recent_announcements"]]
        self.assertIn("Meeting", titles)

    def test_a_pending_unapproved_announcement_never_shows_on_the_chiefs_dashboard(self):
        tenant_services.submit_announcement(community=self.bodi, title="Still Pending", content="x", actor=self.admin)
        result = build_dashboard(self.chief)
        titles = [a["title"] for a in result["sections"]["traditional_leader_overview"]["recent_announcements"]]
        self.assertNotIn("Still Pending", titles)


class TraditionalLeaderBoundaryTests(TestCase):
    """The Chief is oversight-only — every operational action must be genuinely blocked, not just visually hidden."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-chief-boundary",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="chief_boundary_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="chief_boundary_chief", password="a-real-password-123", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = Member.objects.create(community=self.bodi, family=self.asona, full_name="A Member", gender="male")
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "chief_boundary_chief", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_the_chief_cannot_register_a_member(self):
        client = self._login()
        res = client.post("/api/members/", {"full_name": "Should Fail", "gender": "male"})
        self.assertEqual(res.status_code, 403)

    def test_the_chief_cannot_record_a_gift(self):
        client = self._login()
        res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20"})
        self.assertIn(res.status_code, (403, 404))

    def test_the_chief_cannot_create_a_family(self):
        client = self._login()
        res = client.post("/api/families/", {"name": "Should Not Be Created"})
        self.assertEqual(res.status_code, 403)

    def test_the_chief_can_view_reports(self):
        """Oversight, not operations — viewing is explicitly allowed."""
        client = self._login()
        res = client.get(f"/api/reports/funerals/{self.funeral.id}/daily-breakdown/")
        self.assertEqual(res.status_code, 200)

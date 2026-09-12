from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from family_funds import services as fund_services
from members import services as member_services
from tenants.models import Community


class FamilyFundDashboardTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Treasurer Member", gender="female", family=self.asona)
        self.treasurer_user = User.objects.create_user(username="asona_treasurer", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer_user, actor=self.admin)
        family_services.assign_family_officer(family=self.asona, member=self.treasurer_member, officer_role="treasurer", actor=self.head_user)

        self.fund = fund_services.create_family_fund(family=self.asona, name="Building Fund", actor=self.head_user)
        fund_services.record_fund_contribution(fund=self.fund, member=self.treasurer_member, amount=Decimal("100"))

    def test_family_head_dashboard_includes_family_fund_overview(self):
        result = build_dashboard(self.head_user)
        self.assertIn("family_fund_overview", result["sections"])
        overview = result["sections"]["family_fund_overview"][0]
        self.assertEqual(overview["family_name"], "Asona")
        self.assertEqual(overview["your_role"], "head")
        self.assertEqual(Decimal(overview["funds"][0]["total_collected"]), Decimal("100"))

    def test_assigned_treasurer_sees_family_fund_overview_alongside_their_normal_member_view(self):
        """An ordinary Community Member who's also a family treasurer gets BOTH sections."""
        result = build_dashboard(self.treasurer_user)
        self.assertIn("member_overview", result["sections"])
        self.assertIn("family_fund_overview", result["sections"])
        self.assertEqual(result["sections"]["family_fund_overview"][0]["your_role"], "treasurer")

    def test_unrelated_member_sees_no_family_fund_section(self):
        rando_member = member_services.register_member(community=self.bodi, full_name="Rando", gender="male", family=self.asona)
        rando_user = User.objects.create_user(username="rando", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=rando_member, user=rando_user, actor=self.admin)

        result = build_dashboard(rando_user)
        self.assertNotIn("family_fund_overview", result["sections"])

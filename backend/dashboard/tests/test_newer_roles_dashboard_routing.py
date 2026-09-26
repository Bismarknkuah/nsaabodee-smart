from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class NewerRolesDashboardRoutingTests(TestCase):
    """
    'All executive personal dashboard is the same as the community
    member dashboard since they are members.' Confirms the newer
    roles built in recent turns (Arrears Collector, Family Arrears
    Officer, Family Registration Officer, the two Town Elders officer
    roles) each land on the correct existing dashboard section rather
    than silently falling through to build_dashboard's own default.
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="nrdr-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="nrdr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

    def test_arrears_collector_gets_its_own_arrears_section_not_the_contribution_collectors(self):
        """'Differentiate the arrears officers and the contribution collectors' — two different jobs, two different dashboards."""
        user = User.objects.create_user(username="nrdr_arrears_collector", password="x", community=self.bodi, role=Role.ARREARS_COLLECTOR)
        result = build_dashboard(user)
        self.assertEqual(list(result["sections"]), ["arrears_collector_overview"])
        section = result["sections"]["arrears_collector_overview"]
        for key in ("members_owing_count", "total_arrears_outstanding", "worklist", "today_performance", "week_performance"):
            self.assertIn(key, section)

    def test_the_contribution_collector_still_gets_whole_office_today_and_customers_owing(self):
        user = User.objects.create_user(username="nrdr_collector_2", password="x", community=self.bodi, role=Role.COLLECTOR)
        section = build_dashboard(user)["sections"]["collector_performance"]
        self.assertIn("whole_office_today", section)
        self.assertIn("customers_owing_count", section)

    def test_family_arrears_officer_gets_its_own_family_scoped_section(self):
        """
        'We have a family arrears collector who is responsible for
        managing and collecting his family arrears only.' Corrected
        from an earlier turn's routing decision — this role's job is
        collecting, not reviewing/approving, so it gets its own
        dedicated, family-scoped performance section rather than the
        Family Head's oversight dashboard (family_overview).
        """
        user = User.objects.create_user(username="nrdr_family_arrears_officer", password="x", community=self.bodi, role=Role.FAMILY_ARREARS_OFFICER)
        member = member_services.register_member(community=self.bodi, full_name="Officer", gender="male", family=self.asona)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)
        result = build_dashboard(user)
        self.assertIn("family_arrears_officer_performance", result["sections"])
        section = result["sections"]["family_arrears_officer_performance"]
        self.assertEqual(section["family_id"], str(self.asona.id))

    def test_family_registration_officer_gets_the_registration_overview_scoped_to_their_family(self):
        """'The registration officer is not allowed to see the financial oversight' — member information only, own family only."""
        user = User.objects.create_user(username="nrdr_family_reg_officer", password="x", community=self.bodi, role=Role.FAMILY_REGISTRATION_OFFICER)
        member = member_services.register_member(community=self.bodi, full_name="Reg Officer", gender="male", family=self.asona)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)
        result = build_dashboard(user)
        self.assertEqual(list(result["sections"]), ["registration_overview"])
        self.assertEqual(result["sections"]["registration_overview"]["registry"]["scope"], "family")

    def test_town_elders_arrears_officer_gets_the_traditional_leader_overview_section(self):
        user = User.objects.create_user(username="nrdr_town_arrears_officer", password="x", community=self.bodi, role=Role.TOWN_ELDERS_ARREARS_OFFICER)
        result = build_dashboard(user)
        self.assertIn("traditional_leader_overview", result["sections"])

    def test_town_registration_officer_gets_the_registration_overview_and_no_financial_figures(self):
        user = User.objects.create_user(username="nrdr_town_reg_officer", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        result = build_dashboard(user)
        self.assertEqual(list(result["sections"]), ["registration_overview"])
        overview = result["sections"]["registration_overview"]
        self.assertTrue(overview["registers_town_elders_only"])
        # Not one money figure anywhere in what this role is sent.
        import json
        flat = json.dumps(overview).lower()
        for banned in ("collect", "outstanding_total", "expense", "ledger", "paid", "owed", "balance", "amount"):
            self.assertNotIn(banned, flat, banned)

    def test_community_registration_desk_gets_the_registration_overview_scoped_to_the_community(self):
        user = User.objects.create_user(username="nrdr_comm_reg_desk", password="x", community=self.bodi, role=Role.COMMUNITY_REGISTRATION_DESK)
        result = build_dashboard(user)
        self.assertEqual(list(result["sections"]), ["registration_overview"])
        self.assertEqual(result["sections"]["registration_overview"]["registry"]["scope"], "community")

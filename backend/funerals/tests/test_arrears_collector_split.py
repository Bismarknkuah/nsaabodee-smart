from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class ArrearsVersusContributionCollectorTests(TestCase):
    """
    'Differentiate the arrears officers and the contribution collectors...
    the arrears collector should be able to clear or collect community
    members' arrears before they can pay the current bills.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="acs-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="acs_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Debtor", gender="male", family=self.asona)
        self.collector = User.objects.create_user(username="acs_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.arrears = User.objects.create_user(username="acs_arrears", password="x", community=self.bodi, role=Role.ARREARS_COLLECTOR)

        # Two closed funerals (older first) with nothing paid, then one open one.
        self.old1 = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Oldest", deceased_gender="male", deceased_family=self.asona, date_of_death="2026-01-01", collection_start_date="2026-01-02")
        funeral_services.close_funeral_event(funeral=self.old1, actor=self.admin)
        self.old2 = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Older", deceased_gender="female", deceased_family=self.asona, date_of_death="2026-03-01", collection_start_date="2026-03-02")
        funeral_services.close_funeral_event(funeral=self.old2, actor=self.admin)
        self.current = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Current", deceased_gender="male", deceased_family=self.asona, date_of_death="2026-09-01", collection_start_date="2026-09-02")
        self.ob1 = self.old1.obligations.get(member=self.member)   # 50 owed
        self.ob2 = self.old2.obligations.get(member=self.member)   # 50 owed
        self.obc = self.current.obligations.get(member=self.member)  # 50 owed

    def _client(self, user):
        c = APIClient(); c.force_authenticate(user); return c

    def test_a_contribution_collector_cannot_collect_a_closed_funerals_arrears(self):
        res = self._client(self.collector).post(f"/api/funerals/{self.old1.id}/obligations/{self.ob1.id}/record-payment/", {"amount": "10", "method": "cash", "collector_name": "C"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("Arrears Collector", res.data["detail"])

    def test_an_arrears_collector_can(self):
        res = self._client(self.arrears).post(f"/api/funerals/{self.old1.id}/obligations/{self.ob1.id}/record-payment/", {"amount": "10", "method": "cash", "collector_name": "A"})
        self.assertEqual(res.status_code, 201, res.data)

    def test_arrears_position_shows_current_bills_locked_until_arrears_are_cleared(self):
        pos = funeral_services.arrears_position(member=self.member)
        self.assertEqual([a["deceased_name"] for a in pos["arrears"]], ["Oldest", "Older"])
        self.assertEqual(Decimal(pos["total_arrears"]), Decimal("100"))
        self.assertFalse(pos["current_bills_payable"])
        self.assertEqual(pos["current_bills"][0]["deceased_name"], "Current")

    def test_a_lump_sum_clears_the_oldest_arrear_first_then_flows_on_to_the_current_bill(self):
        result = funeral_services.collect_arrears(member=self.member, amount=Decimal("120"), collector=self.arrears, collector_name="A")
        self.assertEqual([p["deceased_name"] for p in result["payments"]], ["Oldest", "Older", "Current"])
        self.assertEqual([Decimal(p["amount"]) for p in result["payments"]], [Decimal("50"), Decimal("50"), Decimal("20")])
        self.assertTrue(result["arrears_cleared"])
        self.assertEqual(Decimal(result["applied_to_current_bills"]), Decimal("20"))
        self.assertTrue(funeral_services.arrears_position(member=self.member)["current_bills_payable"])

    def test_a_partial_lump_sum_never_touches_the_newer_arrear_before_the_older_is_settled(self):
        result = funeral_services.collect_arrears(member=self.member, amount=Decimal("30"), collector=self.arrears, collector_name="A")
        self.assertEqual([p["deceased_name"] for p in result["payments"]], ["Oldest"])
        self.assertFalse(result["arrears_cleared"])
        self.ob2.refresh_from_db(); self.assertEqual(self.ob2.amount_paid, Decimal("0"))

    def test_more_than_everything_owed_is_refused(self):
        with self.assertRaises(ValidationError):
            funeral_services.collect_arrears(member=self.member, amount=Decimal("500"), collector=self.arrears)

    def test_the_arrears_collector_gets_their_own_dashboard_with_the_community_worklist(self):
        sections = build_dashboard(self.arrears)["sections"]
        self.assertEqual(list(sections), ["arrears_collector_overview"])
        ov = sections["arrears_collector_overview"]
        self.assertEqual(ov["members_owing_count"], 1)
        self.assertEqual(Decimal(ov["total_arrears_outstanding"]), Decimal("100"))
        self.assertEqual(ov["worklist"][0]["member_name"], "Debtor")
        # ...and the contribution collector keeps the open-funeral one.
        self.assertEqual(list(build_dashboard(self.collector)["sections"]), ["collector_performance"])

    def test_arrears_desk_endpoints_are_for_arrears_roles_only(self):
        a, c = self._client(self.arrears), self._client(self.collector)
        self.assertEqual(a.get("/api/arrears/worklist/").status_code, 200)
        self.assertEqual(c.get("/api/arrears/worklist/").status_code, 403)
        self.assertEqual(a.get(f"/api/arrears/members/{self.member.id}/position/").status_code, 200)
        res = a.post(f"/api/arrears/members/{self.member.id}/collect/", {"amount": "100", "method": "cash"})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["arrears_cleared"])
        self.assertEqual(c.post(f"/api/arrears/members/{self.member.id}/collect/", {"amount": "1"}).status_code, 403)

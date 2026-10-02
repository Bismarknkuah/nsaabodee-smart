from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community


class LedgerJurisdictionTests(TestCase):
    """
    'The town collector can only record for the elders in the Town Elders ledger; each family collector only
    his family's members... the town secretary and collector should have a ledger button; each family
    secretary and collector too, limited to his family.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="lj-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"))
        self.admin = User.objects.create_user(username="lj_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)
        self.asona_plain = member_services.register_member(community=self.bodi, full_name="Asona Plain", gender="male", family=self.asona, phone="0244000001")
        self.bretuo_plain = member_services.register_member(community=self.bodi, full_name="Bretuo Plain", gender="male", family=self.bretuo)
        self.asona_elder = member_services.register_member(community=self.bodi, full_name="Asona Elder", gender="male", family=self.asona)
        member_services.transfer_ledger(member=self.asona_elder, ledger="town_elders", actor=self.admin, title="linguist")
        funeral_services.create_funeral_event(community=self.bodi, deceased_name="D", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)

    def _user(self, username, role, family=None, nomination=None):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
        if family is not None:
            m = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
            member_services.link_member_to_user(member=m, user=user, actor=self.admin)
            if nomination:
                CollectorNomination.objects.create(community=self.bodi, member=m, collector_type=nomination, scoped_family=family if nomination == "family" else None, status=CollectorNomination.Status.APPROVED)
        c = APIClient(); c.force_authenticate(user); return c

    # ---- the Front Desk's next lookup is confined like the search ----
    def test_a_family_collector_cannot_look_up_an_elder_or_another_familys_member(self):
        c = self._user("lj_fam_col", Role.COLLECTOR, self.asona, "family")
        ok = c.get(f"/api/reports/members/{self.asona_plain.id}/outstanding-obligations/")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(c.get(f"/api/reports/members/{self.asona_elder.id}/outstanding-obligations/").status_code, 403)   # in the family, but on the elders' ledger
        self.assertEqual(c.get(f"/api/reports/members/{self.bretuo_plain.id}/outstanding-obligations/").status_code, 403)

    def test_a_town_elders_collector_can_look_up_elders_only(self):
        c = self._user("lj_te_col", Role.COLLECTOR, self.bretuo, "town_elder")
        self.assertEqual(c.get(f"/api/reports/members/{self.asona_elder.id}/outstanding-obligations/").status_code, 200)
        self.assertEqual(c.get(f"/api/reports/members/{self.asona_plain.id}/outstanding-obligations/").status_code, 403)

    def test_a_community_collector_looks_up_anyone(self):
        c = self._user("lj_col", Role.COLLECTOR)
        for m in (self.asona_plain, self.bretuo_plain, self.asona_elder):
            self.assertEqual(c.get(f"/api/reports/members/{m.id}/outstanding-obligations/").status_code, 200)

    # ---- the ledger buttons: /me says which ledger an account serves ----
    def test_me_reports_the_ledger_scope(self):
        self.assertEqual(self._user("lj_scope_te", Role.COLLECTOR, self.bretuo, "town_elder").get("/api/auth/me/").data["ledger_scope"]["level"], "town_elders")
        fam = self._user("lj_scope_fam", Role.COLLECTOR, self.asona, "family").get("/api/auth/me/").data["ledger_scope"]
        self.assertEqual((fam["level"], fam["family_name"]), ("family", "Asona"))
        self.assertEqual(self._user("lj_scope_c", Role.COLLECTOR).get("/api/auth/me/").data["ledger_scope"]["level"], "community")
        self.assertEqual(self._user("lj_scope_tro", Role.TOWN_REGISTRATION_OFFICER).get("/api/auth/me/").data["ledger_scope"]["level"], "town_elders")
        self.assertEqual(self._user("lj_scope_fs", Role.FAMILY_SECRETARY, self.asona).get("/api/auth/me/").data["ledger_scope"]["family_name"], "Asona")

    # ---- the family ledger, limited to the family ----
    def test_a_family_secretary_and_family_collector_see_their_own_familys_ledger_only(self):
        for c in (self._user("lj_fl_sec", Role.FAMILY_SECRETARY, self.asona), self._user("lj_fl_col", Role.COLLECTOR, self.asona, "family")):
            data = c.get("/api/reports/family-ledger/").data
            self.assertEqual(data["family_name"], "Asona")
            names = {m["member_name"] for m in data["members"]}
            self.assertIn("Asona Plain", names)
            self.assertNotIn("Bretuo Plain", names)
            self.assertNotIn("Asona Elder", names)                                     # pays the elders' ledger, not the family's
            sneaky = c.get(f"/api/reports/family-ledger/?family={self.bretuo.id}").data   # asking for another family changes nothing
            self.assertEqual(sneaky["family_name"], "Asona")

    def test_outsiders_and_the_town_elders_collector_cannot_read_a_family_ledger(self):
        self.assertEqual(self._user("lj_fl_te", Role.COLLECTOR, self.bretuo, "town_elder").get("/api/reports/family-ledger/").status_code, 403)
        self.assertEqual(self._user("lj_fl_member", Role.COMMUNITY_MEMBER, self.asona).get("/api/reports/family-ledger/").status_code, 403)

    def test_community_oversight_chooses_a_family(self):
        c = self._user("lj_fl_fin", Role.FINANCIAL_SECRETARY)
        self.assertEqual(c.get("/api/reports/family-ledger/").status_code, 400)
        self.assertEqual(c.get(f"/api/reports/family-ledger/?family={self.bretuo.id}").data["family_name"], "Bretuo")

    # ---- the Town Elders ledger: the chief, the town secretary, their collector ----
    def test_the_town_secretary_and_the_elders_collector_read_the_town_elders_ledger_and_a_family_collector_cannot(self):
        self.assertEqual(self._user("lj_te_tro", Role.TOWN_REGISTRATION_OFFICER).get("/api/reports/town-elders-ledger/").status_code, 200)
        self.assertEqual(self._user("lj_te_chief", Role.TRADITIONAL_LEADER).get("/api/reports/town-elders-ledger/").status_code, 200)
        self.assertEqual(self._user("lj_te_col2", Role.COLLECTOR, self.bretuo, "town_elder").get("/api/reports/town-elders-ledger/").status_code, 200)
        self.assertEqual(self._user("lj_te_famcol", Role.COLLECTOR, self.asona, "family").get("/api/reports/town-elders-ledger/").status_code, 403)

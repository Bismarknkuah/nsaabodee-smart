from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from welfare.tests._helpers import wm_for
from django.test import override_settings
from rest_framework.test import APIClient

from accounts import services as account_services
from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community
from welfare import services as welfare_services


class RedesignedRoleDashboardTests(TestCase):
    """Collectors, registrars and welfare managers at every level — each with real tools, each inside its own reach."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="rrd-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"))
        self.admin = User.objects.create_user(username="rrd_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)
        self.asona_debtor = member_services.register_member(community=self.bodi, full_name="Asona Debtor", gender="male", family=self.asona, phone="0244000001")
        self.bretuo_debtor = member_services.register_member(community=self.bodi, full_name="Bretuo Debtor", gender="male", family=self.bretuo, phone="0244000002")
        self.elder_debtor = member_services.register_member(community=self.bodi, full_name="Elder Debtor", gender="male", family=self.bretuo, contribution_ledger="town_elders")
        self.funeral = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Open One", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)

    def _collector(self, username, ctype=None, family=None):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=Role.COLLECTOR)
        m = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=self.asona)
        member_services.link_member_to_user(member=m, user=user, actor=self.admin)
        if ctype:
            CollectorNomination.objects.create(community=self.bodi, member=m, collector_type=ctype, scoped_family=family, status=CollectorNomination.Status.APPROVED)
        return user

    # ---------------- collectors ----------------
    def test_who_to_chase_is_scoped_to_each_collectors_own_jurisdiction(self):
        community = self._collector("rrd_c_comm")
        family = self._collector("rrd_c_fam", "family", self.asona)
        elders = self._collector("rrd_c_elders", "town_elder")
        names = lambda u: {r["member_name"] for r in build_dashboard(u)["sections"]["collector_performance"]["owing_now"]["rows"]}
        self.assertTrue({"Asona Debtor", "Bretuo Debtor", "Elder Debtor"} <= names(community))
        self.assertEqual(names(family) & {"Asona Debtor", "Bretuo Debtor", "Elder Debtor"}, {"Asona Debtor"})
        self.assertEqual(names(elders) & {"Asona Debtor", "Bretuo Debtor", "Elder Debtor"}, {"Elder Debtor"})

    def test_a_chase_row_carries_what_a_collector_needs_to_act(self):
        row = next(r for r in build_dashboard(self._collector("rrd_c_row"))["sections"]["collector_performance"]["owing_now"]["rows"] if r["member_name"] == "Asona Debtor")
        self.assertEqual((row["phone"], row["family_name"], row["oldest_deceased_name"]), ("0244000001", "Asona", "Open One"))
        self.assertGreater(Decimal(row["total_owed"]), 0)

    def test_the_handover_splits_by_method_and_recent_entries_are_listed(self):
        col = self._collector("rrd_c_cash")
        funeral_services.record_payment(obligation=self.funeral.obligations.get(member=self.asona_debtor), amount=Decimal("3"), method="cash", collector=col, collector_name="C")
        funeral_services.record_payment(obligation=self.funeral.obligations.get(member=self.bretuo_debtor), amount=Decimal("2"), method="mobile_money", collector=col, collector_name="C")
        t = build_dashboard(col)["sections"]["collector_performance"]["my_takings"]
        self.assertEqual((Decimal(t["today_by_method"]["cash"]), Decimal(t["today_by_method"]["mobile_money"])), (Decimal("3"), Decimal("2")))
        self.assertEqual({r["who"] for r in t["recent"]}, {"Asona Debtor", "Bretuo Debtor"})

    # ---------------- registrars ----------------
    def test_the_registrar_gets_a_data_gap_centre_scoped_to_their_reach(self):
        tro = User.objects.create_user(username="rrd_tro", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        fro = User.objects.create_user(username="rrd_fro", password="x", community=self.bodi, role=Role.FAMILY_REGISTRATION_OFFICER)
        fm = member_services.register_member(community=self.bodi, full_name="Asona Registrar", gender="female", family=self.asona)
        member_services.link_member_to_user(member=fm, user=fro, actor=self.admin)
        town = build_dashboard(tro)["sections"]["registration_overview"]["data_quality"]
        fam = build_dashboard(fro)["sections"]["registration_overview"]["data_quality"]
        self.assertIn("Bretuo Debtor", {r["full_name"] for r in town["missing_date_of_birth"]["rows"]})
        self.assertNotIn("Bretuo Debtor", {r["full_name"] for r in fam["missing_date_of_birth"]["rows"]})   # a family registrar never sees another family's gaps
        self.assertIn("Asona Debtor", {r["full_name"] for r in fam["missing_date_of_birth"]["rows"]})
        self.assertEqual(town["missing_phone"]["count"] >= 1, True)

    def test_ledger_activity_appears_on_the_registrars_dashboard(self):
        tro = User.objects.create_user(username="rrd_tro2", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        member_services.transfer_ledger(member=self.asona_debtor, ledger="town_elders", title="linguist", actor=tro, reason="Appointed")
        activity = build_dashboard(tro)["sections"]["registration_overview"]["ledger_activity"]
        self.assertEqual((activity[0]["member_name"], activity[0]["to_ledger"], activity[0]["by"]), ("Asona Debtor", "town_elders", "rrd_tro2"))

    # ---------------- welfare ----------------
    def _welfare_setup(self):
        category = welfare_services.create_contribution_category(community=self.bodi, name="Welfare", fixed_amount=Decimal("10"), actor=self.admin)
        campaign = welfare_services.initiate_community_campaign(category=category, title="Relief", amount=Decimal("10"), actor=wm_for(self.admin))
        wm = User.objects.create_user(username="rrd_wm", password="x", community=self.bodi, role=Role.WELFARE_MANAGER)
        wmm = member_services.register_member(community=self.bodi, full_name="Welfare Mgr", gender="female", family=self.asona)
        member_services.link_member_to_user(member=wmm, user=wm, actor=self.admin)
        req = welfare_services.submit_welfare_request(campaign=campaign, requester=self.asona_debtor, amount_requested=Decimal("100"), reason="Roof")
        return campaign, wm, wmm, req

    def test_the_welfare_manager_dashboard_carries_the_tools_to_act(self):
        campaign, wm, _, req = self._welfare_setup()
        ov = build_dashboard(wm)["sections"]["welfare_manager_overview"]
        self.assertEqual(ov["pending_requests"][0]["campaign_id"], str(campaign.id))
        self.assertEqual([c["name"] for c in ov["categories"]], ["Welfare"])
        camp = next(c for c in ov["campaigns"] if c["id"] == str(campaign.id))
        self.assertIn("progress_pct", camp)
        self.assertTrue(camp["owing"] == [] or "phone" in camp["owing"][0])

    def test_requests_in_reach_and_what_each_person_may_do(self):
        campaign, wm, wmm, req = self._welfare_setup()
        c = APIClient(); c.force_authenticate(wm)
        row = c.get("/api/welfare/requests/").data[0]
        self.assertEqual((row["requester_name"], row["can_decide"], row["can_disburse"]), ("Asona Debtor", True, False))
        requester_user = User.objects.create_user(username="rrd_req", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.asona_debtor, user=requester_user, actor=self.admin)
        r = APIClient(); r.force_authenticate(requester_user)
        mine = r.get("/api/welfare/requests/").data
        self.assertEqual(len(mine), 1)
        self.assertEqual((mine[0]["is_mine"], mine[0]["can_decide"]), (True, False))
        other = User.objects.create_user(username="rrd_other", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.bretuo_debtor, user=other, actor=self.admin)
        o = APIClient(); o.force_authenticate(other)
        self.assertEqual(o.get("/api/welfare/requests/").data, [])   # a member never sees someone else's request

    def test_nobody_decides_their_own_request_and_the_decider_never_pays_out(self):
        campaign, wm, wmm, _ = self._welfare_setup()
        own = welfare_services.submit_welfare_request(campaign=campaign, requester=wmm, amount_requested=Decimal("50"), reason="Own need")
        with self.assertRaises(ValidationError):
            welfare_services.decide_welfare_request(request=own, actor=wm, approve=True)
        other = welfare_services.submit_welfare_request(campaign=campaign, requester=self.bretuo_debtor, amount_requested=Decimal("40"), reason="Fees")
        welfare_services.decide_welfare_request(request=other, actor=wm, approve=True, amount_approved=Decimal("30"))
        with self.assertRaises(ValidationError):
            welfare_services.disburse_welfare_request(request=other, actor=wm)          # the welfare manager cannot hand over the money
        fin = User.objects.create_user(username="rrd_fin", password="x", community=self.bodi, role=Role.FINANCIAL_SECRETARY)
        paid = welfare_services.disburse_welfare_request(request=other, actor=fin)       # finance can
        self.assertEqual(paid.status, "disbursed")

    # ---------------- personas & labels ----------------
    def test_collector_levels_are_named_in_their_labels(self):
        self.assertEqual(account_services.role_label_for(self._collector("rrd_l_fam", "family", self.asona)), "Asona Collector")
        self.assertEqual(account_services.role_label_for(self._collector("rrd_l_elders", "town_elder")), "Town Elders Collector")
        self.assertEqual(account_services.role_label_for(self._collector("rrd_l_don", "donation", self.asona)), "Asona Donation Collector")
        self.assertEqual(account_services.role_label_for(self._collector("rrd_l_comm")), "Collector")

    @override_settings(DEMO_MODE_ENABLED=True)
    def test_the_demo_personas_log_in_and_carry_their_level(self):
        from django.core.management import call_command
        call_command("seed_demo_data")
        c = APIClient()
        for persona in ("family_collector", "town_elders_collector"):
            self.assertEqual(c.post("/api/auth/demo-login/", {"role": persona}).status_code, 200, persona)
        fam = User.objects.get(username="demo_family_collector"); el = User.objects.get(username="demo_town_elders_collector")
        self.assertEqual((fam.role, el.role), ("collector", "collector"))
        self.assertEqual(account_services.role_label_for(fam), "Asona Collector")
        self.assertEqual(account_services.role_label_for(el), "Town Elders Collector")

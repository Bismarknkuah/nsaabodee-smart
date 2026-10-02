from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from reports import services as report_services
from tenants.models import Community


class CollectorsTakingsTests(TestCase):
    """'Each collector can see what they have received daily and for each funeral; the financial secretary sees all collectors; the family treasurer sees all money collected for the family.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ct-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="ct_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)
        self.asona_m = member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)
        self.bretuo_m = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)
        self.asona_m2 = member_services.register_member(community=self.bodi, full_name="Asona Member Two", gender="female", family=self.asona)
        self.c1 = User.objects.create_user(username="ct_collector_one", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.c2 = User.objects.create_user(username="ct_collector_two", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.fin_sec = User.objects.create_user(username="ct_fin_sec", password="x", community=self.bodi, role=Role.FINANCIAL_SECRETARY)
        self.treasurer = User.objects.create_user(username="ct_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.f1 = funeral_services.create_funeral_event(community=self.bodi, deceased_name="First", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02")
        self.f2 = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Second", deceased_gender="female", deceased_family=self.asona, date_of_death="2026-09-10", collection_start_date="2026-09-11")
        # c1 takes 4 from an Asona member on First and 3 from a Bretuo member on First; c2 takes 5 from a second Asona
        # member on Second (a different member, because the older-debt rule blocks the first one paying a newer funeral).
        funeral_services.record_payment(obligation=self.f1.obligations.get(member=self.asona_m), amount=Decimal("4"), method="cash", collector=self.c1, collector_name="C1")
        funeral_services.record_payment(obligation=self.f1.obligations.get(member=self.bretuo_m), amount=Decimal("3"), method="cash", collector=self.c1, collector_name="C1")
        # ...and she must settle First (3) before Second can take her 5 — the older-debt rule, so c2 takes both.
        funeral_services.record_payment(obligation=self.f1.obligations.get(member=self.asona_m2), amount=Decimal("3"), method="cash", collector=self.c2, collector_name="C2")
        funeral_services.record_payment(obligation=self.f2.obligations.get(member=self.asona_m2), amount=Decimal("5"), method="cash", collector=self.c2, collector_name="C2")

    def test_a_collector_sees_only_their_own_takings_by_day_and_by_funeral(self):
        t = report_services.collector_takings(collector=self.c1)
        self.assertEqual(Decimal(t["totals"]["all_time"]), Decimal("7"))
        self.assertEqual(Decimal(t["totals"]["today"]), Decimal("7"))
        self.assertEqual({r["deceased_name"]: Decimal(r["total"]) for r in t["by_funeral"]}, {"First": Decimal("7")})
        self.assertEqual(len(t["by_day"]), 14)
        self.assertEqual(Decimal(t["by_day"][-1]["total"]), Decimal("7"))

    def test_the_financial_secretary_sees_every_collector_but_the_treasurer_does_not(self):
        fs = build_dashboard(self.fin_sec)["sections"]["financial_overview"]
        rows = {r["username"]: Decimal(r["totals"]["all_time"]) for r in fs["collectors_takings"]["collectors"]}
        self.assertEqual(rows, {"ct_collector_one": Decimal("7"), "ct_collector_two": Decimal("8")})
        self.assertEqual(Decimal(fs["collectors_takings"]["totals"]["all_time"]), Decimal("15"))
        self.assertNotIn("collectors_takings", build_dashboard(self.treasurer)["sections"]["financial_overview"])

    def test_a_family_treasurer_sees_all_money_collected_for_their_family_only(self):
        t_user = User.objects.create_user(username="ct_asona_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        m = member_services.register_member(community=self.bodi, full_name="Asona Treasurer", gender="female", family=self.asona)
        member_services.link_member_to_user(member=m, user=t_user, actor=self.admin)
        fam = build_dashboard(t_user)["sections"]["family_overview"]["family_collectors_takings"]
        # Asona members paid 4 (to c1) + 3 + 5 (to c2) = 12; the Bretuo member's 3 is not Asona's money.
        self.assertEqual(Decimal(fam["totals"]["all_time"]), Decimal("12"))
        self.assertEqual({r["username"]: Decimal(r["totals"]["all_time"]) for r in fam["collectors"]}, {"ct_collector_one": Decimal("4"), "ct_collector_two": Decimal("8")})

    def test_every_collector_dashboard_carries_my_takings(self):
        for role in (Role.COLLECTOR, Role.ARREARS_COLLECTOR, Role.GIFT_COLLECTOR, Role.TOWN_ELDERS_ARREARS_OFFICER):
            u = User.objects.create_user(username=f"ct_{role}", password="x", community=self.bodi, role=role)
            section = next(iter(build_dashboard(u)["sections"].values()))
            self.assertIn("my_takings", section, role)

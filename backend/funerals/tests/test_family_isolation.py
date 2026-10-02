from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community
from welfare import services as welfare_services


class FamilyIsolationTests(TestCase):
    """'Each family executive's role should be isolated, so they can't access or see other families' members.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fiso-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"))
        self.admin = User.objects.create_user(username="fiso_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)
        self.asona_m = member_services.register_member(community=self.bodi, full_name="Asona One", gender="male", family=self.asona)
        self.bretuo_m = member_services.register_member(community=self.bodi, full_name="Bretuo One", gender="male", family=self.bretuo)
        self.asona_elder = member_services.register_member(community=self.bodi, full_name="Asona Elder", gender="male", family=self.asona)
        member_services.transfer_ledger(member=self.asona_elder, ledger="town_elders", actor=self.admin, title="linguist")
        self.funeral = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Opanin", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)

    def _officer(self, username, role, family, nomination=None):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
        m = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
        member_services.link_member_to_user(member=m, user=user, actor=self.admin)
        if nomination:
            CollectorNomination.objects.create(community=self.bodi, member=m, collector_type=nomination, scoped_family=family if nomination == "family" else None, status=CollectorNomination.Status.APPROVED)
        c = APIClient(); c.force_authenticate(user); return c, m

    def _names(self, res):
        rows = res.data["results"] if isinstance(res.data, dict) and "results" in res.data else res.data
        return {r["member_name"] if "member_name" in r else r.get("member", {}).get("full_name") for r in rows}

    def test_a_funerals_obligations_show_a_family_officer_only_their_own_family(self):
        for username, role in (("fiso_sec", Role.FAMILY_SECRETARY), ("fiso_head", Role.FAMILY_HEAD), ("fiso_tre", Role.FAMILY_TREASURER)):
            c, _ = self._officer(username, role, self.asona)
            names = self._names(c.get(f"/api/funerals/{self.funeral.id}/obligations/"))
            self.assertIn("Asona One", names, username)
            self.assertNotIn("Bretuo One", names, username)
            self.assertNotIn("Asona Elder", names, username)           # pays the elders' ledger, not the family's
        c, _ = self._officer("fiso_fcol", Role.COLLECTOR, self.asona, "family")
        names = self._names(c.get(f"/api/funerals/{self.funeral.id}/obligations/"))
        self.assertEqual(names & {"Asona One", "Bretuo One", "Asona Elder"}, {"Asona One"})

    def test_community_oversight_and_the_community_collector_still_see_everyone(self):
        for client in (APIClient(), ):
            client.force_authenticate(self.admin)
            self.assertTrue({"Asona One", "Bretuo One", "Asona Elder"} <= self._names(client.get(f"/api/funerals/{self.funeral.id}/obligations/")))
        c, _ = self._officer("fiso_col", Role.COLLECTOR, self.bretuo)      # a community collector (no nomination = the community desk)
        self.assertTrue({"Asona One", "Bretuo One"} <= self._names(c.get(f"/api/funerals/{self.funeral.id}/obligations/")))

    def test_a_family_officer_sees_only_their_own_familys_collector_nominations(self):
        c_sec, _ = self._officer("fiso_sec2", Role.FAMILY_SECRETARY, self.asona)
        b_head_client, b_head = self._officer("fiso_b_head", Role.FAMILY_HEAD, self.bretuo)
        member_services.nominate_collector(member=self.asona_m, collector_type="family", actor=User.objects.get(username="fiso_sec2"))
        member_services.nominate_collector(member=self.bretuo_m, collector_type="family", actor=User.objects.get(username="fiso_b_head"))
        asona_sees = {n["member_name"] if "member_name" in n else n["member"]["full_name"] for n in c_sec.get("/api/members/collector-nominations/").data}
        self.assertIn("Asona One", asona_sees)
        self.assertNotIn("Bretuo One", asona_sees)
        admin = APIClient(); admin.force_authenticate(self.admin)
        self.assertEqual(len(admin.get("/api/members/collector-nominations/").data), 2)

    def test_the_welfare_manager_creates_every_type_of_welfare_in_their_jurisdiction(self):
        wm = User.objects.create_user(username="fiso_wm", password="x", community=self.bodi, role=Role.WELFARE_MANAGER)
        cat = welfare_services.create_contribution_category(community=self.bodi, name="Voluntary support", is_mandatory=False, amount_type="flexible", actor=wm)
        self.assertEqual(cat.community_id, self.bodi.id)
        fixed = welfare_services.create_contribution_category(community=self.bodi, name="Annual dues", fixed_amount=Decimal("10"), actor=wm)
        self.assertIsNotNone(welfare_services.initiate_community_campaign(category=fixed, title="Community welfare", actor=wm).id)
        self.assertEqual(welfare_services.initiate_family_campaign(category=fixed, family=self.asona, title="Asona welfare", actor=wm).family_id, self.asona.id)
        from django.core.exceptions import ValidationError
        self._officer("fiso_sec3", Role.FAMILY_SECRETARY, self.asona)
        with self.assertRaises(ValidationError):                                 # a family officer creates no welfare of any type
            welfare_services.create_contribution_category(community=self.bodi, name="Nope", fixed_amount=Decimal("1"), actor=User.objects.get(username="fiso_sec3"))

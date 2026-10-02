from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community


class CollectorWorklistJurisdictionTests(TestCase):
    """
    One role, three levels: a Collector's arrears worklist is the community's, one family's, or the
    Town Elders' — decided by nomination — and every row is the same rich row (phone, family, oldest
    funeral, funeral count) so the call/text actions work at every level.
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="cwl-bodi", default_general_male_amount=Decimal("5"),
            default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"),
        )
        self.admin = User.objects.create_user(username="cwl_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)

        reg = lambda name, fam, phone: member_services.register_member(community=self.bodi, full_name=name, gender="male", family=fam, phone=phone)
        self.asona_plain = reg("Asona Plain", self.asona, "0244000001")
        self.bretuo_plain = reg("Bretuo Plain", self.bretuo, "0244000002")
        self.asona_elder = reg("Asona Elder", self.asona, "0244000003")
        member_services.transfer_ledger(member=self.asona_elder, ledger="town_elders", actor=self.admin, title="linguist")

        old = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Old One", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-01-01", collection_start_date="2026-01-02", actor=self.admin)
        funeral_services.close_funeral_event(funeral=old, actor=self.admin)   # nobody paid: real arrears

    def _collector(self, username, *nominations):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=Role.COLLECTOR)
        member = member_services.register_member(community=self.bodi, full_name=f"{username} member", gender="male", family=self.asona)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)
        for ctype, fam in nominations:
            CollectorNomination.objects.create(community=self.bodi, member=member, collector_type=ctype, scoped_family=fam, status=CollectorNomination.Status.APPROVED)
        return user

    def _worklist(self, user):
        return build_dashboard(user)["sections"]["collector_performance"]["arrears"]["worklist"]

    def test_a_family_collector_sees_only_their_familys_arrears_with_full_rows(self):
        rows = self._worklist(self._collector("cwl_family", ("family", self.asona)))
        names = {r["member_name"] for r in rows}
        self.assertIn("Asona Plain", names)
        self.assertNotIn("Bretuo Plain", names)                  # another family's debtor is not theirs
        row = next(r for r in rows if r["member_name"] == "Asona Plain")
        self.assertEqual(row["family_name"], "Asona")            # used to come back empty for this level
        self.assertEqual(row["phone"], "0244000001")             # so Call / Text work here too
        self.assertEqual(row["oldest_deceased_name"], "Old One")
        self.assertEqual(row["funeral_count"], 1)

    def test_the_ledger_decides_who_collects_a_moved_member_belongs_to_the_elders_collector(self):
        """
        An Asona member moved onto the Town Elders ledger is still in Asona, but no longer pays Asona.
        His arrears are the Town Elders collector's to chase — and drop off the Asona family collector's list.
        """
        elders_rows = self._worklist(self._collector("cwl_elders", ("town_elder", None)))
        self.assertEqual({r["member_name"] for r in elders_rows}, {"Asona Elder"})
        self.assertEqual(elders_rows[0]["family_name"], "Asona")            # he still belongs to his family
        family_names = {r["member_name"] for r in self._worklist(self._collector("cwl_family2", ("family", self.asona)))}
        self.assertIn("Asona Plain", family_names)
        self.assertNotIn("Asona Elder", family_names)

    def test_only_the_collector_whose_ledger_it_is_may_record_the_money(self):
        from funerals.jurisdiction import can_record_arrears
        from funerals.models import ContributionObligation
        family, elders = self._collector("cwl_f3", ("family", self.asona)), self._collector("cwl_e3", ("town_elder", None))
        elder_ob = ContributionObligation.objects.get(member=self.asona_elder)
        plain_ob = ContributionObligation.objects.get(member=self.asona_plain)
        self.assertEqual(elder_ob.rate_type, "town_elder")                  # billed on the elders' ledger
        self.assertFalse(can_record_arrears(family, elder_ob))              # ...so not the family collector's
        self.assertTrue(can_record_arrears(elders, elder_ob))
        self.assertTrue(can_record_arrears(family, plain_ob))
        self.assertFalse(can_record_arrears(elders, plain_ob))

    def test_a_family_collector_cannot_search_up_a_member_on_the_elders_ledger(self):
        names = {m.full_name for m in member_services.search_members(community=self.bodi, actor=self._collector("cwl_f4", ("family", self.asona)))}
        self.assertIn("Asona Plain", names)
        self.assertNotIn("Asona Elder", names)

    def test_the_community_collector_sees_everyone(self):
        names = {r["member_name"] for r in self._worklist(self._collector("cwl_community"))}
        self.assertTrue({"Asona Plain", "Bretuo Plain", "Asona Elder"} <= names)

    def test_a_collector_with_two_scopes_sees_each_debtor_once(self):
        rows = self._worklist(self._collector("cwl_both", ("family", self.asona), ("town_elder", None)))
        ids = [r["member_id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))                # the Asona elder falls in both scopes: one row, not two
        self.assertIn("Asona Elder", {r["member_name"] for r in rows})

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class ContributionLedgerChoiceTests(TestCase):
    """
    'When registering a new member he has to select the family he belongs to, and
    also a ledger... a member can belong to a family but contribute his funeral to
    the Town Elders ledger. Once a family member is called to be part of the town
    executives, he pays his funeral contribution in the Town Elders ledger.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="clc-bodi", default_general_male_amount=Decimal("5"),
            default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"),
        )
        self.admin = User.objects.create_user(username="clc_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.tro = User.objects.create_user(username="clc_tro", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)

    def _funeral(self, name, family, start):
        return funeral_services.create_funeral_event(community=self.bodi, deceased_name=name, deceased_gender="male", deceased_family=family, date_of_death=start, collection_start_date=start, actor=self.admin)

    # ---- registration ----
    def test_the_default_ledger_is_family_and_community(self):
        m = member_services.register_member(community=self.bodi, full_name="Ordinary", gender="male", family=self.asona, registered_by=self.tro)
        self.assertEqual(m.contribution_ledger, "family")
        self.assertFalse(m.is_town_leader)

    def test_a_member_keeps_their_family_and_contributes_to_the_town_elders_ledger(self):
        m = member_services.register_member(community=self.bodi, full_name="Family Elder", gender="male", family=self.asona, contribution_ledger="town_elders", registered_by=self.tro)
        self.assertEqual(m.family_id, self.asona.id)             # still belongs to the family
        self.assertEqual(m.contribution_ledger, "town_elders")   # but pays in the elders' ledger
        self.assertTrue(m.is_town_leader)
        self.assertEqual(m.town_elder_title, "other")

    def test_the_admin_can_also_register_onto_the_elders_ledger_with_a_title(self):
        m = member_services.register_member(community=self.bodi, full_name="The Chief", gender="male", family=self.bretuo, contribution_ledger="town_elders", town_elder_title="chief", registered_by=self.admin)
        self.assertEqual(m.town_elder_title, "chief")

    def test_the_king_and_queen_belong_to_a_family_too(self):
        """'Every member belongs to a family, including the king and queen of the town.'"""
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="The Queen Mother", gender="female", family=None, contribution_ledger="town_elders", town_elder_title="queen_mother", registered_by=self.admin)
        queen = member_services.register_member(community=self.bodi, full_name="The Queen Mother", gender="female", family=self.bretuo, contribution_ledger="town_elders", town_elder_title="queen_mother", registered_by=self.admin)
        self.assertEqual((queen.family_id, queen.contribution_ledger), (self.bretuo.id, "town_elders"))

    def test_the_old_ledger_name_still_means_the_family_ledger(self):
        m = member_services.register_member(community=self.bodi, full_name="Legacy Caller", gender="male", family=self.asona, contribution_ledger="community", registered_by=self.tro)
        self.assertEqual(m.contribution_ledger, "family")

    def test_the_town_registration_officer_must_choose_a_family(self):
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="No Family", gender="male", family=None, registered_by=self.tro)

    def test_a_family_registrar_cannot_place_anyone_on_the_elders_ledger(self):
        sec = User.objects.create_user(username="clc_fam_sec", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        m = member_services.register_member(community=self.bodi, full_name="Sec Person", gender="male", family=self.asona)
        member_services.link_member_to_user(member=m, user=sec, actor=self.admin)
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="Sneaky Elder", gender="male", family=self.asona, contribution_ledger="town_elders", registered_by=sec)

    def test_contradictory_ledger_choices_are_refused(self):
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="Confused", gender="male", family=self.asona, contribution_ledger="family", is_town_leader=True)
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="Nonsense", gender="male", family=self.asona, contribution_ledger="guest")

    # ---- the billing consequence ----
    def test_the_ledger_decides_the_rate_on_the_next_funeral_whatever_the_family(self):
        elder = member_services.register_member(community=self.bodi, full_name="Asona Elder", gender="male", family=self.asona, contribution_ledger="town_elders", registered_by=self.tro)
        plain = member_services.register_member(community=self.bodi, full_name="Asona Plain", gender="male", family=self.asona, registered_by=self.tro)
        f = self._funeral("Bretuo Death", self.bretuo, "2026-09-02")
        self.assertEqual(f.obligations.get(member=elder).rate_type, "town_elder")
        self.assertEqual(f.obligations.get(member=elder).expected_amount, Decimal("20"))
        self.assertEqual(f.obligations.get(member=plain).rate_type, "general")

    def test_promotion_moves_a_family_member_to_the_elders_ledger_for_future_funerals_only(self):
        """'Once a family member is called to be part of the town executives, he pays his funeral contribution in the Town Elders ledger.'"""
        member = member_services.register_member(community=self.bodi, full_name="Soon An Elder", gender="male", family=self.asona, registered_by=self.tro)
        before = self._funeral("Before", self.bretuo, "2026-09-02")
        old_obligation = before.obligations.get(member=member)
        old_type, old_amount = old_obligation.rate_type, old_obligation.expected_amount

        member_services.transfer_to_town_elder(member=member, title="linguist", actor=self.tro)   # the registrar may promote
        member.refresh_from_db()
        self.assertEqual(member.contribution_ledger, "town_elders")
        self.assertEqual(member.family_id, self.asona.id)

        after = self._funeral("After", self.bretuo, "2026-09-20")
        self.assertEqual(after.obligations.get(member=member).rate_type, "town_elder")
        old_obligation.refresh_from_db()
        self.assertEqual((old_obligation.rate_type, old_obligation.expected_amount), (old_type, old_amount))  # never retroactive

        member_services.remove_from_town_elder(member=member, actor=self.tro)
        member.refresh_from_db()
        self.assertEqual(member.contribution_ledger, "family")

    # ---- the API ----
    def test_registration_endpoint_takes_family_and_ledger(self):
        c = APIClient(); c.force_authenticate(self.tro)
        res = c.post("/api/members/", {"full_name": "Api Elder", "gender": "male", "family_id": str(self.asona.id), "contribution_ledger": "town_elders", "town_elder_title": "queen_mother"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["contribution_ledger"], "town_elders")
        self.assertEqual(str(res.data["family"]), str(self.asona.id))
        missing = c.post("/api/members/", {"full_name": "No Family Api", "gender": "male"}, format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("family_id", missing.data)

    def test_registry_analytics_counts_members_by_ledger(self):
        member_services.register_member(community=self.bodi, full_name="E1", gender="male", family=self.asona, contribution_ledger="town_elders", registered_by=self.tro)
        member_services.register_member(community=self.bodi, full_name="P1", gender="male", family=self.bretuo, registered_by=self.tro)
        a = member_services.member_registry_analytics(actor=self.tro)
        self.assertEqual(a["by_contribution_ledger"], {"family": 1, "town_elders": 1})


class LedgerTransferTests(TestCase):
    """'A member should be transferred from one ledger to another' — and an elder does not pay their family's ledger."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="lt-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"))
        self.admin = User.objects.create_user(username="lt_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.tro = User.objects.create_user(username="lt_tro", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

    def _funeral(self, name, date):
        return funeral_services.create_funeral_event(community=self.bodi, deceased_name=name, deceased_gender="male", deceased_family=self.asona, date_of_death=date, collection_start_date=date, actor=self.admin)

    def test_an_elder_in_the_deceased_familys_own_funeral_pays_the_elders_ledger_not_the_family_ledger(self):
        """'Once promoted they don't pay their funeral contribution to their family, but in the town elders' ledger.'"""
        plain = member_services.register_member(community=self.bodi, full_name="Plain Asona", gender="male", family=self.asona, registered_by=self.tro)
        elder = member_services.register_member(community=self.bodi, full_name="Asona Elder", gender="male", family=self.asona, contribution_ledger="town_elders", registered_by=self.tro)
        f = self._funeral("Asona Death", "2026-09-02")
        self.assertEqual(f.obligations.get(member=plain).rate_type, "own_family")   # family ledger
        self.assertEqual(f.obligations.get(member=elder).rate_type, "town_elder")   # NOT the family ledger
        summary = funeral_services.funeral_summary(f)
        self.assertEqual(Decimal(str(summary["town_elder"]["expected_total"])), Decimal("20"))

    def test_transfer_there_and_back_keeps_the_family_and_records_who_and_why(self):
        m = member_services.register_member(community=self.bodi, full_name="Kofi", gender="male", family=self.asona, registered_by=self.tro)
        member_services.transfer_ledger(member=m, ledger="town_elders", title="chief", actor=self.tro, reason="Enstooled as chief")
        m.refresh_from_db()
        self.assertEqual((m.contribution_ledger, m.family_id, m.town_elder_title), ("town_elders", self.asona.id, "chief"))
        member_services.transfer_ledger(member=m, ledger="family", actor=self.admin, reason="Stepped down")
        m.refresh_from_db()
        self.assertEqual((m.contribution_ledger, m.family_id), ("family", self.asona.id))
        history = member_services.ledger_history(member=m)
        self.assertEqual([h["to_ledger"] for h in history], ["family", "town_elders"])
        self.assertIn("Enstooled as chief", history[1]["description"])
        self.assertEqual(history[0]["by"], "lt_admin")

    def test_transferring_to_the_ledger_a_member_is_already_on_is_refused(self):
        m = member_services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.asona, registered_by=self.tro)
        with self.assertRaises(ValidationError):
            member_services.transfer_ledger(member=m, ledger="family", actor=self.tro)

    def test_a_member_with_no_family_must_be_given_one_before_any_ledger_move(self):
        orphan = member_services.register_member(community=self.bodi, full_name="Legacy Orphan", gender="male", family=None)
        with self.assertRaises(ValidationError):
            member_services.transfer_ledger(member=orphan, ledger="town_elders", actor=self.tro)

    def test_a_family_officer_cannot_transfer_ledgers_and_an_issued_bill_is_untouched(self):
        head = User.objects.create_user(username="lt_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        m = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        member_services.link_member_to_user(member=head.member_profile if hasattr(head, "member_profile") and head.member_profile else m, user=head, actor=self.admin)
        target = member_services.register_member(community=self.bodi, full_name="Target", gender="male", family=self.asona, registered_by=self.tro)
        before = self._funeral("Before", "2026-09-02").obligations.get(member=target)
        with self.assertRaises(ValidationError):
            member_services.transfer_ledger(member=target, ledger="town_elders", actor=head)
        member_services.transfer_ledger(member=target, ledger="town_elders", actor=self.tro)
        before.refresh_from_db()
        self.assertEqual(before.rate_type, "own_family")   # the bill already issued stays on the ledger it was raised on

    def test_transfer_endpoint(self):
        m = member_services.register_member(community=self.bodi, full_name="Api Move", gender="male", family=self.asona, registered_by=self.tro)
        c = APIClient(); c.force_authenticate(self.tro)
        res = c.post(f"/api/members/{m.id}/transfer-ledger/", {"ledger": "town_elders", "title": "linguist", "reason": "Appointed"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["contribution_ledger"], "town_elders")
        m.refresh_from_db()
        prof = member_services.member_profile(member=m, actor=self.tro)
        self.assertEqual(prof["member"]["contribution_ledger"], "town_elders")
        self.assertEqual(len(prof["ledger_history"]), 1)
        self.assertEqual(c.post(f"/api/members/{m.id}/transfer-ledger/", {"ledger": "family"}, format="json").status_code, 200)

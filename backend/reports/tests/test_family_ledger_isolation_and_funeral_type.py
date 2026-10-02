from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import AsupedeObligation, ContributionObligation, FuneralEvent
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community


class FamilyLedgerAndFuneralTypeTests(TestCase):
    """
    'Each family should have their own ledger — the family secretary, head, collector and treasurer can view its
    details; after each funeral the details of the ledger should be seen; each family isolated, and the community
    ledger isolated from other communities. When opening a funeral the system should ask the type: Asupedeɛ or
    funeral contributions.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fli-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.other = Community.objects.create(name="Other Town", slug="fli-other", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="fli_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_admin = User.objects.create_user(username="fli_other_admin", password="x", community=self.other, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.other_fam = family_services.create_family(community=self.other, name="Oyoko", actor=self.other_admin)
        for fam, actor in ((self.asona, self.admin), (self.bretuo, self.admin), (self.other_fam, self.other_admin)):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=actor)
            family_services.approve_family_rate(family=fam, actor=actor)
        self.asona_m = member_services.register_member(community=self.bodi, full_name="Asona One", gender="male", family=self.asona, phone="0244000001")
        self.bretuo_m = member_services.register_member(community=self.bodi, full_name="Bretuo One", gender="male", family=self.bretuo)
        self.funeral = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Opanin", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)
        self.collector = User.objects.create_user(username="fli_col", password="x", community=self.bodi, role=Role.COLLECTOR)
        funeral_services.record_payment(obligation=self.funeral.obligations.get(member=self.asona_m), amount=Decimal("2"), method="cash", collector=self.collector, collector_name="C")

    def _officer(self, username, role, family, nomination=None):
        user = User.objects.create_user(username=username, password="x", community=family.community, role=role)
        m = member_services.register_member(community=family.community, full_name=username, gender="male", family=family)
        member_services.link_member_to_user(member=m, user=user, actor=self.admin if family.community_id == self.bodi.id else self.other_admin)
        if nomination:
            CollectorNomination.objects.create(community=family.community, member=m, collector_type=nomination, scoped_family=family, status=CollectorNomination.Status.APPROVED)
        c = APIClient(); c.force_authenticate(user); return c

    # ---- every family officer and the family collector read the family's ledger, in detail ----
    def test_head_secretary_treasurer_and_collector_all_read_the_familys_ledger_with_per_funeral_detail(self):
        for username, role, nom in (("fli_head", Role.FAMILY_HEAD, None), ("fli_sec", Role.FAMILY_SECRETARY, None), ("fli_tre", Role.FAMILY_TREASURER, None), ("fli_fcol", Role.COLLECTOR, "family")):
            c = self._officer(username, role, self.asona, nom)
            ledger = c.get("/api/reports/family-ledger/").data
            self.assertEqual(ledger["family_name"], "Asona", username)
            self.assertEqual([f["deceased_name"] for f in ledger["funerals"]], ["Opanin"])
            self.assertEqual(ledger["funerals"][0]["funeral_type"], "contributions")
            detail = c.get(f"/api/reports/family-ledger/funerals/{self.funeral.id}/").data
            names = {m["member_name"] for m in detail["members"]}
            self.assertIn("Asona One", names)
            self.assertNotIn("Bretuo One", names)                                   # another family's member is not in Asona's ledger
            row = next(m for m in detail["members"] if m["member_name"] == "Asona One")
            self.assertEqual((row["amount_paid"], row["balance"]), ("2.00", "3.00"))
            self.assertEqual(row["payments"][0]["collected_by"], "fli_col")          # payment by payment, with who took it

    # ---- isolation: family from family, community from community ----
    def test_a_family_cannot_read_another_familys_ledger_or_funeral_detail(self):
        bretuo_head = self._officer("fli_b_head", Role.FAMILY_HEAD, self.bretuo)
        self.assertEqual(bretuo_head.get(f"/api/reports/family-ledger/?family={self.asona.id}").data["family_name"], "Bretuo")   # asking changes nothing
        detail = bretuo_head.get(f"/api/reports/family-ledger/funerals/{self.funeral.id}/").data
        self.assertEqual(detail["family_name"], "Bretuo")
        self.assertNotIn("Asona One", {m["member_name"] for m in detail["members"]})

    def test_a_community_cannot_read_another_communitys_ledgers(self):
        c = APIClient(); c.force_authenticate(self.other_admin)
        self.assertEqual(c.get(f"/api/reports/family-ledger/?family={self.asona.id}").status_code, 404)              # Asona is not in Other Town
        self.assertEqual(c.get(f"/api/reports/family-ledger/funerals/{self.funeral.id}/?family={self.other_fam.id}").status_code, 404)   # nor is the funeral
        elders = c.get("/api/reports/town-elders-ledger/").data
        self.assertNotIn("Asona One", str(elders))
        their_own = c.get(f"/api/reports/family-ledger/?family={self.other_fam.id}").data
        self.assertEqual((their_own["family_name"], their_own["funerals"]), ("Oyoko", []))
        other_officer = self._officer("fli_other_head", Role.FAMILY_HEAD, self.other_fam)
        self.assertEqual(other_officer.get(f"/api/reports/family-ledger/funerals/{self.funeral.id}/").status_code, 404)

    # ---- the type of funeral ----
    def test_an_asupede_funeral_bills_only_the_asupede_levy_and_a_contributions_funeral_bills_the_ledger(self):
        asupede = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Asupedeɛ One", deceased_gender="female", deceased_family=self.asona, date_of_death="2026-09-10", collection_start_date="2026-09-11", actor=self.admin, funeral_type="asupede", asupede_amount=Decimal("20"))
        self.assertEqual(asupede.funeral_type, "asupede")
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=asupede).count(), 0)       # nobody gets an ordinary bill
        self.assertGreater(AsupedeObligation.objects.filter(funeral_event=asupede).count(), 0)         # everyone gets the levy
        self.assertEqual(AsupedeObligation.objects.filter(funeral_event=asupede).first().expected_amount, Decimal("20"))
        self.assertEqual(self.funeral.funeral_type, "contributions")
        self.assertGreater(ContributionObligation.objects.filter(funeral_event=self.funeral).count(), 0)
        with self.assertRaises(ValidationError):                                                      # Asupedeɛ needs its amount
            funeral_services.create_funeral_event(community=self.bodi, deceased_name="No Amount", deceased_gender="male", deceased_family=self.asona, date_of_death="2026-09-12", collection_start_date="2026-09-13", actor=self.admin, funeral_type="asupede")

    def test_a_family_opened_asupede_funeral_bills_the_levy_only_once_approved(self):
        head_user = User.objects.create_user(username="fli_open_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        hm = member_services.register_member(community=self.bodi, full_name="Opening Head", gender="male", family=self.asona)
        member_services.link_member_to_user(member=hm, user=head_user, actor=self.admin)
        funeral = funeral_services.request_funeral_event(community=self.bodi, deceased_name="Family Opened", deceased_gender="male", deceased_family=self.asona, date_of_death="2026-09-15", collection_start_date="2026-09-16", actor=head_user, funeral_type="asupede", asupede_amount=Decimal("15"))
        self.assertEqual((funeral.status, funeral.funeral_type), (FuneralEvent.Status.PENDING_APPROVAL, "asupede"))
        self.assertEqual(AsupedeObligation.objects.filter(funeral_event=funeral).count(), 0)           # nothing billed before approval
        chair = User.objects.create_user(username="fli_chair", password="x", community=self.bodi, role=Role.CHAIRMAN)
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.admin)
        funeral_services.approve_funeral_opening(funeral=funeral, approver=chair)
        funeral.refresh_from_db()
        self.assertEqual(funeral.status, FuneralEvent.Status.ACTIVE)
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=funeral).count(), 0)
        self.assertGreater(AsupedeObligation.objects.filter(funeral_event=funeral).count(), 0)
        detail = self._officer("fli_detail_sec", Role.FAMILY_SECRETARY, self.asona).get(f"/api/reports/family-ledger/funerals/{funeral.id}/").data
        self.assertEqual(detail["funeral"]["funeral_type"], "asupede")
        self.assertGreater(len(detail["asupede"]), 0)                                                  # the levy is shown in the family's ledger

    def test_the_api_asks_for_the_type_and_defaults_to_contributions(self):
        c = APIClient(); c.force_authenticate(self.admin)
        res = c.post("/api/funerals/", {"deceased_name": "Api One", "deceased_gender": "male", "deceased_family_id": str(self.asona.id), "cause_of_death": "illness", "date_of_death": "2026-09-20", "collection_start_date": "2026-09-21", "funeral_type": "asupede", "asupede_amount": "10"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["funeral_type"], "asupede")
        res = c.post("/api/funerals/", {"deceased_name": "Api Two", "deceased_gender": "male", "deceased_family_id": str(self.asona.id), "cause_of_death": "illness", "date_of_death": "2026-09-22", "collection_start_date": "2026-09-23"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["funeral_type"], "contributions")

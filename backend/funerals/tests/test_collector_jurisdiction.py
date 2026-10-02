"""
"Each collector should receive or collect in his jurisdiction only." One
collector per level, and every money path they can and cannot touch.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.jurisdiction import can_record_contribution, can_record_gift, collector_grants
from funerals.models import AsupedeObligation
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community


class CollectorJurisdictionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="cj-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"))
        cls.admin = User.objects.create_user(username="cj_admin", password="x", community=cls.bodi, role=Role.COMMUNITY_ADMIN)
        cls.asona = family_services.create_family(community=cls.bodi, name="Asona", actor=cls.admin)
        cls.bretuo = family_services.create_family(community=cls.bodi, name="Bretuo", actor=cls.admin)
        for fam in (cls.asona, cls.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=cls.admin)
            family_services.approve_family_rate(family=fam, actor=cls.admin)
        cls.asona_member = member_services.register_member(community=cls.bodi, full_name="Asona Payer", gender="male", family=cls.asona)
        cls.bretuo_member = member_services.register_member(community=cls.bodi, full_name="Bretuo Payer", gender="male", family=cls.bretuo)
        cls.elder = member_services.register_member(community=cls.bodi, full_name="Nana Elder", gender="male", family=cls.bretuo, is_town_leader=True)

        def collector(username, nomination_type=None, family=None):
            user = User.objects.create_user(username=username, password="x", community=cls.bodi, role=Role.COLLECTOR)
            member = member_services.register_member(community=cls.bodi, full_name=username, gender="male", family=family or cls.asona)
            member_services.link_member_to_user(member=member, user=user, actor=cls.admin)
            if nomination_type:
                CollectorNomination.objects.create(community=cls.bodi, member=member, collector_type=nomination_type, scoped_family=family, nominated_by=cls.admin, status=CollectorNomination.Status.APPROVED)
            return user

        cls.general = collector("cj_general", "general")
        cls.asona_collector = collector("cj_asona_collector", "family", cls.asona)
        cls.elders_collector = collector("cj_elders_collector", "town_elder")
        cls.gift_collector = User.objects.create_user(username="cj_gift", password="x", community=cls.bodi, role=Role.GIFT_COLLECTOR)

        cls.funeral = funeral_services.create_funeral_event(community=cls.bodi, deceased_name="Deceased", deceased_gender="male", deceased_family=cls.asona, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=cls.admin)
        funeral_services.activate_asupede(funeral=cls.funeral, amount=Decimal("10"), actor=cls.admin)
        cls.ob_asona = cls.funeral.obligations.get(member=cls.asona_member)
        cls.ob_bretuo = cls.funeral.obligations.get(member=cls.bretuo_member)
        cls.ob_elder = cls.funeral.obligations.get(member=cls.elder)

    def test_the_grants_table_reads_as_designed(self):
        self.assertIn(("contributions", ("community", None)), collector_grants(self.general))
        self.assertIn(("contributions", ("family", self.asona.id)), collector_grants(self.asona_collector))
        self.assertIn(("contributions", ("town_elders", None)), collector_grants(self.elders_collector))
        self.assertTrue(any(kind == "gifts" for kind, _ in collector_grants(self.gift_collector)))

    def test_a_family_collector_reaches_only_their_own_familys_members(self):
        self.assertTrue(can_record_contribution(self.asona_collector, self.ob_asona))
        self.assertFalse(can_record_contribution(self.asona_collector, self.ob_bretuo))

    def test_the_community_collector_reaches_every_member(self):
        self.assertTrue(can_record_contribution(self.general, self.ob_asona))
        self.assertTrue(can_record_contribution(self.general, self.ob_bretuo))

    def test_a_town_elders_collector_reaches_elders_only(self):
        self.assertTrue(can_record_contribution(self.elders_collector, self.ob_elder))
        self.assertFalse(can_record_contribution(self.elders_collector, self.ob_asona))

    def test_a_gift_collector_takes_gifts_but_never_contributions(self):
        self.assertTrue(can_record_gift(self.gift_collector, self.funeral))
        self.assertFalse(can_record_contribution(self.gift_collector, self.ob_asona))
        self.assertFalse(can_record_gift(self.general, self.funeral))

    def test_asupede_follows_the_same_family_boundary_over_http(self):
        """The path closed this turn: Asupedeɛ used the old blanket collector check and ignored jurisdiction."""
        a_asona = AsupedeObligation.objects.get(funeral_event=self.funeral, member=self.asona_member)
        a_bretuo = AsupedeObligation.objects.get(funeral_event=self.funeral, member=self.bretuo_member)
        c = APIClient(); c.force_authenticate(self.asona_collector)
        body = {"amount": "1", "method": "cash", "collector_name": "A"}
        self.assertEqual(c.post(f"/api/funerals/{self.funeral.id}/asupede-obligations/{a_asona.id}/record-payment/", body).status_code, 201)
        self.assertEqual(c.post(f"/api/funerals/{self.funeral.id}/asupede-obligations/{a_bretuo.id}/record-payment/", body).status_code, 403)
        g = APIClient(); g.force_authenticate(self.general)
        self.assertEqual(g.post(f"/api/funerals/{self.funeral.id}/asupede-obligations/{a_bretuo.id}/record-payment/", body).status_code, 201)

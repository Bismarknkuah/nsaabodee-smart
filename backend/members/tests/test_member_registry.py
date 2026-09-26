from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class MemberRegistryTests(TestCase):
    """'His major role is to have access of the members data... each user role plays its role, not other users' role.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="reg-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="reg_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)
        self.a1 = member_services.register_member(community=self.bodi, full_name="Asona One", gender="male", family=self.asona, date_of_birth=date(1998, 1, 1))
        self.a2 = member_services.register_member(community=self.bodi, full_name="Asona Two", gender="female", family=self.asona, date_of_birth=date(1960, 1, 1))
        self.b1 = member_services.register_member(community=self.bodi, full_name="Bretuo One", gender="male", family=self.bretuo)

        self.desk = User.objects.create_user(username="reg_desk", password="x", community=self.bodi, role=Role.COMMUNITY_REGISTRATION_DESK)
        self.tro = User.objects.create_user(username="reg_tro", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        self.family_officer = User.objects.create_user(username="reg_fro", password="x", community=self.bodi, role=Role.FAMILY_REGISTRATION_OFFICER)
        member_services.link_member_to_user(member=self.a1, user=self.family_officer, actor=self.admin)

    def test_community_registrars_see_the_whole_community_with_gender_age_and_family_breakdowns(self):
        for actor in (self.desk, self.tro):
            a = member_services.member_registry_analytics(actor=actor)
            self.assertEqual(a["scope"], "community")
            self.assertEqual(a["total"], 3)
            self.assertEqual(a["by_gender"], {"male": 2, "female": 1})
            self.assertEqual(a["by_age_band"]["18_35"], 1)
            self.assertEqual(a["by_age_band"]["over_65"], 1)
            self.assertEqual(a["by_age_band"]["unknown"], 1)
            self.assertEqual({r["family_name"]: r["total"] for r in a["by_family"]}, {"Asona": 2, "Bretuo": 1})

    def test_a_family_registration_officer_sees_only_their_own_family(self):
        a = member_services.member_registry_analytics(actor=self.family_officer)
        self.assertEqual(a["scope"], "family")
        self.assertEqual(a["total"], 2)
        self.assertEqual([r["family_name"] for r in a["by_family"]], ["Asona"])

    def test_a_plain_member_has_no_registry(self):
        member_user = User.objects.create_user(username="reg_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            member_services.member_registry_analytics(actor=member_user)

    def test_profile_shows_family_every_obligation_and_total_owed(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Deceased", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01", actor=self.admin,
        )
        obligation = funeral.obligations.get(member=self.a1)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("2"), method="cash", collector_name="Desk")
        p = member_services.member_profile(member=self.a1, actor=self.desk)
        self.assertEqual(p["family"]["name"], "Asona")
        self.assertEqual(len(p["obligations"]), 1)
        self.assertEqual(Decimal(p["total_owed"]), obligation.balance)
        self.assertEqual(Decimal(p["paid_all_time"]), Decimal("2"))
        self.assertEqual(p["login"]["username"], "reg_fro")

    def test_a_family_officer_cannot_open_another_familys_member_profile(self):
        with self.assertRaises(ValidationError):
            member_services.member_profile(member=self.b1, actor=self.family_officer)

    def test_a_registrar_can_move_a_member_to_another_family_but_a_family_officer_cannot(self):
        member_services.move_member_to_family(member=self.a2, family=self.bretuo, actor=self.tro)
        self.a2.refresh_from_db()
        self.assertEqual(self.a2.family_id, self.bretuo.id)
        with self.assertRaises(ValidationError):
            member_services.move_member_to_family(member=self.b1, family=self.asona, actor=self.family_officer)

    def test_a_family_head_must_be_replaced_before_being_moved(self):
        family_services.assign_family_head(family=self.asona, member=self.a1, actor=self.admin)
        with self.assertRaises(ValidationError):
            member_services.move_member_to_family(member=self.a1, family=self.bretuo, actor=self.desk)

    def test_deactivate_is_a_soft_delete_that_also_suspends_the_login(self):
        member_services.deactivate_member(member=self.a1, actor=self.desk, reason="Relocated")
        self.a1.refresh_from_db(); self.family_officer.refresh_from_db()
        self.assertEqual(self.a1.status, Member.Status.INACTIVE)
        self.assertFalse(self.family_officer.is_active)
        self.assertTrue(Member.objects.filter(id=self.a1.id).exists())
        member_services.reactivate_member(member=self.a1, actor=self.desk)
        self.a1.refresh_from_db(); self.family_officer.refresh_from_db()
        self.assertEqual(self.a1.status, Member.Status.ACTIVE)
        self.assertTrue(self.family_officer.is_active)

    def test_endpoints_are_wired(self):
        client = APIClient(); client.force_authenticate(self.desk)
        self.assertEqual(client.get("/api/members/registry-analytics/").status_code, 200)
        self.assertEqual(client.get(f"/api/members/{self.a1.id}/profile/").status_code, 200)
        r = client.post(f"/api/members/{self.b1.id}/move-family/", {"family_id": str(self.asona.id)})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(client.post(f"/api/members/{self.b1.id}/deactivate/", {"reason": "test"}).status_code, 200)
        fro = APIClient(); fro.force_authenticate(self.family_officer)
        self.assertEqual(fro.post(f"/api/members/{self.b1.id}/deactivate/").status_code, 403)

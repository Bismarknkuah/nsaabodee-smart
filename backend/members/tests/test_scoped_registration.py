from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class DuplicatePreventionTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_exact_name_and_phone_match_is_blocked(self):
        member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", phone="0244000000")
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", phone="0244000000")

    def test_case_insensitive_name_match_still_blocked(self):
        member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", phone="0244000000")
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="KOJO MENSAH", gender="male", phone="0244000000")

    def test_same_name_different_phone_is_allowed(self):
        member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", phone="0244000000")
        # Two genuinely different people can share a common name.
        member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", phone="0201111111")
        self.assertIsNotNone(member.id)

    def test_force_flag_overrides_the_block(self):
        member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", phone="0244000000")
        member = member_services.register_member(
            community=self.bodi, full_name="Kojo Mensah", gender="male", phone="0244000000",
            force_despite_duplicate=True,
        )
        self.assertIsNotNone(member.id)

    def test_no_phone_provided_never_blocks(self):
        member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male")
        member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male")
        self.assertIsNotNone(member.id)


class FamilyHeadScopedRegistrationTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_family_head_registers_into_own_family_by_default(self):
        client = self._login("abusuapanin")
        res = client.post("/api/members/", {"full_name": "New Asona Member", "gender": "male"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(str(res.data["family"]), str(self.asona.id))

    def test_family_head_cannot_register_into_another_family(self):
        client = self._login("abusuapanin")
        res = client.post("/api/members/", {"full_name": "Sneaky Member", "gender": "male", "family_id": str(self.bretuo.id)})
        self.assertEqual(res.status_code, 400)

    def test_chairman_can_register_into_any_family(self):
        client = self._login("chairman")
        res = client.post("/api/members/", {"full_name": "Bretuo Member", "gender": "male", "family_id": str(self.bretuo.id)})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(str(res.data["family"]), str(self.bretuo.id))

    def test_chairman_can_transfer_members_between_families(self):
        member = member_services.register_member(community=self.bodi, full_name="Movable Member", gender="male", family=self.asona)
        client = self._login("chairman")
        res = client.post(
            f"/api/families/{self.bretuo.id}/transfer-members/",
            {"member_ids": [str(member.id)], "target_family_id": str(self.bretuo.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        member.refresh_from_db()
        self.assertEqual(member.family_id, self.bretuo.id)

    def test_ordinary_community_member_cannot_register_anyone(self):
        rando = User.objects.create_user(username="rando", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        client = self._login("rando")
        res = client.post("/api/members/", {"full_name": "Nope", "gender": "male"})
        self.assertEqual(res.status_code, 403)

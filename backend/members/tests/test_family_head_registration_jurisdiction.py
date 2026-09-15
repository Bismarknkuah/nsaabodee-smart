from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class FamilyHeadRegistrationJurisdictionTests(TestCase):
    """'Family head should only [be] allowed to register his family members, not new families.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-head-jurisdiction")
        self.admin = User.objects.create_user(username="head_jur_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="jur_abusuapanin", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

    def test_family_head_can_register_a_member_into_their_own_family(self):
        member = member_services.register_member(
            community=self.bodi, full_name="New Asona Member", gender="male", family=self.asona, registered_by=self.head_user,
        )
        self.assertEqual(member.family_id, self.asona.id)

    def test_family_head_cannot_register_a_member_into_a_different_family(self):
        with self.assertRaises(ValidationError):
            member_services.register_member(
                community=self.bodi, full_name="Sneaky Bretuo Member", gender="male", family=self.bretuo, registered_by=self.head_user,
            )

    def test_family_head_cannot_register_a_member_with_no_family_at_all(self):
        """No family specified means they'd effectively be creating an unassigned member — still not their jurisdiction to decide."""
        with self.assertRaises(ValidationError):
            member_services.register_member(
                community=self.bodi, full_name="No Family Member", gender="male", family=None, registered_by=self.head_user,
            )

    def test_community_admin_is_unaffected_and_can_register_into_any_family(self):
        member = member_services.register_member(
            community=self.bodi, full_name="Any Family Member", gender="male", family=self.bretuo, registered_by=self.admin,
        )
        self.assertEqual(member.family_id, self.bretuo.id)

    def test_end_to_end_http_request_confirms_the_restriction(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "jur_abusuapanin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/members/", {"full_name": "Sneaky HTTP Member", "gender": "male", "family_id": str(self.bretuo.id)})
        self.assertEqual(res.status_code, 400)


class FamilySecretaryRegistrationJurisdictionTests(TestCase):
    """
    'Family Secretary also has registration authority and is equally
    family-scoped, not community-wide' — the same restriction just
    verified for Family Head applies here too, closing a real gap
    where only the Head was covered before.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-secretary-jurisdiction")
        self.admin = User.objects.create_user(username="sec_jur_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Secretary Person", gender="female", family=self.asona)
        self.secretary_user = User.objects.create_user(username="jur_family_secretary", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary_user, actor=self.admin)

    def test_family_secretary_can_register_a_member_into_their_own_family(self):
        member = member_services.register_member(
            community=self.bodi, full_name="New Asona Member", gender="male", family=self.asona, registered_by=self.secretary_user,
        )
        self.assertEqual(member.family_id, self.asona.id)

    def test_family_secretary_cannot_register_a_member_into_a_different_family(self):
        with self.assertRaises(ValidationError):
            member_services.register_member(
                community=self.bodi, full_name="Sneaky Bretuo Member", gender="male", family=self.bretuo, registered_by=self.secretary_user,
            )

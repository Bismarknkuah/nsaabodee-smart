from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from accounts.models import Role, User
from families import services
from families.models import Family
from tenants.models import Community


class RegisterFamilyWithHeadTests(TestCase):
    """
    'When a new family is created, the system must require the
    registration of the Family Head as part of the process... The
    Family Head account should be created automatically and linked to
    the newly created family.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-head-reg")
        self.admin = User.objects.create_user(username="head_reg_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_registering_a_family_creates_the_family_the_head_member_and_the_head_login_all_together(self):
        family, head_member, head_user = services.register_family_with_head(
            community=self.bodi, name="Asona", actor=self.admin,
            head_full_name="Kwame Head", head_gender="male",
            head_username="kwame_head", head_password="a-real-password-123",
            head_phone="0244000000", head_email="kwame@example.com", head_ghana_card_number="GHA-000000000-0",
            head_address="Bodi, Ghana", head_occupation="Farmer",
        )
        self.assertEqual(family.name, "Asona")
        self.assertEqual(head_member.full_name, "Kwame Head")
        self.assertEqual(head_member.family_id, family.id)
        self.assertEqual(head_member.email, "kwame@example.com")
        self.assertEqual(head_user.role, Role.FAMILY_HEAD)
        self.assertEqual(head_member.linked_user_id, head_user.id)

        family.refresh_from_db()
        self.assertEqual(family.family_head_id, head_member.id)

    def test_the_new_heads_login_actually_works(self):
        """Not just correctly linked in the database — a genuinely usable login."""
        from rest_framework.test import APIClient
        services.register_family_with_head(
            community=self.bodi, name="Bretuo", actor=self.admin,
            head_full_name="Ama Head", head_gender="female",
            head_username="ama_head", head_password="a-real-password-123",
        )
        client = APIClient()
        res = client.post("/api/auth/login/", {"username": "ama_head", "password": "a-real-password-123"})
        self.assertEqual(res.status_code, 200)

    def test_a_full_profile_is_optional_beyond_the_required_fields(self):
        """Ghana Card, email, address, etc. are all optional — only name, gender, and login credentials are truly required."""
        family, head_member, head_user = services.register_family_with_head(
            community=self.bodi, name="Minimal Family", actor=self.admin,
            head_full_name="Minimal Head", head_gender="male",
            head_username="minimal_head", head_password="a-real-password-123",
        )
        self.assertEqual(head_member.email, "")
        self.assertIsNone(head_member.ghana_card_number)

    def test_registration_is_fully_atomic_a_failed_login_creation_rolls_back_the_whole_family(self):
        """
        The core guarantee: if creating the head's login fails for any
        reason (here, a username that's already taken), NOTHING should
        be left behind — no orphaned family with no head, no orphaned
        member with no login. Real database state is checked after the
        failure, not just that an exception was raised.
        """
        User.objects.create_user(username="already_taken", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

        with self.assertRaises(ValidationError):
            services.register_family_with_head(
                community=self.bodi, name="Should Not Exist", actor=self.admin,
                head_full_name="Someone", head_gender="male",
                head_username="already_taken", head_password="a-real-password-123",
            )

        self.assertFalse(Family.objects.filter(community=self.bodi, name="Should Not Exist").exists())

    def test_create_family_without_a_head_still_works_completely_unchanged(self):
        """Backward compatibility: every existing test and internal flow that creates a family with no head up front must keep working exactly as before."""
        family = services.create_family(community=self.bodi, name="No Head Yet", actor=self.admin)
        self.assertIsNone(family.family_head)

    def test_two_families_cannot_share_the_same_heads_username(self):
        services.register_family_with_head(
            community=self.bodi, name="First Family", actor=self.admin,
            head_full_name="First Head", head_gender="male",
            head_username="shared_username", head_password="a-real-password-123",
        )
        with self.assertRaises(ValidationError):
            services.register_family_with_head(
                community=self.bodi, name="Second Family", actor=self.admin,
                head_full_name="Second Head", head_gender="male",
                head_username="shared_username", head_password="a-real-password-123",
            )


class RegisterFamilyWithHeadHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-head-http")
        self.admin = User.objects.create_user(username="head_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_full_registration_via_http(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "head_http_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post("/api/families/register-with-head/", {
            "name": "Http Family", "head_full_name": "Http Head", "head_gender": "male",
            "head_username": "http_head_user", "head_password": "a-real-password-123",
            "head_email": "httphead@example.com",
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["family"]["name"], "Http Family")
        self.assertEqual(res.data["head_username"], "http_head_user")
        self.assertIsNotNone(res.data["family"]["family_head"])

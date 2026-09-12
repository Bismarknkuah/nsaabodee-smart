from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class RoleAssignmentServiceTests(TestCase):
    """
    'There should be specific roles to select when the community admin
    wants to assign a role or task to someone — [they] should have
    more options as he supervises and manages the community system.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-role-assign")
        self.other_community = Community.objects.create(name="Other Town", slug="other-role-assign")
        self.admin = User.objects.create_user(username="role_assign_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="role_assign_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Some Member", gender="male", family=self.asona)

    def test_community_admin_can_create_a_new_login_and_assign_a_role_to_a_member_with_none(self):
        user = member_services.assign_role_to_member(
            member=self.member, role="collector", actor=self.admin, username="new_collector", password="a-real-password-123",
        )
        self.assertEqual(user.role, "collector")
        self.assertEqual(user.community_id, self.bodi.id)
        self.member.refresh_from_db()
        self.assertEqual(self.member.linked_user_id, user.id)

    def test_community_admin_can_change_the_role_of_a_member_who_already_has_a_login(self):
        existing_user = User.objects.create_user(username="already_has_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=existing_user, actor=self.admin)

        updated_user = member_services.assign_role_to_member(member=self.member, role="treasurer", actor=self.admin)
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.role, "treasurer")
        self.assertEqual(updated_user.id, existing_user.id)

    def test_community_admin_has_many_role_options_available(self):
        """'Should have more options as he supervises and manages the community system.'"""
        from members.services import ASSIGNABLE_COMMUNITY_ROLES
        self.assertGreaterEqual(len(ASSIGNABLE_COMMUNITY_ROLES), 14)
        self.assertIn("chairman", ASSIGNABLE_COMMUNITY_ROLES)
        self.assertIn("traditional_leader", ASSIGNABLE_COMMUNITY_ROLES)
        self.assertIn("family_head", ASSIGNABLE_COMMUNITY_ROLES)

    def test_platform_admin_is_never_an_assignable_role(self):
        """The critical safety boundary — a Community Admin must never be able to grant platform-level access."""
        from members.services import ASSIGNABLE_COMMUNITY_ROLES
        self.assertNotIn("platform_admin", ASSIGNABLE_COMMUNITY_ROLES)
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(
                member=self.member, role="platform_admin", actor=self.admin, username="sneaky", password="a-real-password-123",
            )

    def test_a_chairman_cannot_assign_roles_only_the_community_admin_can(self):
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(
                member=self.member, role="collector", actor=self.chairman, username="x", password="a-real-password-123",
            )

    def test_cannot_assign_a_role_to_a_member_outside_your_own_community(self):
        other_admin = User.objects.create_user(username="other_admin_role", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(
                member=self.member, role="collector", actor=other_admin, username="x", password="a-real-password-123",
            )

    def test_creating_a_login_without_a_username_and_password_fails_clearly(self):
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(member=self.member, role="collector", actor=self.admin)


class RoleAssignmentHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-role-assign-http")
        self.admin = User.objects.create_user(username="role_assign_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="HTTP Member", gender="male", family=self.asona)

    def test_full_role_assignment_flow_via_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "role_assign_http_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post(f"/api/members/{self.member.id}/assign-role/", {
            "role": "collector", "username": "http_new_collector", "password": "a-real-password-123",
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["role"], "collector")

        new_login = client.post("/api/auth/login/", {"username": "http_new_collector", "password": "a-real-password-123"})
        self.assertEqual(new_login.status_code, 200)

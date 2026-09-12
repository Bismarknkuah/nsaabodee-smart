from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import Community


class PlatformAdminCapabilityServiceTests(TestCase):
    """'System settings should provide more option that will restrict or give access to the platform admin based on what they can do.'"""

    def setUp(self):
        self.full_admin = User.objects.create_user(username="cap_full_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.target_admin = User.objects.create_user(username="cap_target_admin", password="x", role=Role.PLATFORM_ADMIN)

    def test_a_capability_absent_from_the_dict_defaults_to_allowed(self):
        """A key never having been set must never silently restrict an existing account the moment this field starts existing."""
        self.assertTrue(self.target_admin.has_platform_admin_capability("manage_communities"))
        self.assertTrue(self.target_admin.has_platform_admin_capability("manage_platform_admins"))

    def test_explicitly_restricting_a_capability_works(self):
        services.update_platform_admin_capabilities(
            target=self.target_admin, capabilities={"manage_communities": False}, actor=self.full_admin,
        )
        self.target_admin.refresh_from_db()
        self.assertFalse(self.target_admin.has_platform_admin_capability("manage_communities"))
        # An untouched capability stays permissive.
        self.assertTrue(self.target_admin.has_platform_admin_capability("manage_feature_flags"))

    def test_a_platform_admin_cannot_modify_their_own_capabilities(self):
        """The core safety rule — without this, restricting your own manage_platform_admins by mistake would be a genuine, permanent lockout."""
        with self.assertRaises(ValidationError):
            services.update_platform_admin_capabilities(
                target=self.full_admin, capabilities={"manage_communities": False}, actor=self.full_admin,
            )

    def test_only_a_platform_admin_with_the_manage_platform_admins_capability_can_restrict_others(self):
        restricted_admin = User.objects.create_user(username="cap_restricted_admin", password="x", role=Role.PLATFORM_ADMIN)
        services.update_platform_admin_capabilities(
            target=restricted_admin, capabilities={"manage_platform_admins": False}, actor=self.full_admin,
        )
        restricted_admin.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.update_platform_admin_capabilities(
                target=self.target_admin, capabilities={"manage_communities": False}, actor=restricted_admin,
            )

    def test_an_unrecognized_capability_key_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.update_platform_admin_capabilities(
                target=self.target_admin, capabilities={"not_a_real_capability": False}, actor=self.full_admin,
            )

    def test_cannot_set_capabilities_on_a_non_platform_admin_account(self):
        community = Community.objects.create(name="Cap Test Community", slug="cap-test-community")
        community_admin = User.objects.create_user(username="cap_community_admin", password="x", community=community, role=Role.COMMUNITY_ADMIN)
        with self.assertRaises(ValidationError):
            services.update_platform_admin_capabilities(
                target=community_admin, capabilities={"manage_communities": False}, actor=self.full_admin,
            )

    def test_a_restricted_capability_actually_blocks_the_real_action(self):
        """Not just a flag that exists — it has to actually stop the action it names."""
        services.update_platform_admin_capabilities(
            target=self.target_admin, capabilities={"manage_platform_admins": False}, actor=self.full_admin,
        )
        self.target_admin.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.add_platform_admin(username="should_fail", password="a-real-password-123", actor=self.target_admin)

    def test_a_superuser_always_has_every_capability_regardless_of_the_stored_dict(self):
        superuser = User.objects.create_superuser(username="cap_superuser", password="x")
        self.assertTrue(superuser.has_platform_admin_capability("manage_communities"))
        self.assertTrue(superuser.has_platform_admin_capability("anything_not_even_real"))


class PlatformAdminCapabilitiesHttpTests(TestCase):
    def setUp(self):
        self.full_admin = User.objects.create_user(username="cap_http_full", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.target_admin = User.objects.create_user(username="cap_http_target", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_get_lists_every_admin_with_their_capabilities(self):
        client = self._login("cap_http_full")
        res = client.get("/api/tenants/platform-admins/capabilities/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("capability_definitions", res.data)
        usernames = [a["username"] for a in res.data["admins"]]
        self.assertIn("cap_http_full", usernames)
        self.assertIn("cap_http_target", usernames)

    def test_full_http_patch_restricts_another_admin(self):
        client = self._login("cap_http_full")
        res = client.patch(
            "/api/tenants/platform-admins/capabilities/",
            {"target_id": str(self.target_admin.id), "capabilities": {"manage_communities": False}},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.target_admin.refresh_from_db()
        self.assertFalse(self.target_admin.has_platform_admin_capability("manage_communities"))

    def test_full_http_patch_on_self_is_rejected(self):
        client = self._login("cap_http_full")
        res = client.patch(
            "/api/tenants/platform-admins/capabilities/",
            {"target_id": str(self.full_admin.id), "capabilities": {"manage_communities": False}},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_a_community_admin_cannot_reach_this_endpoint_at_all(self):
        community = Community.objects.create(name="Cap HTTP Community", slug="cap-http-community")
        User.objects.create_user(username="cap_http_community_admin", password="a-real-password-123", community=community, role=Role.COMMUNITY_ADMIN)
        client = self._login("cap_http_community_admin")
        res = client.get("/api/tenants/platform-admins/capabilities/")
        self.assertEqual(res.status_code, 403)

    def test_restricted_manage_communities_capability_actually_blocks_community_creation_over_http(self):
        """The end-to-end guarantee: a restriction set via this endpoint genuinely blocks the real action, not just a flag nobody checks."""
        services.update_platform_admin_capabilities(
            target=self.target_admin, capabilities={"manage_communities": False}, actor=self.full_admin,
        )
        client = self._login("cap_http_target")
        res = client.post("/api/tenants/communities/", {
            "name": "Should Not Be Created", "slug": "should-not-be-created",
            "admin_username": "blocked_admin", "admin_password": "a-real-password-123",
        }, format="json")
        self.assertEqual(res.status_code, 403)


class AllCommunityAdminsViewTests(TestCase):
    """'They can manage the platform admins on the community admins.'"""

    def setUp(self):
        self.admin = User.objects.create_user(username="acav_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.community_a = Community.objects.create(name="Community A", slug="acav-community-a")
        self.community_b = Community.objects.create(name="Community B", slug="acav-community-b")
        User.objects.create_user(username="acav_admin_a", password="x", community=self.community_a, role=Role.COMMUNITY_ADMIN)
        User.objects.create_user(username="acav_admin_b", password="x", community=self.community_b, role=Role.COMMUNITY_ADMIN)

    def test_lists_every_community_admin_across_every_community_in_one_call(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "acav_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/tenants/community-admins/all/")
        self.assertEqual(res.status_code, 200)
        usernames = [a["username"] for a in res.data]
        self.assertIn("acav_admin_a", usernames)
        self.assertIn("acav_admin_b", usernames)

    def test_restricting_manage_community_admins_blocks_this_endpoint(self):
        restricted = User.objects.create_user(username="acav_restricted", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        services.update_platform_admin_capabilities(target=restricted, capabilities={"manage_community_admins": False}, actor=self.admin)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "acav_restricted", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/tenants/community-admins/all/")
        self.assertEqual(res.status_code, 403)

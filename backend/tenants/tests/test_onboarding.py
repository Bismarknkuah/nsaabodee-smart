from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants.models import Community
from tenants import services


class CommunityOnboardingServiceTests(TestCase):
    def test_onboarding_creates_a_real_community_and_admin_together(self):
        community, admin = services.onboard_new_community(
            community_name="Sefwi Asawinso", admin_username="asawinso_admin", admin_password="a-real-password-123",
        )
        self.assertTrue(Community.objects.filter(id=community.id).exists())
        self.assertEqual(admin.community_id, community.id)
        self.assertEqual(admin.role, Role.COMMUNITY_ADMIN)
        self.assertTrue(admin.check_password("a-real-password-123"))

    def test_two_communities_with_the_same_name_get_disambiguated_slugs_not_rejected(self):
        first, _ = services.onboard_new_community(community_name="Bodi", admin_username="bodi_admin_1", admin_password="a-real-password-123")
        second, _ = services.onboard_new_community(community_name="Bodi", admin_username="bodi_admin_2", admin_password="a-real-password-123")
        self.assertNotEqual(first.slug, second.slug)

    def test_duplicate_username_is_rejected_before_any_community_is_created(self):
        from django.core.exceptions import ValidationError
        User.objects.create_user(username="taken", password="x")
        with self.assertRaises(ValidationError):
            services.onboard_new_community(community_name="New Town", admin_username="taken", admin_password="a-real-password-123")
        self.assertFalse(Community.objects.filter(name="New Town").exists())

    def test_a_new_communitys_data_starts_completely_empty_and_isolated(self):
        community, _ = services.onboard_new_community(
            community_name="Isolated Town", admin_username="isolated_admin", admin_password="a-real-password-123",
        )
        from families.models import Family
        from members.models import Member
        self.assertEqual(Family.objects.filter(community=community).count(), 0)
        self.assertEqual(Member.objects.filter(community=community).count(), 0)


class PlatformAdminConsoleHttpTests(TestCase):
    """
    'I think it's the super admin who should add, edit, or remove a
    community.' Every one of these actions requires platform-admin
    authentication now — no public signup endpoint exists anymore.
    """

    def setUp(self):
        self.super_admin = User.objects.create_superuser(username="root", password="a-real-password-123")
        self.regular_community_admin = User.objects.create_user(
            username="just_a_community_admin", password="x",
            community=Community.objects.create(name="Existing Town", slug="existing-town"),
            role=Role.COMMUNITY_ADMIN,
        )

    def _login(self, username, password="a-real-password-123"):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": password})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_super_admin_can_create_a_community(self):
        client = self._login("root")
        res = client.post("/api/tenants/communities/", {
            "community_name": "New Kumasi Chapter", "admin_username": "new_kumasi_admin", "admin_password": "a-real-password-123",
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["community"]["name"], "New Kumasi Chapter")
        self.assertEqual(res.data["admin"]["username"], "new_kumasi_admin")

    def test_an_ordinary_community_admin_cannot_create_a_new_community(self):
        client = self._login("just_a_community_admin", password="x")
        res = client.post("/api/tenants/communities/", {
            "community_name": "Shouldnt Work", "admin_username": "shouldnt_work_admin", "admin_password": "a-real-password-123",
        })
        self.assertEqual(res.status_code, 403)

    def test_an_unauthenticated_request_cannot_create_a_community_either(self):
        client = APIClient()
        res = client.post("/api/tenants/communities/", {
            "community_name": "No Auth Town", "admin_username": "noauth_admin", "admin_password": "a-real-password-123",
        })
        self.assertEqual(res.status_code, 401)

    def test_super_admin_can_edit_a_communitys_rates(self):
        community = Community.objects.create(name="Rate Town", slug="rate-town")
        client = self._login("root")
        res = client.patch(f"/api/tenants/communities/{community.id}/", {"default_general_male_amount": "10"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["default_general_male_amount"], "10.00")

    def test_ordinary_community_admin_cannot_edit_any_community(self):
        community = Community.objects.create(name="Rate Town 2", slug="rate-town-2")
        client = self._login("just_a_community_admin", password="x")
        res = client.patch(f"/api/tenants/communities/{community.id}/", {"default_general_male_amount": "10"})
        self.assertEqual(res.status_code, 403)

    def test_deactivating_a_community_hides_it_but_keeps_its_data(self):
        community, _ = services.onboard_new_community(
            community_name="To Be Deactivated", admin_username="tbd_admin", admin_password="a-real-password-123",
        )
        client = self._login("root")
        res = client.post(f"/api/tenants/communities/{community.id}/deactivate/")
        self.assertEqual(res.status_code, 200)
        community.refresh_from_db()
        self.assertFalse(community.is_active)
        res2 = client.post(f"/api/tenants/communities/{community.id}/reactivate/")
        self.assertEqual(res2.status_code, 200)
        community.refresh_from_db()
        self.assertTrue(community.is_active)

    def test_deleting_a_community_with_real_data_is_refused(self):
        from families import services as family_services
        community, admin = services.onboard_new_community(
            community_name="Has Real Data", admin_username="hasrealdata_admin", admin_password="a-real-password-123",
        )
        family_services.create_family(community=community, name="Some Family", actor=admin)

        client = self._login("root")
        res = client.delete(f"/api/tenants/communities/{community.id}/")
        self.assertEqual(res.status_code, 409)
        self.assertTrue(Community.objects.filter(id=community.id).exists())

    def test_deleting_a_genuinely_empty_community_succeeds(self):
        community, _ = services.onboard_new_community(
            community_name="Truly Empty", admin_username="trulyempty_admin", admin_password="a-real-password-123",
        )
        client = self._login("root")
        res = client.delete(f"/api/tenants/communities/{community.id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Community.objects.filter(id=community.id).exists())

    def test_super_admin_can_add_an_additional_community_admin(self):
        community, _ = services.onboard_new_community(
            community_name="Needs Another Admin", admin_username="original_admin", admin_password="a-real-password-123",
        )
        client = self._login("root")
        res = client.post(f"/api/tenants/communities/{community.id}/admins/", {
            "username": "second_admin", "password": "a-real-password-123",
        })
        self.assertEqual(res.status_code, 201)

        list_res = client.get(f"/api/tenants/communities/{community.id}/admins/")
        usernames = {a["username"] for a in list_res.data}
        self.assertEqual(usernames, {"original_admin", "second_admin"})

    def test_the_new_communitys_own_admin_still_manages_their_own_community_normally(self):
        community, admin = services.onboard_new_community(
            community_name="Self Managed Town", admin_username="self_managed_admin", admin_password="a-real-password-123",
        )
        client = self._login("self_managed_admin")
        res = client.post("/api/families/", {"name": "A Real Family"})
        self.assertEqual(res.status_code, 201)

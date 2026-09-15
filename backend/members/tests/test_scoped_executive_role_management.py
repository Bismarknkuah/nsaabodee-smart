from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class FamilyHeadRoleAssignmentTests(TestCase):
    """'Each family head should be able to add new family executive role... the arrears collector should be available to each of the family head to assign to someone.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fhra-bodi")
        self.admin = User.objects.create_user(username="fhra_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.family_head_user = User.objects.create_user(username="fhra_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        member_services.link_member_to_user(member=head_member, user=self.family_head_user, actor=self.admin)

        self.asona_member = member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)

    def test_a_family_head_can_assign_family_arrears_officer_to_their_own_member(self):
        user = member_services.assign_role_to_member(
            member=self.asona_member, role="family_arrears_officer", actor=self.family_head_user,
            username="asona_arrears_officer", password="a-real-password-123",
        )
        self.assertEqual(user.role, "family_arrears_officer")

    def test_a_family_head_can_assign_family_registration_officer(self):
        user = member_services.assign_role_to_member(
            member=self.asona_member, role="family_registration_officer", actor=self.family_head_user,
            username="asona_reg_officer", password="a-real-password-123",
        )
        self.assertEqual(user.role, "family_registration_officer")

    def test_a_family_head_cannot_assign_a_role_to_a_different_familys_member(self):
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(
                member=self.bretuo_member, role="family_arrears_officer", actor=self.family_head_user,
                username="bretuo_arrears_officer", password="a-real-password-123",
            )

    def test_a_family_head_cannot_assign_a_community_wide_role(self):
        """Family Head's authority stops at the family-scoped roles — chairman, treasurer (community-wide), etc. stay out of reach."""
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(
                member=self.asona_member, role="chairman", actor=self.family_head_user,
                username="asona_chairman", password="a-real-password-123",
            )

    def test_assign_role_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "fhra_head", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/members/{self.asona_member.id}/assign-role/",
            {"role": "family_arrears_officer", "username": "http_arrears_officer", "password": "a-real-password-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["role"], "family_arrears_officer")

    def test_a_family_head_gets_404_assigning_to_a_different_familys_member_over_http(self):
        """404, not 403 — Family Head's own queryset never includes another family's members at all (see search_members' FAMILY_SCOPED_MEMBER_ROLES scoping), so the object genuinely isn't visible to reach a permission check against."""
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "fhra_head", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/members/{self.bretuo_member.id}/assign-role/",
            {"role": "family_arrears_officer", "username": "should_fail", "password": "a-real-password-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)


class TraditionalLeaderRoleAssignmentTests(TestCase):
    """'The town leader should also have these features.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tlra-bodi")
        self.admin = User.objects.create_user(username="tlra_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.chief = User.objects.create_user(username="tlra_chief", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)

        self.elder = member_services.register_member(community=self.bodi, full_name="An Elder", gender="male", family=self.asona, is_town_leader=True)
        self.ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary Member", gender="male", family=self.asona)

    def test_a_traditional_leader_can_assign_town_elders_arrears_officer_to_an_elder(self):
        user = member_services.assign_role_to_member(
            member=self.elder, role="town_elders_arrears_officer", actor=self.chief,
            username="elder_arrears_officer", password="a-real-password-123",
        )
        self.assertEqual(user.role, "town_elders_arrears_officer")

    def test_a_traditional_leader_cannot_assign_a_role_to_an_ordinary_member(self):
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(
                member=self.ordinary_member, role="town_elders_arrears_officer", actor=self.chief,
                username="should_fail", password="a-real-password-123",
            )

    def test_assign_role_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "tlra_chief", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/members/{self.elder.id}/assign-role/",
            {"role": "town_registration_officer", "username": "http_town_reg", "password": "a-real-password-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["role"], "town_registration_officer")

    def test_a_traditional_leader_gets_403_assigning_to_an_ordinary_member_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "tlra_chief", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/members/{self.ordinary_member.id}/assign-role/",
            {"role": "town_elders_arrears_officer", "username": "should_fail", "password": "a-real-password-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)


class CommunityAdminArrearsCollectorAssignmentTests(TestCase):
    """'The community admin should also be able to add or assign the arrears collector role to someone.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="caac-bodi")
        self.admin = User.objects.create_user(username="caac_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Some Member", gender="male", family=self.asona)

    def test_community_admin_can_assign_arrears_collector(self):
        user = member_services.assign_role_to_member(
            member=self.member, role="arrears_collector", actor=self.admin,
            username="new_arrears_collector", password="a-real-password-123",
        )
        self.assertEqual(user.role, "arrears_collector")

    def test_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "caac_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/members/{self.member.id}/assign-role/",
            {"role": "arrears_collector", "username": "http_arrears_collector", "password": "a-real-password-123"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["role"], "arrears_collector")


class SuspendReactivateAccountTests(TestCase):
    """'Suspend, or delete executive role.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="sra-bodi")
        self.admin = User.objects.create_user(username="sra_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.collector_user = User.objects.create_user(username="sra_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        self.member = member_services.register_member(community=self.bodi, full_name="Some Collector", gender="male", family=self.asona)
        member_services.link_member_to_user(member=self.member, user=self.collector_user, actor=self.admin)

    def test_suspending_sets_is_active_false_without_changing_role(self):
        user = member_services.suspend_member_account(member=self.member, actor=self.admin)
        self.assertFalse(user.is_active)
        self.assertEqual(user.role, "collector")

    def test_reactivating_restores_is_active_with_the_same_role(self):
        member_services.suspend_member_account(member=self.member, actor=self.admin)
        user = member_services.reactivate_member_account(member=self.member, actor=self.admin)
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, "collector")

    def test_a_suspended_account_cannot_log_in(self):
        member_services.suspend_member_account(member=self.member, actor=self.admin)
        client = APIClient()
        res = client.post("/api/auth/login/", {"username": "sra_collector", "password": "a-real-password-123"})
        self.assertEqual(res.status_code, 401)

    def test_suspending_an_already_suspended_account_is_rejected_clearly(self):
        member_services.suspend_member_account(member=self.member, actor=self.admin)
        with self.assertRaises(ValidationError):
            member_services.suspend_member_account(member=self.member, actor=self.admin)

    def test_suspend_and_reactivate_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "sra_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        suspend_res = client.post(f"/api/members/{self.member.id}/suspend-account/")
        self.assertEqual(suspend_res.status_code, 200, suspend_res.data)
        self.assertFalse(suspend_res.data["is_active"])

        reactivate_res = client.post(f"/api/members/{self.member.id}/reactivate-account/")
        self.assertEqual(reactivate_res.status_code, 200, reactivate_res.data)
        self.assertTrue(reactivate_res.data["is_active"])

    def test_a_family_head_can_suspend_their_own_familys_executive(self):
        family_head_user = User.objects.create_user(username="sra_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        member_services.link_member_to_user(member=head_member, user=family_head_user, actor=self.admin)

        user = member_services.suspend_member_account(member=self.member, actor=family_head_user)
        self.assertFalse(user.is_active)

    def test_a_family_head_cannot_suspend_a_different_familys_member(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        family_head_user = User.objects.create_user(username="sra_head_2", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        head_member = member_services.register_member(community=self.bodi, full_name="The Other Head", gender="male", family=bretuo)
        member_services.link_member_to_user(member=head_member, user=family_head_user, actor=self.admin)

        with self.assertRaises(ValidationError):
            member_services.suspend_member_account(member=self.member, actor=family_head_user)


class ManageableUsersMemberIdTests(TestCase):
    """
    Verifies the exact end-to-end path the frontend actually depends
    on: GET manageable-users returns each user's linked member_id (not
    just their own user id), since suspend-account/reactivate-account
    are member-scoped endpoints, not user-scoped ones.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="mumi-bodi")
        self.admin = User.objects.create_user(username="mumi_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.collector_user = User.objects.create_user(username="mumi_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.member = member_services.register_member(community=self.bodi, full_name="Some Collector", gender="male", family=self.asona)
        member_services.link_member_to_user(member=self.member, user=self.collector_user, actor=self.admin)

    def test_manageable_users_includes_member_id(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mumi_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/accounts/manageable-users/")
        self.assertEqual(res.status_code, 200)
        entry = next(u for u in res.data["users"] if u["username"] == "mumi_collector")
        self.assertEqual(entry["member_id"], str(self.member.id))
        self.assertTrue(entry["is_active"])

    def test_the_full_lookup_then_suspend_round_trip_actually_works(self):
        """The exact sequence the frontend performs: fetch the list, read member_id off of it, then suspend using that id."""
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mumi_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        list_res = client.get("/api/accounts/manageable-users/")
        member_id = next(u for u in list_res.data["users"] if u["username"] == "mumi_collector")["member_id"]

        suspend_res = client.post(f"/api/members/{member_id}/suspend-account/")
        self.assertEqual(suspend_res.status_code, 200, suspend_res.data)
        self.assertFalse(suspend_res.data["is_active"])

    def test_a_user_with_no_linked_member_has_a_null_member_id_not_a_crash(self):
        User.objects.create_user(username="mumi_unlinked", password="x", community=self.bodi, role=Role.COLLECTOR)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mumi_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/accounts/manageable-users/")
        self.assertEqual(res.status_code, 200)
        entry = next(u for u in res.data["users"] if u["username"] == "mumi_unlinked")
        self.assertIsNone(entry["member_id"])

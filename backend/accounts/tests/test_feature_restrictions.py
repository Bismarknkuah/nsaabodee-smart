from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts import services
from accounts.models import Role, User
from accounts.permissions import can_restrict_features_for
from families import services as family_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class CommunityAdminRestrictionTests(TestCase):
    """
    'The community admin should also have user management and system
    settings where he can manage all the family head, community
    executives, community leader, collectors.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="car-bodi")
        self.other_community = Community.objects.create(name="Other Town", slug="car-other-town")
        self.admin = User.objects.create_user(username="car_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="car_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.collector = User.objects.create_user(username="car_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.other_community_admin = User.objects.create_user(username="car_other_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        self.other_community_treasurer = User.objects.create_user(username="car_other_treasurer", password="x", community=self.other_community, role=Role.TREASURER)

    def test_community_admin_can_restrict_a_treasurer_in_their_own_community(self):
        self.assertTrue(can_restrict_features_for(self.admin, self.treasurer))

    def test_community_admin_can_restrict_a_collector_in_their_own_community(self):
        self.assertTrue(can_restrict_features_for(self.admin, self.collector))

    def test_community_admin_cannot_restrict_an_executive_in_a_different_community(self):
        """The core cross-tenant boundary — this must never leak."""
        self.assertFalse(can_restrict_features_for(self.admin, self.other_community_treasurer))

    def test_community_admin_cannot_restrict_another_community_admin(self):
        peer_admin = User.objects.create_user(username="car_peer_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.assertFalse(can_restrict_features_for(self.admin, peer_admin))

    def test_community_admin_cannot_restrict_themselves(self):
        self.assertFalse(can_restrict_features_for(self.admin, self.admin))

    def test_community_admin_cannot_restrict_a_plain_community_member(self):
        """'They manage only the platform admin, not community member' — the same principle at this tier: executives only, never ordinary members."""
        family = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        member_user = User.objects.create_user(username="car_plain_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        Member.objects.create(community=self.bodi, family=family, full_name="Plain", gender="male", linked_user=member_user)
        self.assertFalse(can_restrict_features_for(self.admin, member_user))

    def test_setting_disabled_features_actually_persists(self):
        services.set_disabled_features(target=self.treasurer, features=["/reports"], actor=self.admin)
        self.treasurer.refresh_from_db()
        self.assertEqual(self.treasurer.disabled_features, ["/reports"])
        self.assertFalse(self.treasurer.has_feature("/reports"))
        self.assertTrue(self.treasurer.has_feature("/payment-reversals"))

    def test_community_admin_can_still_restrict_tasks_unlike_family_head(self):
        """A Community Admin keeps the full restrictable set — the narrower carve-out is specific to Family Head."""
        services.set_disabled_features(target=self.treasurer, features=["/tasks"], actor=self.admin)
        self.treasurer.refresh_from_db()
        self.assertEqual(self.treasurer.disabled_features, ["/tasks"])

    def test_an_unrecognized_feature_key_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.set_disabled_features(target=self.treasurer, features=["/not-a-real-page"], actor=self.admin)

    def test_cross_community_restriction_is_rejected_at_the_service_layer_too(self):
        with self.assertRaises(ValidationError):
            services.set_disabled_features(target=self.other_community_treasurer, features=["/reports"], actor=self.admin)

    def test_list_manageable_users_includes_executives_but_never_the_actor_or_a_different_community(self):
        manageable = services.list_manageable_users(actor=self.admin)
        usernames = {u.username for u in manageable}
        self.assertIn("car_treasurer", usernames)
        self.assertIn("car_collector", usernames)
        self.assertNotIn("car_admin", usernames)
        self.assertNotIn("car_other_treasurer", usernames)


class FamilyHeadRestrictionTests(TestCase):
    """'Same as each family head should also have user management and system settings where they can manage on their family.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fhr-bodi")
        self.admin = User.objects.create_user(username="fhr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_user = User.objects.create_user(username="fhr_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        self.head_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Head", gender="male", linked_user=self.head_user)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_user = User.objects.create_user(username="fhr_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        Member.objects.create(community=self.bodi, family=self.asona, full_name="The Secretary", gender="male", linked_user=self.secretary_user)

        self.plain_member_user = User.objects.create_user(username="fhr_plain_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        Member.objects.create(community=self.bodi, family=self.asona, full_name="Plain Member", gender="male", linked_user=self.plain_member_user)

        self.other_family_secretary_user = User.objects.create_user(username="fhr_other_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Other Secretary", gender="male", linked_user=self.other_family_secretary_user)

    def test_family_head_can_restrict_their_own_family_secretary(self):
        self.assertTrue(can_restrict_features_for(self.head_user, self.secretary_user))

    def test_family_head_can_restrict_a_plain_member_of_their_own_family(self):
        """'Select features he want members to have access to.'"""
        self.assertTrue(can_restrict_features_for(self.head_user, self.plain_member_user))

    def test_family_head_cannot_restrict_a_secretary_of_a_different_family(self):
        """The core family-scoping boundary — this must never leak, the same rule already enforced everywhere else in this platform."""
        self.assertFalse(can_restrict_features_for(self.head_user, self.other_family_secretary_user))

    def test_family_head_cannot_restrict_themselves(self):
        self.assertFalse(can_restrict_features_for(self.head_user, self.head_user))

    def test_family_head_cannot_restrict_a_community_wide_executive(self):
        treasurer = User.objects.create_user(username="fhr_community_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.assertFalse(can_restrict_features_for(self.head_user, treasurer))

    def test_setting_disabled_features_for_a_family_member_persists(self):
        services.set_disabled_features(target=self.plain_member_user, features=["/my-receipts"], actor=self.head_user)
        self.plain_member_user.refresh_from_db()
        self.assertEqual(self.plain_member_user.disabled_features, ["/my-receipts"])

    def test_family_head_cannot_restrict_tasks_since_that_is_the_community_executives_domain(self):
        """'The abusua can't assign work that was supposed to be assigned by the community executive or admin.'"""
        with self.assertRaises(ValidationError):
            services.set_disabled_features(target=self.plain_member_user, features=["/tasks"], actor=self.head_user)

    def test_list_manageable_users_for_family_head_is_scoped_to_own_family_only(self):
        manageable = services.list_manageable_users(actor=self.head_user)
        usernames = {u.username for u in manageable}
        self.assertIn("fhr_secretary", usernames)
        self.assertIn("fhr_plain_member", usernames)
        self.assertNotIn("fhr_other_secretary", usernames)
        self.assertNotIn("fhr_head", usernames)


class FeatureRestrictionHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="frh-bodi")
        self.admin = User.objects.create_user(username="frh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="frh_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_get_manageable_users(self):
        client = self._login("frh_admin")
        res = client.get("/api/accounts/manageable-users/")
        self.assertEqual(res.status_code, 200)
        usernames = [u["username"] for u in res.data["users"]]
        self.assertIn("frh_treasurer", usernames)

    def test_full_http_patch_restricts_a_feature(self):
        client = self._login("frh_admin")
        res = client.patch(
            "/api/accounts/manageable-users/disabled-features/",
            {"target_id": str(self.treasurer.id), "disabled_features": ["/reports"]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.treasurer.refresh_from_db()
        self.assertEqual(self.treasurer.disabled_features, ["/reports"])

    def test_the_restricted_treasurer_cannot_restrict_anyone_themselves(self):
        """A Treasurer isn't a manager tier at all — they should get an empty list, or a 403, never another user's data."""
        client = self._login("frh_treasurer")
        res = client.get("/api/accounts/manageable-users/")
        self.assertEqual(res.status_code, 403)


class ManageableUsersOwnFamilyFieldTests(TestCase):
    """'Make the Family Head system settings have more options, to let some act as treasurer, family contribution and donation collector, and treasurer, secretary as well.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="mof-bodi")
        self.admin = User.objects.create_user(username="mof_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_user = User.objects.create_user(username="mof_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        self.head_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Head", gender="male", linked_user=self.head_user)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

    def test_full_http_response_includes_the_family_heads_own_family(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mof_head", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/accounts/manageable-users/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["own_family_id"], str(self.asona.id))
        self.assertEqual(res.data["own_family_name"], "Asona")

    def test_a_community_admin_gets_no_own_family_since_they_have_none(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mof_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/accounts/manageable-users/")
        self.assertIsNone(res.data["own_family_id"])


class TraditionalLeaderManagesTownEldersTests(TestCase):
    """'The chief should also have user management and system settings features to manage town elders, including adding town elders and the town elders' executive.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tlte-bodi")
        self.admin = User.objects.create_user(username="tlte_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="tlte_chief", password="a-real-password-123", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.elder_user = User.objects.create_user(username="tlte_elder", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.elder_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="An Elder", gender="male", linked_user=self.elder_user)
        member_services.transfer_to_town_elder(member=self.elder_member, title="linguist", actor=self.chief)

        self.ordinary_user = User.objects.create_user(username="tlte_ordinary", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        Member.objects.create(community=self.bodi, family=self.asona, full_name="Ordinary Member", gender="male", linked_user=self.ordinary_user)

    def test_the_chief_can_see_a_town_elders_account_as_manageable(self):
        manageable = services.list_manageable_users(actor=self.chief)
        self.assertIn(self.elder_user, manageable)

    def test_the_chief_cannot_manage_an_ordinary_non_elder_members_account(self):
        manageable = services.list_manageable_users(actor=self.chief)
        self.assertNotIn(self.ordinary_user, manageable)

    def test_the_chiefs_restrictable_features_are_scoped_to_the_town_elders_domain_only(self):
        """Narrower than the full platform list, but now covers both Town-Elder-specific tools, not just the ledger."""
        features = services.restrictable_features_for(self.chief)
        self.assertEqual(set(features.keys()), {"/town-elders-ledger", "/ledger-wallets"})

    def test_the_chief_can_restrict_the_town_elders_ledger_link_for_an_elder(self):
        services.set_disabled_features(target=self.elder_user, features=["/town-elders-ledger"], actor=self.chief)
        self.elder_user.refresh_from_db()
        self.assertEqual(self.elder_user.disabled_features, ["/town-elders-ledger"])

    def test_the_chief_cannot_restrict_features_outside_their_narrow_scope(self):
        with self.assertRaises(ValidationError):
            services.set_disabled_features(target=self.elder_user, features=["/reports"], actor=self.chief)

    def test_full_http_manageable_users_response_for_the_chief(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "tlte_chief", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/accounts/manageable-users/")
        self.assertEqual(res.status_code, 200)
        usernames = [u["username"] for u in res.data["users"]]
        self.assertIn("tlte_elder", usernames)
        self.assertNotIn("tlte_ordinary", usernames)
        self.assertEqual(res.data["restrictable_features"], {"/town-elders-ledger": "Town Elders Ledger", "/ledger-wallets": "Ledger Wallets"})


class RegistrationOfficerRolesAreManageableTests(TestCase):
    """
    A real gap found and fixed: when the three Registration Officer
    roles were added, they were never wired into the existing
    executive-management sets — a Community Admin or Family Head
    couldn't manage these accounts at all, even though the roles
    themselves worked correctly for registration.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="rome-bodi")
        self.admin = User.objects.create_user(username="rome_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="rome_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.family_officer_member = member_services.register_member(community=self.bodi, full_name="Family Officer", gender="male", family=self.asona)
        self.family_officer_user = User.objects.create_user(username="rome_family_officer", password="x", community=self.bodi, role=Role.FAMILY_REGISTRATION_OFFICER)
        member_services.link_member_to_user(member=self.family_officer_member, user=self.family_officer_user, actor=self.admin)

        self.town_officer_user = User.objects.create_user(username="rome_town_officer", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        self.desk_user = User.objects.create_user(username="rome_desk", password="x", community=self.bodi, role=Role.COMMUNITY_REGISTRATION_DESK)

    def test_community_admin_can_manage_a_family_registration_officer(self):
        self.assertTrue(can_restrict_features_for(self.admin, self.family_officer_user))

    def test_community_admin_can_manage_a_town_registration_officer(self):
        self.assertTrue(can_restrict_features_for(self.admin, self.town_officer_user))

    def test_community_admin_can_manage_a_community_registration_desk_account(self):
        self.assertTrue(can_restrict_features_for(self.admin, self.desk_user))

    def test_family_head_can_manage_their_own_familys_registration_officer(self):
        self.assertTrue(can_restrict_features_for(self.head_user, self.family_officer_user))

    def test_the_family_registration_officer_appears_in_the_family_heads_manageable_list(self):
        """The other half of the fix — list_manageable_users' own hardcoded tuple, separate from can_restrict_features_for, needed the same update."""
        manageable = services.list_manageable_users(actor=self.head_user)
        usernames = [u.username for u in manageable]
        self.assertIn("rome_family_officer", usernames)

    def test_the_family_registration_officer_appears_in_the_admins_manageable_list(self):
        manageable = services.list_manageable_users(actor=self.admin)
        usernames = [u.username for u in manageable]
        self.assertIn("rome_family_officer", usernames)
        self.assertIn("rome_town_officer", usernames)
        self.assertIn("rome_desk", usernames)


class ExpandedFamilyHeadAndTraditionalLeaderOptionsTests(TestCase):
    """'The family head... should have more options in the system settings... same as the town leader.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="efhtl-bodi")
        self.admin = User.objects.create_user(username="efhtl_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.head_user = User.objects.create_user(username="efhtl_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        self.chief_user = User.objects.create_user(username="efhtl_chief", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)

    def test_family_head_now_has_welfare_and_family_fund_as_restrictable_options(self):
        features = services.restrictable_features_for(self.head_user)
        self.assertIn("/welfare-contributions", features)
        self.assertIn("/family-fund", features)

    def test_traditional_leader_now_has_ledger_wallets_as_a_restrictable_option(self):
        features = services.restrictable_features_for(self.chief_user)
        self.assertIn("/ledger-wallets", features)

    def test_community_admin_sees_the_full_expanded_list_including_the_newer_features(self):
        features = services.restrictable_features_for(self.admin)
        self.assertIn("/family-fund", features)
        self.assertIn("/ledger-wallets", features)

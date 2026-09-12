from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants import services as tenant_services
from tenants.models import Community


class RoleRevocationTests(TestCase):
    """'Assign and revoke roles and permissions.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-role-revocation")
        self.admin = User.objects.create_user(username="revoke_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Revoke Test Member", gender="male", family=self.asona)

    def test_revoking_a_role_returns_the_member_to_community_member(self):
        member_services.assign_role_to_member(member=self.member, role="treasurer", actor=self.admin, username="revoke_target", password="a-real-password-123")
        self.member.refresh_from_db()
        self.assertEqual(self.member.linked_user.role, "treasurer")

        updated_user = member_services.revoke_role_from_member(member=self.member, actor=self.admin)
        self.assertEqual(updated_user.role, "community_member")

    def test_cannot_revoke_from_someone_with_no_login(self):
        with self.assertRaises(ValidationError):
            member_services.revoke_role_from_member(member=self.member, actor=self.admin)

    def test_cannot_revoke_an_already_plain_member(self):
        member_services.assign_role_to_member(member=self.member, role="community_member", actor=self.admin, username="already_plain", password="a-real-password-123")
        with self.assertRaises(ValidationError):
            member_services.revoke_role_from_member(member=self.member, actor=self.admin)


class CommunityBrandingTests(TestCase):
    """'Configure branding (logo, colors, community information)' — self-service, no Platform Admin involvement."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-branding")
        self.admin = User.objects.create_user(username="branding_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_community = Community.objects.create(name="Other Town", slug="other-town-branding")
        self.other_admin = User.objects.create_user(username="other_branding_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)

    def test_community_admin_can_set_their_own_branding(self):
        updated = tenant_services.update_own_community_branding(actor=self.admin, tagline="Every ledger transparent.", primary_color="#2F5233", secondary_color="#B8860B")
        self.assertEqual(updated.tagline, "Every ledger transparent.")
        self.assertEqual(updated.primary_color, "#2F5233")

    def test_invalid_hex_color_is_rejected(self):
        with self.assertRaises(ValidationError):
            tenant_services.update_own_community_branding(actor=self.admin, primary_color="not-a-color")

    def test_a_non_community_admin_cannot_configure_branding(self):
        member = User.objects.create_user(username="branding_plain_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            tenant_services.update_own_community_branding(actor=member, tagline="Should fail")

    def test_branding_never_leaks_into_another_communitys_data(self):
        tenant_services.update_own_community_branding(actor=self.admin, tagline="Bodi's own tagline")
        self.other_community.refresh_from_db()
        self.assertEqual(self.other_community.tagline, "")


class ApprovalWorkflowConfigurationTests(TestCase):
    """'Configure approval workflows' — each community's own Admin decides how many approvals a funeral opening needs."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-approval-config")
        self.admin = User.objects.create_user(username="approval_config_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="approval_config_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.chairman = User.objects.create_user(username="approval_config_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_default_required_approvals_is_two(self):
        self.assertEqual(self.bodi.required_funeral_approvals, 2)

    def test_community_admin_can_lower_required_approvals_to_one(self):
        tenant_services.update_required_funeral_approvals(actor=self.admin, required_approvals=1)
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.required_funeral_approvals, 1)

    def test_a_single_approval_now_activates_the_funeral_when_configured_to_one(self):
        tenant_services.update_required_funeral_approvals(actor=self.admin, required_approvals=1)
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Approval Config Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.secretary, own_family_amount=Decimal("50"),
        )
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.chairman)
        funeral.refresh_from_db()
        from funerals.models import FuneralEvent
        self.assertEqual(funeral.status, FuneralEvent.Status.ACTIVE)

    def test_value_outside_one_to_ten_is_rejected(self):
        with self.assertRaises(ValidationError):
            tenant_services.update_required_funeral_approvals(actor=self.admin, required_approvals=0)
        with self.assertRaises(ValidationError):
            tenant_services.update_required_funeral_approvals(actor=self.admin, required_approvals=11)


class TerminateCommunityAccessTests(TestCase):
    """'Extend or terminate licenses.'"""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="terminate_platform_admin", password="x", role=Role.PLATFORM_ADMIN)

    def test_terminating_a_temporary_communitys_access_ends_it_immediately(self):
        from django.utils import timezone
        from datetime import timedelta
        temp_community = Community.objects.create(
            name="Temp Event", slug="temp-event-terminate",
            access_plan=Community.AccessPlan.TIME_LIMITED, access_expires_at=timezone.now() + timedelta(days=30),
        )
        updated = tenant_services.terminate_community_access(community=temp_community, actor=self.platform_admin)
        self.assertTrue(updated.is_access_expired)

    def test_cannot_terminate_an_ongoing_permanent_communitys_access(self):
        permanent_community = Community.objects.create(name="Permanent Town", slug="permanent-town-terminate")
        with self.assertRaises(ValidationError):
            tenant_services.terminate_community_access(community=permanent_community, actor=self.platform_admin)


class ResetAdministratorPasswordTests(TestCase):
    """'Reset administrator accounts when requested.'"""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="reset_pw_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-reset-pw")
        self.community_admin = User.objects.create_user(username="reset_pw_community_admin", password="the-old-password", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.ordinary_member = User.objects.create_user(username="reset_pw_ordinary_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_platform_admin_can_reset_a_community_admins_password(self):
        tenant_services.reset_administrator_password(actor=self.platform_admin, username="reset_pw_community_admin", new_password="a-brand-new-password-123")
        self.community_admin.refresh_from_db()
        self.assertTrue(self.community_admin.check_password("a-brand-new-password-123"))
        self.assertFalse(self.community_admin.check_password("the-old-password"))

    def test_cannot_reset_an_ordinary_members_password_this_way(self):
        with self.assertRaises(ValidationError):
            tenant_services.reset_administrator_password(actor=self.platform_admin, username="reset_pw_ordinary_member", new_password="a-brand-new-password-123")

    def test_a_community_admin_cannot_reset_anyones_password_this_way(self):
        with self.assertRaises(ValidationError):
            tenant_services.reset_administrator_password(actor=self.community_admin, username="reset_pw_ordinary_member", new_password="a-brand-new-password-123")

    def test_password_under_eight_characters_is_rejected(self):
        with self.assertRaises(ValidationError):
            tenant_services.reset_administrator_password(actor=self.platform_admin, username="reset_pw_community_admin", new_password="short")


class AdministratorAutonomyHttpTests(TestCase):
    """Full round-trip HTTP tests for the new self-service endpoints."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-autonomy-http")
        self.admin = User.objects.create_user(username="autonomy_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.platform_admin = User.objects.create_user(username="autonomy_http_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_community_admin_can_view_and_update_their_own_branding_over_http(self):
        client = self._login("autonomy_http_admin")
        get_res = client.get("/api/tenants/my-community/branding/")
        self.assertEqual(get_res.status_code, 200)

        patch_res = client.patch("/api/tenants/my-community/branding/", {"tagline": "Every family seen."}, format="json")
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["tagline"], "Every family seen.")

    def test_community_admin_can_configure_approval_workflow_over_http(self):
        client = self._login("autonomy_http_admin")
        res = client.patch("/api/tenants/my-community/approval-workflow/", {"required_approvals": 3}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["required_funeral_approvals"], 3)

    def test_platform_admin_can_reset_a_password_over_http_without_a_community_id_in_the_url(self):
        client = self._login("autonomy_http_platform_admin")
        res = client.post("/api/tenants/reset-admin-password/", {"username": "autonomy_http_admin", "new_password": "a-fresh-password-456"})
        self.assertEqual(res.status_code, 200)

    def test_platform_admin_can_terminate_a_temporary_communitys_license_over_http(self):
        from django.utils import timezone
        from datetime import timedelta
        temp_community = Community.objects.create(
            name="HTTP Temp Event", slug="http-temp-event",
            access_plan=Community.AccessPlan.TIME_LIMITED, access_expires_at=timezone.now() + timedelta(days=30),
        )
        client = self._login("autonomy_http_platform_admin")
        res = client.post(f"/api/tenants/communities/{temp_community.id}/terminate-access/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_access_expired"])

    def test_a_community_admin_cannot_configure_another_communitys_branding(self):
        other_community = Community.objects.create(name="Other Autonomy Town", slug="other-autonomy-town")
        User.objects.create_user(username="other_autonomy_admin", password="a-real-password-123", community=other_community, role=Role.COMMUNITY_ADMIN)
        client = self._login("autonomy_http_admin")
        client.patch("/api/tenants/my-community/branding/", {"tagline": "Trying to configure my own only"}, format="json")
        other_community.refresh_from_db()
        self.assertEqual(other_community.tagline, "")

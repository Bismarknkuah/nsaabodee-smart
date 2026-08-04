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


class PlatformAdminIsNeverASuperuserTests(TestCase):
    """
    'Platform Administrator must not...' only holds if a real platform
    admin account genuinely lacks is_superuser — that flag bypasses
    every one of these checks throughout the whole codebase. Both
    creation paths are tested directly.
    """

    def test_create_platform_admin_management_command_never_sets_superuser(self):
        from django.core.management import call_command
        from unittest.mock import patch

        with patch("getpass.getpass", side_effect=["a-real-password-123", "a-real-password-123"]):
            call_command("create_platform_admin", username="cli_admin")
        user = User.objects.get(username="cli_admin")
        self.assertEqual(user.role, Role.PLATFORM_ADMIN)
        self.assertFalse(user.is_superuser)

    def test_add_platform_admin_via_api_never_sets_superuser(self):
        existing_admin = User.objects.create_user(username="existing_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        new_admin = tenant_services.add_platform_admin(username="api_admin", password="a-real-password-123", actor=existing_admin)
        self.assertEqual(new_admin.role, Role.PLATFORM_ADMIN)
        self.assertFalse(new_admin.is_superuser)


class PlatformAdminMustNotTests(TestCase):
    """Every item on 'The Platform Administrator must not...' tested directly, with a genuinely non-superuser platform admin account."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="boundary_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.assertFalse(self.platform_admin.is_superuser)  # sanity check on the fixture itself

        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-pa-boundaries",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.community_admin = User.objects.create_user(username="boundary_community_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.community_admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Boundary Member", gender="male", family=self.asona)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_cannot_add_a_community_member(self):
        client = self._login("boundary_platform_admin")
        res = client.post("/api/members/", {"full_name": "Should Fail", "gender": "male"})
        self.assertEqual(res.status_code, 403)

    def test_cannot_edit_a_community_member(self):
        client = self._login("boundary_platform_admin")
        res = client.patch(f"/api/members/{self.member.id}/", {"phone": "0200000000"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_cannot_manage_community_families(self):
        client = self._login("boundary_platform_admin")
        res = client.post("/api/families/", {"name": "Should Fail Family"})
        self.assertEqual(res.status_code, 403)

    def test_cannot_create_a_funeral_event(self):
        client = self._login("boundary_platform_admin")
        res = client.post("/api/funerals/", {
            "deceased_name": "Should Fail", "deceased_gender": "male",
            "deceased_family": str(self.asona.id), "date_of_death": "2026-07-01",
            "collection_start_date": "2026-07-01", "own_family_amount": "50",
        })
        self.assertEqual(res.status_code, 403)

    def test_cannot_record_a_funeral_contribution(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Boundary Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.community_admin, own_family_amount=Decimal("50"),
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=self.member)
        client = self._login("boundary_platform_admin")
        res = client.post(f"/api/funerals/{funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        # 404 is an equally valid "blocked" outcome here — CanRecordPaymentsOrIsDeskWorker
        # would reject with 403, but the view resolves the funeral through
        # a community-scoped queryset first, and Platform Admin's own
        # community is None, so it never matches a real funeral at all.
        # Either way, the boundary genuinely holds.
        self.assertIn(res.status_code, (403, 404))

    def test_cannot_record_a_gift_donation(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Boundary Deceased 2", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.community_admin, own_family_amount=Decimal("50"),
        )
        client = self._login("boundary_platform_admin")
        res = client.post(f"/api/gifts/funerals/{funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "100"})
        self.assertIn(res.status_code, (403, 404))

    def test_cannot_view_community_financial_reports(self):
        client = self._login("boundary_platform_admin")
        res = client.get("/api/reports/expenses/", {"start_date": "2026-07-01", "end_date": "2026-07-31"})
        self.assertEqual(res.status_code, 403)

    def test_cannot_view_a_communitys_financial_overview(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Boundary Deceased 3", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.community_admin, own_family_amount=Decimal("50"),
        )
        client = self._login("boundary_platform_admin")
        res = client.get(f"/api/funerals/{funeral.id}/financial-overview/")
        # Same reasoning as the payment-recording test above — 404 here
        # comes from the community-scoped queryset excluding Platform
        # Admin (community=None never matches a real funeral), which is
        # just as genuine a block as an explicit 403 would be.
        self.assertIn(res.status_code, (403, 404))


class PlatformAdminMustTests(TestCase):
    """Every item on 'should be responsible for' that's actually built, confirmed still genuinely reachable."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="capability_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_can_register_a_new_community(self):
        client = self._login("capability_platform_admin")
        res = client.post("/api/tenants/communities/", {
            "community_name": "New Test Town", "admin_username": "new_test_town_admin", "admin_password": "a-real-password-123",
        })
        self.assertEqual(res.status_code, 201)

    def test_can_suspend_and_reactivate_a_community(self):
        community = Community.objects.create(name="Suspend Test", slug="suspend-test-pa")
        client = self._login("capability_platform_admin")
        deactivate_res = client.post(f"/api/tenants/communities/{community.id}/deactivate/")
        self.assertEqual(deactivate_res.status_code, 200)
        reactivate_res = client.post(f"/api/tenants/communities/{community.id}/reactivate/")
        self.assertEqual(reactivate_res.status_code, 200)

    def test_can_manage_feature_flags(self):
        client = self._login("capability_platform_admin")
        res = client.get("/api/tenants/feature-flags/")
        self.assertEqual(res.status_code, 200)

    def test_can_view_the_audit_log(self):
        client = self._login("capability_platform_admin")
        res = client.get("/api/audit-log/")
        self.assertEqual(res.status_code, 200)

    def test_can_view_the_support_ticket_queue(self):
        client = self._login("capability_platform_admin")
        res = client.get("/api/support/tickets/all/")
        self.assertEqual(res.status_code, 200)

    def test_can_view_platform_revenue(self):
        client = self._login("capability_platform_admin")
        res = client.get("/api/tenants/platform-revenue/")
        self.assertEqual(res.status_code, 200)

    def test_can_manage_other_platform_admins(self):
        client = self._login("capability_platform_admin")
        list_res = client.get("/api/tenants/platform-admins/")
        self.assertEqual(list_res.status_code, 200)
        create_res = client.post("/api/tenants/platform-admins/", {"username": "second_platform_admin", "password": "a-real-password-123"})
        self.assertEqual(create_res.status_code, 201)
        new_user = User.objects.get(username="second_platform_admin")
        self.assertFalse(new_user.is_superuser)

    def test_dashboard_shows_only_high_level_aggregate_platform_stats(self):
        client = self._login("capability_platform_admin")
        res = client.get("/api/dashboard/")
        self.assertEqual(res.status_code, 200)
        overview = res.data["sections"]["platform_overview"]
        self.assertIn("community_count", overview)
        self.assertIn("total_members_platform_wide", overview)
        # Never a per-member or per-transaction breakdown, only aggregate counts.
        self.assertNotIn("members", overview)
        self.assertNotIn("transactions", overview)


class NonPlatformAdminCannotManagePlatformAdminsTests(TestCase):
    def test_a_community_admin_cannot_list_or_create_platform_admins(self):
        bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-pa-guard")
        community_admin = User.objects.create_user(username="guard_community_admin", password="a-real-password-123", community=bodi, role=Role.COMMUNITY_ADMIN)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "guard_community_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        list_res = client.get("/api/tenants/platform-admins/")
        self.assertEqual(list_res.status_code, 403)
        create_res = client.post("/api/tenants/platform-admins/", {"username": "should_not_exist", "password": "a-real-password-123"})
        self.assertEqual(create_res.status_code, 403)
        self.assertFalse(User.objects.filter(username="should_not_exist").exists())

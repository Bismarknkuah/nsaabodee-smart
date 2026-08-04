"""
'Maintain the platform admin and delete the super admin' — Role.SUPER_ADMIN
has been removed entirely; Role.PLATFORM_ADMIN is now the one and only
platform-tier role. This file (kept under its original name so its git
history stays attached) now tests PLATFORM_ADMIN's own boundaries.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from tenants.models import Community


class PlatformAdminOperationalBoundaryTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-boundary",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.platform_admin = User.objects.create_user(username="role_only_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="real_community_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.community_admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.community_admin)
        family_services.approve_family_rate(family=self.asona, actor=self.community_admin)

    def test_platform_admin_cannot_register_a_member(self):
        from members.permissions import MEMBER_REGISTRATION_ROLES
        self.assertNotIn(self.platform_admin.role, MEMBER_REGISTRATION_ROLES)

    def test_platform_admin_cannot_manage_families(self):
        self.assertFalse(self.platform_admin.can_manage_families())

    def test_community_admin_can_still_manage_families_completely_unaffected(self):
        self.assertTrue(self.community_admin.can_manage_families())

    def test_platform_admin_is_not_in_any_gift_recording_role(self):
        from gifts.permissions import GIFT_RECORDING_ROLES
        self.assertNotIn(Role.PLATFORM_ADMIN, GIFT_RECORDING_ROLES)
        self.assertIn(Role.COLLECTOR, GIFT_RECORDING_ROLES)

    def test_platform_admin_is_not_in_any_payment_collecting_role(self):
        from funerals.permissions import PAYMENT_COLLECTING_ROLES
        self.assertNotIn(Role.PLATFORM_ADMIN, PAYMENT_COLLECTING_ROLES)

    def test_platform_admin_is_not_a_funeral_opening_approver(self):
        from funerals.permissions import FUNERAL_OPENING_APPROVAL_ROLES
        self.assertNotIn(Role.PLATFORM_ADMIN, FUNERAL_OPENING_APPROVAL_ROLES)

    def test_platform_admin_cannot_manage_contribution_rules(self):
        from contribution_rules.permissions import CONTRIBUTION_RULE_MANAGER_ROLES
        self.assertNotIn(Role.PLATFORM_ADMIN, CONTRIBUTION_RULE_MANAGER_ROLES)

    def test_platform_admin_cannot_view_reports(self):
        from reports.permissions import REPORT_VIEWING_ROLES
        self.assertNotIn(Role.PLATFORM_ADMIN, REPORT_VIEWING_ROLES)

    def test_platform_admin_cannot_assign_tasks_or_record_expenses(self):
        from tasks.permissions import TASK_ASSIGNMENT_ROLES
        from funeral_logistics.permissions import EXPENSE_ROLES
        self.assertNotIn(Role.PLATFORM_ADMIN, TASK_ASSIGNMENT_ROLES)
        self.assertNotIn(Role.PLATFORM_ADMIN, EXPENSE_ROLES)

    def test_platform_admin_cannot_assign_funeral_desk_workers(self):
        from funerals.services import _DESK_ASSIGNER_COMMUNITY_WIDE_ROLES
        self.assertNotIn("platform_admin", _DESK_ASSIGNER_COMMUNITY_WIDE_ROLES)

    def test_end_to_end_a_real_http_request_to_register_a_member_is_genuinely_rejected(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "role_only_platform_admin", "password": "x"})
        self.assertEqual(login.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/members/", {"full_name": "Should Be Rejected", "gender": "male"})
        self.assertEqual(res.status_code, 403)

    def test_end_to_end_a_real_http_request_to_record_a_gift_is_genuinely_rejected(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.community_admin, own_family_amount=Decimal("50"),
        )
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "role_only_platform_admin", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(f"/api/funerals/{funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20"})
        self.assertIn(res.status_code, (403, 404))


class PlatformAdminStillHasPlatformAccessTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="platform_job_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def test_platform_admin_can_still_reach_the_communities_console(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "platform_job_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/tenants/communities/")
        self.assertEqual(res.status_code, 200)

    def test_platform_admin_still_sees_the_platform_overview_dashboard_not_a_community_one(self):
        from dashboard.services import build_dashboard
        result = build_dashboard(self.platform_admin)
        self.assertIn("platform_overview", result["sections"])
        self.assertNotIn("community_overview", result["sections"])


class RealDemoAccountsReflectTheRestrictionTests(TestCase):
    def test_demo_platform_admin_is_genuinely_role_only(self):
        from django.core.management import call_command
        import io
        call_command("seed_demo_data", stdout=io.StringIO())
        demo_platform_admin = User.objects.get(username="demo_platform_admin")
        self.assertFalse(demo_platform_admin.is_superuser)
        self.assertFalse(demo_platform_admin.can_manage_families())

    def test_demo_super_admin_no_longer_exists_at_all(self):
        from django.core.management import call_command
        import io
        call_command("seed_demo_data", stdout=io.StringIO())
        self.assertFalse(User.objects.filter(username="demo_super_admin").exists())

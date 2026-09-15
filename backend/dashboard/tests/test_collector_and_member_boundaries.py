from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class CollectorAndMemberBoundaryTests(TestCase):
    """'Collectors cannot edit system settings.' 'Members must never access community administration pages.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-collector-member-boundaries")
        self.admin = User.objects.create_user(username="boundary_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.collector = User.objects.create_user(username="boundary_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member_profile = member_services.register_member(community=self.bodi, full_name="Boundary Member", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(username="boundary_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member_profile, user=self.member_user, actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_a_collector_cannot_update_community_settings(self):
        client = self._login("boundary_collector")
        res = client.patch("/api/tenants/my-community/branding/", {"tagline": "Should fail"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_a_collector_cannot_configure_the_approval_workflow(self):
        client = self._login("boundary_collector")
        res = client.patch("/api/tenants/my-community/approval-workflow/", {"required_approvals": 5}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_a_collector_cannot_create_a_contribution_category(self):
        client = self._login("boundary_collector")
        res = client.post("/api/welfare/categories/", {"name": "Should Fail", "amount_type": "fixed", "fixed_amount": "5"})
        self.assertEqual(res.status_code, 400)

    def test_an_ordinary_member_cannot_create_a_family(self):
        client = self._login("boundary_member")
        res = client.post("/api/families/", {"name": "Should Fail"})
        self.assertEqual(res.status_code, 403)

    def test_an_ordinary_member_cannot_view_the_audit_log(self):
        client = self._login("boundary_member")
        res = client.get("/api/audit-log/")
        self.assertEqual(res.status_code, 403)

    def test_an_ordinary_member_cannot_manage_feature_flags(self):
        client = self._login("boundary_member")
        res = client.get("/api/tenants/feature-flags/")
        self.assertEqual(res.status_code, 403)

    def test_an_ordinary_member_cannot_view_the_platform_revenue_report(self):
        client = self._login("boundary_member")
        res = client.get("/api/tenants/platform-revenue/")
        self.assertEqual(res.status_code, 403)

    def test_an_ordinary_member_cannot_register_a_new_member(self):
        client = self._login("boundary_member")
        res = client.post("/api/members/", {"full_name": "Should Fail", "gender": "male"})
        self.assertEqual(res.status_code, 403)

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class WelfareHttpRoundTripTests(TestCase):
    """Full round-trip HTTP tests across the whole welfare contribution API."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-welfare-http")
        self.admin = User.objects.create_user(username="welfare_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="HTTP Family Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="welfare_http_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="HTTP Secretary", gender="female", family=self.asona)
        self.secretary_user = User.objects.create_user(username="welfare_http_secretary", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary_user, actor=self.admin)
        self.asona.family_secretary = self.secretary_member
        self.asona.save(update_fields=["family_secretary"])

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="HTTP Treasurer", gender="male", family=self.asona)
        self.treasurer_user = User.objects.create_user(username="welfare_http_treasurer", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer_user, actor=self.admin)
        self.asona.family_treasurer = self.treasurer_member
        self.asona.save(update_fields=["family_treasurer"])

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_community_wide_flow_category_to_payment(self):
        admin_client = self._login("welfare_http_admin")

        cat_res = admin_client.post("/api/welfare/categories/", {
            "name": "Annual Dues", "amount_type": "fixed", "fixed_amount": "20", "frequency": "annual",
        })
        self.assertEqual(cat_res.status_code, 201)
        category_id = cat_res.data["id"]

        campaign_res = admin_client.post("/api/welfare/campaigns/community-wide/", {
            "category_id": category_id, "title": "2026 Annual Dues",
        })
        self.assertEqual(campaign_res.status_code, 201)
        self.assertEqual(campaign_res.data["status"], "active")
        campaign_id = campaign_res.data["id"]

        obligations_res = admin_client.get(f"/api/welfare/campaigns/{campaign_id}/obligations/")
        self.assertEqual(obligations_res.status_code, 200)
        self.assertGreaterEqual(len(obligations_res.data), 1)
        obligation_id = obligations_res.data[0]["id"]

        pay_res = admin_client.post(f"/api/welfare/obligations/{obligation_id}/record-payment/", {"amount": "20", "method": "cash"})
        self.assertEqual(pay_res.status_code, 201)
        self.assertEqual(pay_res.data["payment_status"], "paid")

    def test_full_family_initiated_flow_with_two_approvals(self):
        admin_client = self._login("welfare_http_admin")
        cat_res = admin_client.post("/api/welfare/categories/", {"name": "Family Drive", "amount_type": "fixed", "fixed_amount": "15"})
        category_id = cat_res.data["id"]

        head_client = self._login("welfare_http_head")
        campaign_res = head_client.post(f"/api/welfare/families/{self.asona.id}/campaigns/", {
            "category_id": category_id, "title": "Asona Welfare Drive",
        })
        self.assertEqual(campaign_res.status_code, 201)
        self.assertEqual(campaign_res.data["status"], "pending_approval")
        campaign_id = campaign_res.data["id"]

        secretary_client = self._login("welfare_http_secretary")
        decide1_res = secretary_client.post(f"/api/welfare/campaigns/{campaign_id}/decide/", {"approve": True})
        self.assertEqual(decide1_res.status_code, 200)
        self.assertEqual(decide1_res.data["status"], "pending_approval")

        treasurer_client = self._login("welfare_http_treasurer")
        decide2_res = treasurer_client.post(f"/api/welfare/campaigns/{campaign_id}/decide/", {"approve": True})
        self.assertEqual(decide2_res.status_code, 200)
        self.assertEqual(decide2_res.data["status"], "family_approved")

        pending_res = admin_client.get("/api/welfare/campaigns/pending-admin-approval/")
        self.assertEqual(pending_res.status_code, 200)
        self.assertEqual(len(pending_res.data), 1)

        final_res = admin_client.post(f"/api/welfare/campaigns/{campaign_id}/admin-approve/")
        self.assertEqual(final_res.status_code, 200)
        self.assertEqual(final_res.data["status"], "active")

    def test_campaign_list_excludes_another_familys_campaign_for_an_ordinary_member(self):
        admin_client = self._login("welfare_http_admin")
        cat_res = admin_client.post("/api/welfare/categories/", {"name": "Test Cat", "amount_type": "fixed", "fixed_amount": "5"})
        category_id = cat_res.data["id"]

        bretuo_head_member = member_services.register_member(community=self.bodi, full_name="Bretuo Head", gender="male", family=self.bretuo)
        bretuo_head_user = User.objects.create_user(username="welfare_http_bretuo_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=bretuo_head_member, user=bretuo_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=bretuo_head_member, actor=self.admin)

        bretuo_client = self._login("welfare_http_bretuo_head")
        bretuo_client.post(f"/api/welfare/families/{self.bretuo.id}/campaigns/", {"category_id": category_id, "title": "Bretuo Only Campaign"})

        head_client = self._login("welfare_http_head")
        list_res = head_client.get("/api/welfare/campaigns/")
        titles = [c["title"] for c in list_res.data]
        self.assertNotIn("Bretuo Only Campaign", titles)

    def test_a_non_admin_cannot_create_a_category_over_http(self):
        client = self._login("welfare_http_head")
        res = client.post("/api/welfare/categories/", {"name": "Should Fail", "amount_type": "fixed", "fixed_amount": "5"})
        # The serializer's own save() converts the ValidationError before
        # the view's except block ever sees it, so DRF's own default
        # handling applies here — 400, the established convention for
        # serializer-level validation failures throughout this codebase.
        self.assertEqual(res.status_code, 400)

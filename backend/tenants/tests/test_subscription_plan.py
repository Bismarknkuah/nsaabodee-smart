from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from audit_log.models import AuditLogEntry
from tenants import services as tenant_services
from tenants.models import Community, SubscriptionPlan


def _login(username):
    client = APIClient()
    login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


class CommunitySubscriptionPlanTests(TestCase):
    """'The platform admin should be able to promote or demote a community to any of the subscription plans.'"""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="sp_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="sp-bodi")
        self.community_admin = User.objects.create_user(username="sp_community_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_the_three_plans_are_seeded_by_the_migration(self):
        self.assertTrue(set(SubscriptionPlan.objects.values_list("code", flat=True)) >= {"single_funeral", "community", "multi_community"})

    def test_a_newly_registered_community_defaults_to_the_community_tier(self):
        community, _admin = tenant_services.onboard_new_community(community_name="Brand New Town", admin_username="bnt_admin", admin_password="a-real-password-123")
        self.assertEqual(community.subscription_plan.code, "community")

    def test_platform_admin_can_promote_a_community_to_multi_community(self):
        tenant_services.set_community_subscription_plan(community=self.bodi, plan="multi_community", actor=self.platform_admin)
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.subscription_plan.code, "multi_community")

    def test_platform_admin_can_demote_a_community_to_single_funeral(self):
        tenant_services.set_community_subscription_plan(community=self.bodi, plan="single_funeral", actor=self.platform_admin)
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.subscription_plan.code, "single_funeral")

    def test_a_community_admin_cannot_change_their_own_communitys_plan(self):
        with self.assertRaises(ValidationError):
            tenant_services.set_community_subscription_plan(community=self.bodi, plan="multi_community", actor=self.community_admin)

    def test_an_unrecognised_plan_is_rejected(self):
        with self.assertRaises(ValidationError):
            tenant_services.set_community_subscription_plan(community=self.bodi, plan="platinum", actor=self.platform_admin)

    def test_a_plan_change_is_recorded_in_the_audit_log(self):
        tenant_services.set_community_subscription_plan(community=self.bodi, plan="multi_community", actor=self.platform_admin)
        entry = AuditLogEntry.objects.filter(action="subscription_plan_changed", community=self.bodi).first()
        self.assertIsNotNone(entry)
        self.assertIn("multi_community", entry.description)


class CommunitySubscriptionPlanEndpointTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="spe_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="spe-bodi")
        self.community_admin = User.objects.create_user(username="spe_community_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_platform_admin_can_change_the_plan_over_http(self):
        res = _login("spe_platform_admin").post(f"/api/tenants/communities/{self.bodi.id}/subscription-plan/", {"plan": "multi_community"})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["subscription_plan"], "multi_community")
        self.assertEqual(res.data["subscription_plan_name"], "Multi-Community")

    def test_a_community_admin_is_rejected_over_http(self):
        res = _login("spe_community_admin").post(f"/api/tenants/communities/{self.bodi.id}/subscription-plan/", {"plan": "multi_community"})
        self.assertIn(res.status_code, (403, 400))
        self.bodi.refresh_from_db()
        self.assertIsNone(self.bodi.subscription_plan_id)

    def test_an_invalid_plan_returns_400(self):
        res = _login("spe_platform_admin").post(f"/api/tenants/communities/{self.bodi.id}/subscription-plan/", {"plan": "platinum"})
        self.assertEqual(res.status_code, 400)


class SubscriptionPlanCrudTests(TestCase):
    """'+ New plan' and 'Edit' — plans as real, editable records, Platform Admin only."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="spc_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="spc-bodi")
        self.community_admin = User.objects.create_user(username="spc_community_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_platform_admin_can_create_a_brand_new_plan(self):
        plan = tenant_services.create_subscription_plan(
            actor=self.platform_admin, code="Enterprise Plus", name="Enterprise Plus",
            price_yearly="9000.00", price_monthly="900.00", max_members=100000, trial_days=90,
            features=["Everything in Multi-Community", "Dedicated support"],
        )
        self.assertEqual(plan.code, "enterprise_plus")
        self.assertEqual(plan.features, ["Everything in Multi-Community", "Dedicated support"])

    def test_a_duplicate_code_is_rejected(self):
        with self.assertRaises(ValidationError):
            tenant_services.create_subscription_plan(actor=self.platform_admin, code="community", name="Duplicate")

    def test_a_community_admin_cannot_create_or_edit_plans(self):
        plan = SubscriptionPlan.objects.get(code="community")
        with self.assertRaises(ValidationError):
            tenant_services.create_subscription_plan(actor=self.community_admin, code="sneaky", name="Sneaky")
        with self.assertRaises(ValidationError):
            tenant_services.update_subscription_plan(plan=plan, actor=self.community_admin, price_yearly="1.00")

    def test_editing_a_plan_updates_its_price_and_features_but_never_its_code(self):
        plan = SubscriptionPlan.objects.get(code="community")
        tenant_services.update_subscription_plan(plan=plan, actor=self.platform_admin, price_yearly="4000.00", features=["A", "B"])
        plan.refresh_from_db()
        self.assertEqual(str(plan.price_yearly), "4000.00")
        self.assertEqual(plan.features, ["A", "B"])
        self.assertEqual(plan.code, "community")

    def test_plans_endpoint_lists_every_plan_with_its_community_count(self):
        tenant_services.set_community_subscription_plan(community=self.bodi, plan="multi_community", actor=self.platform_admin)
        res = _login("spc_platform_admin").get("/api/tenants/subscription-plans/")
        self.assertEqual(res.status_code, 200)
        by_code = {p["code"]: p for p in res.data}
        self.assertEqual(by_code["multi_community"]["community_count"], 1)
        self.assertIn("features", by_code["single_funeral"])

    def test_plan_can_be_created_and_edited_over_http(self):
        client = _login("spc_platform_admin")
        res = client.post("/api/tenants/subscription-plans/", {"code": "starter", "name": "Starter", "price_yearly": "1500.00", "features": ["Academics"]}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        res2 = client.patch(f"/api/tenants/subscription-plans/{res.data['id']}/", {"price_monthly": "150.00"}, format="json")
        self.assertEqual(res2.status_code, 200, res2.data)
        self.assertEqual(res2.data["price_monthly"], "150.00")

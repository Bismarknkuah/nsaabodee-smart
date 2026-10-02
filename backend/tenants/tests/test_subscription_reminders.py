from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import Notification
from tenants import services
from tenants.models import Community, PlatformBillingRecord


class SendSubscriptionReminderTests(TestCase):
    """'The platform admin should have a way to remind communities to pay their subscription fees.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ssr-bodi")
        self.platform_admin = User.objects.create_user(username="ssr_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.community_admin_1 = User.objects.create_user(username="ssr_admin_1", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.community_admin_2 = User.objects.create_user(username="ssr_admin_2", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_a_plain_member_cannot_send_a_reminder(self):
        plain = User.objects.create_user(username="ssr_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            services.send_subscription_reminder(community=self.bodi, actor=plain)

    def test_the_reminder_goes_to_every_community_admin_not_just_one(self):
        sent = services.send_subscription_reminder(community=self.bodi, actor=self.platform_admin, message="Please pay up.")
        self.assertEqual(sent, 2)
        self.assertTrue(Notification.objects.filter(recipient_user=self.community_admin_1, category="subscription_reminder").exists())
        self.assertTrue(Notification.objects.filter(recipient_user=self.community_admin_2, category="subscription_reminder").exists())

    def test_sending_a_reminder_records_who_and_when_on_the_community(self):
        self.assertIsNone(self.bodi.last_subscription_reminder_at)
        services.send_subscription_reminder(community=self.bodi, actor=self.platform_admin, message="test")
        self.bodi.refresh_from_db()
        self.assertIsNotNone(self.bodi.last_subscription_reminder_at)
        self.assertEqual(self.bodi.last_subscription_reminder_by, self.platform_admin)

    def test_the_default_message_names_actual_unpaid_billing_records(self):
        PlatformBillingRecord.objects.create(community=self.bodi, description="Monthly subscription — July 2026", amount=Decimal("150"), created_by=self.platform_admin)
        services.send_subscription_reminder(community=self.bodi, actor=self.platform_admin)
        notification = Notification.objects.filter(recipient_user=self.community_admin_1).first()
        self.assertIn("Monthly subscription — July 2026", notification.message)
        self.assertIn("150", notification.message)

    def test_a_custom_message_overrides_the_default(self):
        services.send_subscription_reminder(community=self.bodi, actor=self.platform_admin, message="Custom reminder text")
        notification = Notification.objects.filter(recipient_user=self.community_admin_1).first()
        self.assertEqual(notification.message, "Custom reminder text")


class CommunitiesNeedingSubscriptionAttentionTests(TestCase):
    """The actual worklist a Platform Admin would use to decide who to remind."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="cnsa_platform_admin", password="x", role=Role.PLATFORM_ADMIN)

    def test_a_permanent_community_with_nothing_unpaid_is_never_listed(self):
        Community.objects.create(name="Fine", slug="cnsa-fine")
        results = services.communities_needing_subscription_attention()
        self.assertEqual(results.count(), 0)

    def test_a_community_with_an_unpaid_billing_record_is_listed(self):
        owing = Community.objects.create(name="Owing", slug="cnsa-owing")
        PlatformBillingRecord.objects.create(community=owing, description="Setup fee", amount=Decimal("100"), created_by=self.platform_admin)
        results = services.communities_needing_subscription_attention()
        self.assertIn(owing, results)

    def test_a_community_with_only_a_paid_billing_record_is_not_listed(self):
        paid_up = Community.objects.create(name="Paid Up", slug="cnsa-paid")
        PlatformBillingRecord.objects.create(
            community=paid_up, description="Setup fee", amount=Decimal("100"),
            status=PlatformBillingRecord.Status.PAID, created_by=self.platform_admin,
        )
        results = services.communities_needing_subscription_attention()
        self.assertNotIn(paid_up, results)

    def test_a_community_with_expired_access_is_listed_even_with_nothing_unpaid(self):
        from django.utils import timezone
        from datetime import timedelta
        expired = Community.objects.create(
            name="Expired", slug="cnsa-expired",
            access_plan=Community.AccessPlan.TIME_LIMITED, access_expires_at=timezone.now() - timedelta(days=1),
        )
        results = services.communities_needing_subscription_attention()
        self.assertIn(expired, results)


class SubscriptionReminderHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="srh-bodi")
        self.platform_admin = User.objects.create_user(username="srh_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="srh_community_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_platform_admin_can_send_a_reminder_over_http(self):
        res = self._login("srh_platform_admin").post(f"/api/tenants/communities/{self.bodi.id}/send-subscription-reminder/", {"message": "test"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["sent_to_admin_count"], 1)

    def test_a_community_admin_cannot_send_a_reminder_over_http(self):
        res = self._login("srh_community_admin").post(f"/api/tenants/communities/{self.bodi.id}/send-subscription-reminder/", {}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_the_needing_attention_list_is_reachable_over_http(self):
        res = self._login("srh_platform_admin").get("/api/tenants/communities/needing-subscription-attention/")
        self.assertEqual(res.status_code, 200)

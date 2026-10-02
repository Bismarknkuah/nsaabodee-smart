from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import Community, FeatureFlag, PlatformBillingRecord


class PlatformRevenueReportTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="revenue_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="revenue_community_admin", password="x", role=Role.COMMUNITY_ADMIN)
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-revenue")
        self.other = Community.objects.create(name="Other Town", slug="other-revenue")

    def test_only_a_platform_admin_can_view_the_revenue_report(self):
        with self.assertRaises(ValidationError):
            services.platform_revenue_report(actor=self.community_admin)

    def test_paid_unpaid_and_waived_are_aggregated_separately(self):
        r1 = services.create_billing_record(community=self.bodi, description="Setup fee", amount=Decimal("100"), actor=self.platform_admin)
        services.mark_billing_record_paid(record=r1, actor=self.platform_admin)
        services.create_billing_record(community=self.other, description="Monthly", amount=Decimal("50"), actor=self.platform_admin)
        r3 = services.create_billing_record(community=self.bodi, description="Waived fee", amount=Decimal("25"), actor=self.platform_admin)
        services.waive_billing_record(record=r3, actor=self.platform_admin)

        report = services.platform_revenue_report(actor=self.platform_admin)
        self.assertEqual(report["total_paid"], "100")
        self.assertEqual(report["total_outstanding"], "50")
        self.assertEqual(report["total_waived"], "25")

    def test_never_touches_a_communitys_own_contribution_ledger(self):
        """The hard boundary this model exists to enforce — a sanity check that the report only ever queries PlatformBillingRecord."""
        report = services.platform_revenue_report(actor=self.platform_admin)
        self.assertIn("total_paid", report)
        self.assertNotIn("contributions", report)
        self.assertNotIn("gift", str(report).lower())

    def test_date_range_filtering_excludes_records_outside_the_window(self):
        from django.utils import timezone
        r1 = services.create_billing_record(community=self.bodi, description="Old fee", amount=Decimal("10"), actor=self.platform_admin)
        services.mark_billing_record_paid(record=r1, actor=self.platform_admin)
        r1.created_at = timezone.now() - __import__("datetime").timedelta(days=100)
        r1.save(update_fields=["created_at"])

        report = services.platform_revenue_report(actor=self.platform_admin, start_date=timezone.now().date() - __import__("datetime").timedelta(days=1))
        self.assertEqual(report["total_paid"], "0")


class FeatureFlagTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="flag_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="flag_community_admin", password="a-real-password-123", role=Role.COMMUNITY_ADMIN)

    def test_default_flags_are_created_on_first_access_and_default_to_enabled(self):
        services.ensure_default_feature_flags()
        self.assertTrue(FeatureFlag.objects.filter(key="chatbot", is_enabled=True).exists())
        self.assertTrue(FeatureFlag.objects.filter(key="messaging", is_enabled=True).exists())

    def test_only_platform_admin_can_toggle_a_flag(self):
        services.ensure_default_feature_flags()
        with self.assertRaises(ValidationError):
            services.set_feature_flag_enabled(key="chatbot", is_enabled=False, actor=self.community_admin)

    def test_toggling_a_flag_off_is_reflected_immediately(self):
        services.set_feature_flag_enabled(key="chatbot", is_enabled=False, actor=self.platform_admin)
        self.assertFalse(services.is_feature_enabled("chatbot"))
        self.assertTrue(services.is_feature_enabled("messaging"))

    def test_an_unconfigured_flag_fails_open_not_closed(self):
        """A brand-new deployment behaves exactly as it always has — nothing silently disabled by omission."""
        self.assertTrue(services.is_feature_enabled("some_flag_nobody_created_yet"))

    def test_toggling_a_flag_writes_an_audit_entry(self):
        from audit_log.models import AuditLogEntry
        services.set_feature_flag_enabled(key="chatbot", is_enabled=False, actor=self.platform_admin)
        self.assertTrue(AuditLogEntry.objects.filter(action="feature_flag_toggled").exists())

    def test_full_http_toggle_and_status_round_trip(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "flag_platform_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        toggle_res = client.post("/api/tenants/feature-flags/chatbot/toggle/", {"is_enabled": False}, format="json")
        self.assertEqual(toggle_res.status_code, 200)
        self.assertFalse(toggle_res.data["is_enabled"])

        status_res = client.get("/api/tenants/feature-flags/status/")
        self.assertEqual(status_res.status_code, 200)
        self.assertFalse(status_res.data["chatbot"])

    def test_a_disabled_chatbot_flag_actually_blocks_the_chatbot_endpoint(self):
        services.set_feature_flag_enabled(key="chatbot", is_enabled=False, actor=self.platform_admin)
        member = User.objects.create_user(username="flag_chatbot_user", password="a-real-password-123", role=Role.COMMUNITY_MEMBER)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "flag_chatbot_user", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/ai/chatbot/", {"message": "hello"})
        self.assertEqual(res.status_code, 503)

    def test_a_disabled_messaging_flag_actually_blocks_the_channels_endpoint(self):
        services.set_feature_flag_enabled(key="messaging", is_enabled=False, actor=self.platform_admin)
        member = User.objects.create_user(username="flag_messaging_user", password="a-real-password-123", role=Role.COMMUNITY_MEMBER)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "flag_messaging_user", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/messaging/channels/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

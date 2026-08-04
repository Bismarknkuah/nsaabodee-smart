from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts import services
from accounts.models import PhoneOTP, Role, User


class ResetPasswordWithOtpServiceTests(TestCase):
    """'Forgot password' — reuses the exact same phone verification already trusted for OTP sign-in, rather than a separate email flow this platform has no real infrastructure to send."""

    def setUp(self):
        self.user = User.objects.create_user(username="reset_test_user", password="old-password-123", phone_number="+233200000500", role=Role.COMMUNITY_MEMBER)

    def _create_otp(self, phone="+233200000500", code="123456", expires_in_minutes=10, attempts=0):
        return PhoneOTP.objects.create(phone_number=phone, code=code, expires_at=timezone.now() + timedelta(minutes=expires_in_minutes), attempts=attempts)

    def test_a_valid_code_actually_changes_the_password(self):
        self._create_otp()
        services.reset_password_with_otp("+233200000500", "123456", "a-brand-new-password-456")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-brand-new-password-456"))
        self.assertFalse(self.user.check_password("old-password-123"))

    def test_the_old_password_no_longer_works_after_a_reset(self):
        self._create_otp()
        services.reset_password_with_otp("+233200000500", "123456", "a-brand-new-password-456")
        client = APIClient()
        res = client.post("/api/auth/login/", {"username": "reset_test_user", "password": "old-password-123"})
        self.assertEqual(res.status_code, 401)

    def test_a_wrong_code_does_not_change_the_password(self):
        self._create_otp()
        with self.assertRaises(ValidationError):
            services.reset_password_with_otp("+233200000500", "000000", "a-brand-new-password-456")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-password-123"))

    def test_a_short_new_password_is_rejected(self):
        self._create_otp()
        with self.assertRaises(ValidationError):
            services.reset_password_with_otp("+233200000500", "123456", "short")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-password-123"))

    def test_the_same_code_cannot_be_used_twice(self):
        """Same one-time-use guarantee as OTP login — a code that already reset a password can't reset it again."""
        self._create_otp()
        services.reset_password_with_otp("+233200000500", "123456", "first-new-password-1")
        with self.assertRaises(ValidationError):
            services.reset_password_with_otp("+233200000500", "123456", "second-new-password-2")

    def test_resetting_with_no_account_on_that_number_fails_generically(self):
        self._create_otp(phone="+233200000999")
        with self.assertRaises(ValidationError):
            services.reset_password_with_otp("+233200000999", "123456", "a-brand-new-password-456")


class ResetPasswordWithOtpHttpTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reset_http_user", password="old-password-123", phone_number="+233200000600", role=Role.COMMUNITY_MEMBER)

    def test_full_reset_flow_via_http_signs_the_user_in_immediately(self):
        PhoneOTP.objects.create(phone_number="+233200000600", code="654321", expires_at=timezone.now() + timedelta(minutes=10))
        client = APIClient()
        res = client.post("/api/auth/otp/reset-password/", {
            "phone_number": "+233200000600", "code": "654321", "new_password": "a-genuinely-new-password-1",
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

        old_login = client.post("/api/auth/login/", {"username": "reset_http_user", "password": "old-password-123"})
        self.assertEqual(old_login.status_code, 401)
        new_login = client.post("/api/auth/login/", {"username": "reset_http_user", "password": "a-genuinely-new-password-1"})
        self.assertEqual(new_login.status_code, 200)

    def test_reset_endpoint_requires_no_login_at_all(self):
        client = APIClient()  # deliberately no credentials
        PhoneOTP.objects.create(phone_number="+233200000600", code="111111", expires_at=timezone.now() + timedelta(minutes=10))
        res = client.post("/api/auth/otp/reset-password/", {"phone_number": "+233200000600", "code": "111111", "new_password": "another-new-password-2"})
        self.assertEqual(res.status_code, 200)

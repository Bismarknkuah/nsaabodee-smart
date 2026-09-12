from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts import services
from accounts.models import PhoneOTP, Role, User

TWILIO_SETTINGS = dict(TWILIO_ACCOUNT_SID="AC_test", TWILIO_AUTH_TOKEN="token_test", TWILIO_FROM_NUMBER="+15005550006")


def _mock_twilio_success():
    return patch("requests.post", MagicMock(return_value=MagicMock(status_code=201, text='{"sid": "SM123"}')))


class RequestOtpServiceTests(TestCase):
    @override_settings(**TWILIO_SETTINGS)
    def test_requesting_an_otp_sends_a_real_looking_sms_and_stores_a_code(self):
        with _mock_twilio_success() as mock_post:
            services.request_otp("+233200000001")
        self.assertTrue(PhoneOTP.objects.filter(phone_number="+233200000001").exists())
        mock_post.assert_called_once()
        sent_body = mock_post.call_args.kwargs["data"]["Body"]
        otp = PhoneOTP.objects.get(phone_number="+233200000001")
        self.assertIn(otp.code, sent_body)

    @override_settings(**TWILIO_SETTINGS)
    def test_requesting_again_immediately_is_rate_limited(self):
        with _mock_twilio_success():
            services.request_otp("+233200000002")
            with self.assertRaises(ValidationError):
                services.request_otp("+233200000002")

    def test_requesting_with_no_phone_number_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.request_otp("")

    @override_settings(**TWILIO_SETTINGS)
    def test_requesting_never_reveals_whether_an_account_exists(self):
        """The whole point: succeeding or failing here must not depend on whether a real User uses this number."""
        User.objects.create_user(username="has_phone", password="x", phone_number="+233200000003")
        with _mock_twilio_success():
            services.request_otp("+233200000003")  # has an account
            services.request_otp("+233200000099")  # doesn't — both just succeed identically

    @override_settings(DEMO_MODE_ENABLED=True, TWILIO_ACCOUNT_SID=None, TWILIO_AUTH_TOKEN=None, TWILIO_FROM_NUMBER=None)
    def test_with_no_sms_provider_configured_and_demo_mode_on_the_code_is_returned_directly(self):
        """Real SMS delivery genuinely can't work without a paid Twilio account — demo mode is how phone+OTP sign-in stays testable without one."""
        returned_code = services.request_otp("+233200000010")
        self.assertIsNotNone(returned_code)
        stored = PhoneOTP.objects.get(phone_number="+233200000010")
        self.assertEqual(returned_code, stored.code)

    @override_settings(DEMO_MODE_ENABLED=False, TWILIO_ACCOUNT_SID=None, TWILIO_AUTH_TOKEN=None, TWILIO_FROM_NUMBER=None)
    def test_with_no_sms_provider_configured_and_demo_mode_off_a_real_error_is_raised(self):
        """The one thing that must never happen: a working login code silently handed back outside demo mode."""
        with self.assertRaises(ValidationError):
            services.request_otp("+233200000011")

    @override_settings(**TWILIO_SETTINGS, DEMO_MODE_ENABLED=True)
    def test_when_twilio_is_actually_configured_no_code_is_returned_even_in_demo_mode(self):
        """Demo mode is a fallback for when SMS ISN'T configured — a real, working provider always takes priority."""
        with _mock_twilio_success():
            returned_code = services.request_otp("+233200000012")
        self.assertIsNone(returned_code)


class VerifyOtpServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="phoneuser", password="x", phone_number="+233200000010", role=Role.COMMUNITY_MEMBER)

    def _create_otp(self, phone="+233200000010", code="123456", expires_in_minutes=10, attempts=0):
        return PhoneOTP.objects.create(
            phone_number=phone, code=code, expires_at=timezone.now() + timedelta(minutes=expires_in_minutes), attempts=attempts,
        )

    def test_the_correct_code_for_a_real_account_returns_that_user(self):
        self._create_otp()
        user = services.verify_otp("+233200000010", "123456")
        self.assertEqual(user.id, self.user.id)

    def test_the_wrong_code_is_rejected(self):
        self._create_otp()
        with self.assertRaises(ValidationError):
            services.verify_otp("+233200000010", "000000")

    def test_an_expired_code_is_rejected(self):
        self._create_otp(expires_in_minutes=-1)
        with self.assertRaises(ValidationError):
            services.verify_otp("+233200000010", "123456")

    def test_an_already_used_code_cannot_be_reused(self):
        self._create_otp()
        services.verify_otp("+233200000010", "123456")
        with self.assertRaises(ValidationError):
            services.verify_otp("+233200000010", "123456")

    def test_too_many_attempts_locks_out_the_code_even_with_the_right_answer_eventually(self):
        otp = self._create_otp(attempts=5)  # already at the max
        with self.assertRaises(ValidationError):
            services.verify_otp("+233200000010", "123456")

    def test_a_correct_code_for_a_phone_number_with_no_account_is_rejected(self):
        self._create_otp(phone="+233299999999", code="654321")
        with self.assertRaises(ValidationError):
            services.verify_otp("+233299999999", "654321")

    def test_wrong_and_right_codes_produce_the_exact_same_error_message(self):
        """Distinguishing 'wrong code' from 'no account' from 'expired' would itself leak information to an attacker."""
        self._create_otp(phone="+233299999998", code="111111")  # no account with this number
        expired = self._create_otp(expires_in_minutes=-1)
        try:
            services.verify_otp("+233299999998", "111111")
            self.fail("should have raised")
        except ValidationError as e1:
            try:
                services.verify_otp("+233200000010", "wrong-code")
                self.fail("should have raised")
            except ValidationError as e2:
                self.assertEqual(str(e1), str(e2))


class OtpHttpTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="httpphoneuser", password="x", phone_number="+233200000020", role=Role.COMMUNITY_MEMBER)

    @override_settings(**TWILIO_SETTINGS)
    def test_full_request_then_verify_flow_via_http(self):
        client = APIClient()
        with _mock_twilio_success():
            request_res = client.post("/api/auth/otp/request/", {"phone_number": "+233200000020"})
        self.assertEqual(request_res.status_code, 200)

        otp = PhoneOTP.objects.get(phone_number="+233200000020")
        verify_res = client.post("/api/auth/otp/verify/", {"phone_number": "+233200000020", "code": otp.code})
        self.assertEqual(verify_res.status_code, 200)
        self.assertIn("access", verify_res.data)
        self.assertIn("refresh", verify_res.data)

        # The issued token actually works for authenticated requests, same as a normal login.
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {verify_res.data['access']}")
        me = client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "httpphoneuser")

    def test_verifying_a_wrong_code_via_http_returns_400_not_500(self):
        client = APIClient()
        res = client.post("/api/auth/otp/verify/", {"phone_number": "+233200000020", "code": "000000"})
        self.assertEqual(res.status_code, 400)

    def test_username_password_login_still_works_unaffected(self):
        """Additive, not a replacement — the existing login path must be completely untouched."""
        client = APIClient()
        res = client.post("/api/auth/login/", {"username": "httpphoneuser", "password": "x"})
        self.assertEqual(res.status_code, 200)


class ProfilePhoneNumberTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="profilephoneuser", password="x")

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "profilephoneuser", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_setting_a_phone_number_on_your_own_profile(self):
        client = self._login()
        res = client.patch("/api/auth/me/", {"phone_number": "+233200000030"})
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "+233200000030")

    def test_cannot_set_a_phone_number_already_used_by_another_account(self):
        User.objects.create_user(username="other_phone_user", password="x", phone_number="+233200000040")
        client = self._login()
        res = client.patch("/api/auth/me/", {"phone_number": "+233200000040"})
        self.assertEqual(res.status_code, 400)

    def test_two_users_can_both_have_no_phone_number_without_a_conflict(self):
        """The empty-string-vs-NULL trap: clearing your phone number must never collide with someone else who also has none."""
        other = User.objects.create_user(username="another_no_phone_user", password="x")
        client = self._login()
        res = client.patch("/api/auth/me/", {"phone_number": ""})
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.phone_number)
        # And a second user also saving an empty phone number must not collide either.
        client2 = APIClient()
        login2 = client2.post("/api/auth/login/", {"username": "another_no_phone_user", "password": "x"})
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {login2.data['access']}")
        res2 = client2.patch("/api/auth/me/", {"phone_number": ""})
        self.assertEqual(res2.status_code, 200)

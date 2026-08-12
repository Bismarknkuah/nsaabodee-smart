from unittest.mock import MagicMock

from django.core import mail
from django.test import TestCase, override_settings

from communication.providers import (
    ConsoleProvider,
    EmailProvider,
    ProviderNotConfiguredError,
    SmsProvider,
    WhatsAppProvider,
)


class ConsoleProviderTests(TestCase):
    def test_console_provider_always_succeeds(self):
        result = ConsoleProvider().send(recipient_address="someone", subject="Hi", message="Test message")
        self.assertEqual(result.status, "sent")


class EmailProviderTests(TestCase):
    def test_email_provider_actually_sends_via_django_mail(self):
        """
        Django automatically switches EMAIL_BACKEND to locmem during
        tests regardless of what settings.py says, capturing everything
        in mail.outbox — so this test genuinely exercises the real
        send_mail() call this provider makes, not a mock of it.
        """
        result = EmailProvider().send(recipient_address="member@example.com", subject="Test Subject", message="Test body")
        self.assertEqual(result.status, "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["member@example.com"])
        self.assertEqual(mail.outbox[0].subject, "Test Subject")
        self.assertIn("Test body", mail.outbox[0].body)

    def test_email_provider_requires_an_address(self):
        with self.assertRaises(ProviderNotConfiguredError):
            EmailProvider().send(recipient_address="", subject="x", message="y")


class SmsProviderTests(TestCase):
    def test_raises_when_not_configured(self):
        with self.assertRaises(ProviderNotConfiguredError):
            SmsProvider().send(recipient_address="+233200000000", subject="x", message="y")

    @override_settings(TWILIO_ACCOUNT_SID="AC_test", TWILIO_AUTH_TOKEN="token_test", TWILIO_FROM_NUMBER="+15005550006")
    def test_sends_correctly_structured_request_when_configured(self):
        """
        No real network access to api.twilio.com exists in this
        environment (and no real account either) — this verifies the
        REQUEST this code would make is structurally correct against
        Twilio's documented API, by mocking the HTTP call itself rather
        than skipping the test.
        """
        mock_post = MagicMock(return_value=MagicMock(status_code=201, text='{"sid": "SM123"}'))
        provider = SmsProvider(http_post=mock_post)

        result = provider.send(recipient_address="+233200000000", subject="ignored", message="Payment received")

        self.assertEqual(result.status, "sent")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("AC_test", args[0])  # account SID is part of the URL path
        self.assertEqual(kwargs["auth"], ("AC_test", "token_test"))
        self.assertEqual(kwargs["data"]["From"], "+15005550006")
        self.assertEqual(kwargs["data"]["To"], "+233200000000")
        self.assertEqual(kwargs["data"]["Body"], "Payment received")

    @override_settings(TWILIO_ACCOUNT_SID="AC_test", TWILIO_AUTH_TOKEN="token_test", TWILIO_FROM_NUMBER="+15005550006")
    def test_reports_failed_status_on_http_error(self):
        mock_post = MagicMock(return_value=MagicMock(status_code=400, text="Bad request"))
        provider = SmsProvider(http_post=mock_post)
        result = provider.send(recipient_address="+233200000000", subject="x", message="y")
        self.assertEqual(result.status, "failed")


class WhatsAppProviderTests(TestCase):
    def test_raises_when_not_configured(self):
        with self.assertRaises(ProviderNotConfiguredError):
            WhatsAppProvider().send(recipient_address="+233200000000", subject="x", message="y")

    @override_settings(WHATSAPP_ACCESS_TOKEN="token_test", WHATSAPP_PHONE_NUMBER_ID="123456")
    def test_sends_correctly_structured_request_when_configured(self):
        mock_post = MagicMock(return_value=MagicMock(status_code=200, text='{"messages": [{"id": "wamid.123"}]}'))
        provider = WhatsAppProvider(http_post=mock_post)

        result = provider.send(recipient_address="+233200000000", subject="ignored", message="Payment received")

        self.assertEqual(result.status, "sent")
        args, kwargs = mock_post.call_args
        self.assertIn("123456", args[0])  # phone_number_id is part of the URL path
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token_test")
        self.assertEqual(kwargs["json"]["to"], "+233200000000")
        self.assertEqual(kwargs["json"]["text"]["body"], "Payment received")

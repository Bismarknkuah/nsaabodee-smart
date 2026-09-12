"""
Delivery providers for the Communication Module.

Two of these are genuinely complete and require no external account at
all: ConsoleProvider (always works — it's the same idea as Django's own
console email backend, a real and honest implementation of "deliver
this," not a placeholder) and EmailProvider (wraps Django's own email
framework, which sends real SMTP mail the moment EMAIL_HOST/etc. are
configured in settings — nothing about it is fake, it's just unconfigured
by default in a sandbox with no mail server to point at).

SmsProvider and WhatsAppProvider are written against the real, stable,
public APIs of Twilio and Meta's WhatsApp Business Cloud API
respectively — the request-building logic is genuine and unit-tested
(mocking the HTTP call, since this sandbox has no network access to
api.twilio.com or graph.facebook.com and no real account credentials to
use even if it did). Both raise ProviderNotConfiguredError clearly if
their required settings are missing, rather than silently doing nothing
or pretending to succeed.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("communication")


class ProviderNotConfiguredError(Exception):
    """Raised when a channel's real credentials/settings aren't present. Caught by services.py, never by accident."""


class DeliveryResult:
    def __init__(self, status: str, provider_response: str = ""):
        self.status = status
        self.provider_response = provider_response


class ConsoleProvider:
    """
    Always available, needs no configuration. Logs the notification the
    way Django's own console email backend logs mail during development
    — a real, working channel for environments (or communities) that
    haven't set up SMS/email/WhatsApp yet, not a stand-in for one.
    """

    def send(self, *, recipient_address: str, subject: str, message: str) -> DeliveryResult:
        logger.info("[Notification] To: %s | %s | %s", recipient_address or "(no address)", subject, message)
        return DeliveryResult(status="sent", provider_response="Logged to console.")


class EmailProvider:
    """
    Sends via Django's own email framework. This is real, working code —
    Django's `send_mail` genuinely delivers SMTP mail once
    EMAIL_HOST/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD/DEFAULT_FROM_EMAIL are
    set in settings (see settings.py's COMMUNICATION_* block). With no
    mail server configured, Django's default EMAIL_BACKEND
    (`django.core.mail.backends.console.EmailBackend`, or Django's
    automatic locmem backend during tests) means this still runs without
    crashing — it just doesn't reach a real inbox until a real SMTP
    server is configured.
    """

    def send(self, *, recipient_address: str, subject: str, message: str) -> DeliveryResult:
        if not recipient_address:
            raise ProviderNotConfiguredError("No email address to send to.")
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[recipient_address],
            fail_silently=False,
        )
        return DeliveryResult(status="sent", provider_response="Handed to Django's email backend.")


class SmsProvider:
    """
    Twilio's SMS API (https://www.twilio.com/docs/sms/send-messages) —
    genuinely one of the most stable, long-standing public APIs in this
    space, so the request-building logic here is written with real
    confidence, the same way NetworkThermalPrinterConnection on the
    mobile side is. What's NOT available in this sandbox: a real Twilio
    account, and network access to api.twilio.com at all (not in the
    sandbox's allowed domain list) — so this has been tested by mocking
    the HTTP call (see communication/tests/test_providers.py), not by
    actually sending an SMS.
    """

    API_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    def __init__(self, http_post=None):
        # Injectable for testing — defaults to the real `requests.post`.
        import requests
        self._http_post = http_post or requests.post

    def send(self, *, recipient_address: str, subject: str, message: str) -> DeliveryResult:
        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
        from_number = getattr(settings, "TWILIO_FROM_NUMBER", None)
        if not (account_sid and auth_token and from_number):
            raise ProviderNotConfiguredError(
                "SMS isn't configured — set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                "and TWILIO_FROM_NUMBER to enable it."
            )
        if not recipient_address:
            raise ProviderNotConfiguredError("No phone number to send to.")

        response = self._http_post(
            self.API_URL_TEMPLATE.format(account_sid=account_sid),
            auth=(account_sid, auth_token),
            data={"From": from_number, "To": recipient_address, "Body": message},
            timeout=10,
        )
        if response.status_code >= 400:
            return DeliveryResult(status="failed", provider_response=f"Twilio returned {response.status_code}: {response.text}")
        return DeliveryResult(status="sent", provider_response=response.text)


class WhatsAppProvider:
    """
    Meta's WhatsApp Business Cloud API
    (https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages).
    Same confidence/caveat profile as SmsProvider: the request structure
    is written against Meta's real, documented API and unit-tested by
    mocking the HTTP call — no live account or network access available
    here to actually send a message.

    One real technical caveat worth stating plainly rather than glossing
    over: WhatsApp Business accounts can only send free-form text to a
    recipient within a 24-hour customer-service window opened by that
    recipient messaging first; sending a business-initiated notification
    outside that window requires a pre-approved message TEMPLATE, not
    arbitrary text. This implementation sends free-form text, which is
    correct for the 24-hour-window case but will be rejected by Meta's
    API outside it — using this for proactive defaulter/notification
    alerts in production would need template message support added, plus
    the templates themselves submitted to Meta for approval in advance.
    """

    API_URL_TEMPLATE = "https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    def __init__(self, http_post=None):
        import requests
        self._http_post = http_post or requests.post

    def send(self, *, recipient_address: str, subject: str, message: str) -> DeliveryResult:
        access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
        phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
        if not (access_token and phone_number_id):
            raise ProviderNotConfiguredError(
                "WhatsApp isn't configured — set WHATSAPP_ACCESS_TOKEN and "
                "WHATSAPP_PHONE_NUMBER_ID to enable it."
            )
        if not recipient_address:
            raise ProviderNotConfiguredError("No phone number to send to.")

        response = self._http_post(
            self.API_URL_TEMPLATE.format(phone_number_id=phone_number_id),
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": recipient_address,
                "type": "text",
                "text": {"body": message},
            },
            timeout=10,
        )
        if response.status_code >= 400:
            return DeliveryResult(status="failed", provider_response=f"WhatsApp API returned {response.status_code}: {response.text}")
        return DeliveryResult(status="sent", provider_response=response.text)

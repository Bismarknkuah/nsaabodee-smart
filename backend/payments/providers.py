"""
Mobile Money collection via Paystack's own Charge API
(https://paystack.com/docs/api/charge/) — one unified integration
covering MTN, Vodafone, and AirtelTigo in Ghana, rather than this
platform maintaining a direct integration against MTN's own Collections
API alone. Written against Paystack's real, publicly documented API
shape, tested by mocking the HTTP calls since this sandbox has no
network route to api.paystack.co and no real secret key to use even if
it did.

The flow, mirroring the same two-step "kick it off, then find out what
actually happened" shape the previous MTN-direct integration already
used:
  1. Create Charge (POST /charge) — this doesn't return success/failure
     immediately for mobile money; "since payment is completed offline"
     (the customer authorizes on their own phone), the initial response
     status is typically `pay_offline` or, for MTN specifically,
     `send_otp` (needing one more step — see submit_otp below).
  2. The real outcome arrives either via Paystack's webhook (a
     `charge.success` / `charge.failed` event POSTed to a registered,
     publicly reachable URL — see payments/views.py's
     PaystackWebhookView, genuinely usable here since this platform has
     a real, public Railway URL, unlike MTN's own callback which this
     sandbox could never stand up) or by polling Check Pending Charge
     (GET /charge/:reference) — this implementation supports both.
"""

from decimal import Decimal

from django.conf import settings

API_BASE_URL = "https://api.paystack.co"


class ProviderNotConfiguredError(Exception):
    pass


class MomoProviderError(Exception):
    pass


class PaystackMomoProvider:
    """
    Same public interface the previous MTN-direct provider had
    (request_to_pay / check_status), so payments/services.py needed
    only its internal call sites changed, not its own shape — a
    deliberate choice to keep this swap as low-risk as a provider
    migration like this can be.
    """

    PROVIDER_CODES = {"mtn", "vod", "atl"}

    def __init__(self, http_post=None, http_get=None):
        import requests
        self._http_post = http_post or requests.post
        self._http_get = http_get or requests.get

    def _require_config(self) -> str:
        secret_key = getattr(settings, "PAYSTACK_SECRET_KEY", None)
        if not secret_key:
            raise ProviderNotConfiguredError(
                "Mobile Money collection isn't configured — set PAYSTACK_SECRET_KEY "
                "(from your Paystack Dashboard → Settings → API Keys & Webhooks) to enable it."
            )
        return secret_key

    def _headers(self, secret_key: str) -> dict:
        return {"Authorization": f"Bearer {secret_key}", "Content-Type": "application/json"}

    def request_to_pay(
        self, *, reference_id: str, amount: str, phone_number: str, payer_message: str = "",
        provider_code: str = "mtn", payer_email: str = "",
    ) -> dict:
        """
        Initiates the charge. A 200 response here means "Paystack
        accepted and is attempting the charge," not "the payment
        succeeded" — the real outcome is confirmed via webhook or
        check_status(), exactly as request_to_pay's previous MTN-direct
        version worked. Returns Paystack's own initial status string
        (e.g. 'pay_offline', 'send_otp', 'success', 'failed') under the
        'status' key, since the caller (see payments/services.py) needs
        to know if an OTP submission step is required next.
        """
        secret_key = self._require_config()
        provider_code = provider_code if provider_code in self.PROVIDER_CODES else "mtn"

        # Paystack requires amounts in the currency's smallest subunit
        # (pesewas for GHS — 100 pesewas = GH₵1), same convention as
        # every other real payment-gateway integration; this platform's
        # own Decimal amounts are always whole-and-fractional cedis.
        amount_in_pesewas = str(int((Decimal(amount) * 100).to_integral_value()))

        response = self._http_post(
            f"{API_BASE_URL}/charge",
            headers=self._headers(secret_key),
            json={
                "email": payer_email or f"{phone_number}@momo.nsaabodeesmart.local",
                "amount": amount_in_pesewas,
                "currency": "GHS",
                "reference": reference_id,
                "mobile_money": {"phone": phone_number, "provider": provider_code},
                "metadata": {"custom_fields": [{"display_name": "Purpose", "variable_name": "purpose", "value": payer_message}]},
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise MomoProviderError(f"Paystack charge request failed ({response.status_code}): {response.text}")
        body = response.json()
        data = body.get("data", {})
        return {"status": data.get("status", "pending"), "reference_id": reference_id, "raw": data}

    def submit_otp(self, *, reference_id: str, otp: str) -> dict:
        """
        MTN mobile money specifically routes through an OTP step —
        Paystack's own initial charge response comes back with
        status 'send_otp' when this is needed, at which point the
        payer's OTP (sent to their phone by MTN/Paystack) must be
        submitted here to actually complete the charge.
        """
        secret_key = self._require_config()
        response = self._http_post(
            f"{API_BASE_URL}/charge/submit_otp",
            headers=self._headers(secret_key),
            json={"otp": otp, "reference": reference_id},
            timeout=15,
        )
        if response.status_code >= 400:
            raise MomoProviderError(f"Paystack OTP submission failed ({response.status_code}): {response.text}")
        data = response.json().get("data", {})
        return {"status": data.get("status", "pending"), "reference_id": reference_id, "raw": data}

    def check_status(self, *, reference_id: str) -> str:
        """
        Returns this platform's own three-value status vocabulary
        (PENDING / SUCCESSFUL / FAILED — matching MomoPaymentRequest.
        Status), translated from whatever specific status string
        Paystack itself uses at that point in the flow (success,
        failed, pay_offline, send_otp, pending, and so on) — the rest
        of this platform never needs to know Paystack's own internal
        vocabulary, only this one already-established three-way result.
        """
        secret_key = self._require_config()
        response = self._http_get(
            f"{API_BASE_URL}/charge/{reference_id}",
            headers=self._headers(secret_key),
            timeout=15,
        )
        if response.status_code >= 400:
            raise MomoProviderError(f"Could not check Paystack charge status ({response.status_code}): {response.text}")
        data = response.json().get("data", {})
        paystack_status = data.get("status", "")
        if paystack_status == "success":
            return "SUCCESSFUL"
        if paystack_status == "failed":
            return "FAILED"
        return "PENDING"


def verify_paystack_webhook_signature(*, raw_body: bytes, signature_header: str) -> bool:
    """
    'x-paystack-signature' — HMAC-SHA512 of the raw request body, keyed
    with the account's own secret key. Verifying this before trusting
    anything in a webhook payload is the only thing standing between
    "a real Paystack event" and "anyone on the internet POSTing a fake
    charge.success to this URL" — see payments/views.py's
    PaystackWebhookView, which refuses to process a webhook that fails
    this check.
    """
    import hashlib
    import hmac

    secret_key = getattr(settings, "PAYSTACK_SECRET_KEY", None)
    if not secret_key or not signature_header:
        return False
    expected = hmac.new(secret_key.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature_header)

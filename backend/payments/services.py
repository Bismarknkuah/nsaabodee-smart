"""
Ties Mobile Money (via Paystack) into the exact same payment pipelines
every other method already goes through — a successful charge becomes
a real ContributionPayment (funerals.services.record_payment) or a
real GiftDonation (gifts.services.record_gift_donation) the same way a
cash payment does, never a parallel, separately-trusted code path.
Both ledgers can be paid via Mobile Money: a member settling their
mandatory contribution, or a guest/well-wisher — including one giving
to a specific registered donation-account holder — sending a gift.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from funerals.models import ContributionObligation, FuneralEvent
from members.models import Member
from .models import MomoPaymentRequest
from .providers import MomoProviderError, PaystackMomoProvider, ProviderNotConfiguredError


def _send_request_to_pay(request: MomoPaymentRequest, payer_message: str):
    try:
        result = PaystackMomoProvider().request_to_pay(
            reference_id=str(request.reference_id),
            amount=str(request.amount),
            phone_number=request.phone_number,
            payer_message=payer_message,
        )
    except (ProviderNotConfiguredError, MomoProviderError) as exc:
        request.status = MomoPaymentRequest.Status.FAILED
        request.provider_response = str(exc)
        request.save(update_fields=["status", "provider_response"])
        raise ValidationError(str(exc))

    # 'send_otp' is MTN mobile money's own extra step via Paystack —
    # everything else (pay_offline, pending, success) stays PENDING
    # here exactly like the previous MTN-direct integration did, with
    # the real outcome confirmed by webhook or check_status() below.
    if result["status"] == "send_otp":
        request.status = MomoPaymentRequest.Status.AWAITING_OTP
        request.provider_response = "awaiting_otp"
        request.save(update_fields=["status", "provider_response"])


def submit_momo_otp(*, request: MomoPaymentRequest, otp: str) -> MomoPaymentRequest:
    """The one extra step MTN mobile money (via Paystack) needs beyond every other provider — see PaystackMomoProvider.submit_otp."""
    if request.status != MomoPaymentRequest.Status.AWAITING_OTP:
        raise ValidationError("This payment isn't waiting for an OTP.")
    try:
        result = PaystackMomoProvider().submit_otp(reference_id=str(request.reference_id), otp=otp)
    except (ProviderNotConfiguredError, MomoProviderError) as exc:
        raise ValidationError(str(exc))

    if result["status"] == "success":
        return _finalize_as_successful(request, provider_response="success")
    if result["status"] == "failed":
        request.status = MomoPaymentRequest.Status.FAILED
        request.provider_response = "failed"
        request.save(update_fields=["status", "provider_response", "updated_at"])
        return request
    request.status = MomoPaymentRequest.Status.PENDING
    request.provider_response = result["status"]
    request.save(update_fields=["status", "provider_response", "updated_at"])
    return request


def initiate_momo_payment(*, obligation: ContributionObligation, phone_number: str, amount: Decimal, initiated_by=None) -> MomoPaymentRequest:
    """Mandatory contribution (Ledger 1) via Mobile Money — own-family or general rate, same as before."""
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    request = MomoPaymentRequest.objects.create(
        community=obligation.community,
        target_type=MomoPaymentRequest.TargetType.CONTRIBUTION,
        obligation=obligation,
        phone_number=phone_number,
        amount=amount,
        initiated_by=initiated_by,
    )
    _send_request_to_pay(request, f"Nsaabodeɛ contribution — {obligation.funeral_event.deceased_name}")
    return request


def initiate_momo_gift_payment(
    *, funeral: FuneralEvent, phone_number: str, amount: Decimal, donor_name: str,
    received_by_member: Member | None = None, initiated_by=None,
) -> MomoPaymentRequest:
    """
    Gift / donation (Ledger 2) via Mobile Money — a guest, a town
    leader, or a fellow member giving a voluntary gift, optionally
    earmarked to a specific registered donation-account holder
    (gifts.models.DonationAccountRegistration) the same way a cash gift
    can be. Unlike a mandatory contribution, there's no existing
    obligation row to attach this to — the GiftDonation itself only
    gets created once Paystack confirms the payment actually cleared
    (see check_and_finalize_momo_payment / the webhook handler).
    """
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    if received_by_member is not None:
        from gifts.models import DonationAccountRegistration
        is_registered = DonationAccountRegistration.objects.filter(
            funeral_event=funeral, member=received_by_member, is_active=True
        ).exists()
        if not is_registered:
            raise ValidationError(
                f"{received_by_member.full_name} hasn't registered as a donation-account holder for this funeral yet."
            )

    request = MomoPaymentRequest.objects.create(
        community=funeral.community,
        target_type=MomoPaymentRequest.TargetType.GIFT,
        funeral_event=funeral,
        donor_name=donor_name.strip(),
        received_by_member=received_by_member,
        phone_number=phone_number,
        amount=amount,
        initiated_by=initiated_by,
    )
    _send_request_to_pay(request, f"Gift for {funeral.deceased_name}'s funeral")
    return request


@transaction.atomic
def _finalize_as_successful(request: MomoPaymentRequest, *, provider_response: str) -> MomoPaymentRequest:
    """
    Shared by both confirmation paths (the webhook, and the polling
    fallback below) — using this request's own reference_id as the
    client_op_id for whichever ledger this finalizes into, so a
    payment confirmed twice (a webhook AND a poll both landing) can
    never double-credit either ledger, the same idempotency guarantee
    every other payment channel already has.
    """
    if request.status == MomoPaymentRequest.Status.SUCCESSFUL:
        return request  # already finalized — a second confirmation is a harmless no-op

    if request.target_type == MomoPaymentRequest.TargetType.CONTRIBUTION:
        from funerals.services import record_payment
        record_payment(
            obligation=request.obligation,
            amount=request.amount,
            method="mobile_money",
            client_op_id=str(request.reference_id),
        )
    else:
        from gifts.services import record_gift_donation
        record_gift_donation(
            funeral=request.funeral_event,
            donor_name=request.donor_name or "MoMo donor",
            amount_cash=request.amount,
            payment_method="mobile_money",
            received_by_member=request.received_by_member,
            client_op_id=str(request.reference_id),
        )
    request.status = MomoPaymentRequest.Status.SUCCESSFUL
    request.provider_response = provider_response
    request.save(update_fields=["status", "provider_response", "updated_at"])
    return request


@transaction.atomic
def check_and_finalize_momo_payment(request: MomoPaymentRequest) -> MomoPaymentRequest:
    """
    Polls Paystack for the real outcome and, the moment it's genuinely
    successful, records the actual ContributionPayment or GiftDonation
    via the platform's normal pipelines. This is the fallback path —
    the webhook (see payments/views.py's PaystackWebhookView) is the
    primary, faster way this platform actually finds out, now that a
    real, publicly reachable URL exists for Paystack to call back to.
    """
    if request.status not in (MomoPaymentRequest.Status.PENDING, MomoPaymentRequest.Status.AWAITING_OTP):
        return request  # already finalized one way or the other; nothing to do

    try:
        paystack_status = PaystackMomoProvider().check_status(reference_id=str(request.reference_id))
    except (ProviderNotConfiguredError, MomoProviderError) as exc:
        request.provider_response = str(exc)
        request.save(update_fields=["provider_response"])
        return request

    if paystack_status == "SUCCESSFUL":
        return _finalize_as_successful(request, provider_response=paystack_status)
    elif paystack_status == "FAILED":
        request.status = MomoPaymentRequest.Status.FAILED
        request.provider_response = paystack_status
        request.save(update_fields=["status", "provider_response", "updated_at"])
    return request

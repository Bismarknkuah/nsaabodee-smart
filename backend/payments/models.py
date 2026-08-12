import uuid

from django.conf import settings
from django.db import models


class MomoPaymentRequest(models.Model):
    """
    One "Request to Pay" sent to MTN MoMo's Collections API — the real
    difference between "a collector writes down that you paid MoMo
    after the fact" and "you pay from your own phone and the system
    knows the moment it clears." A member, guest, or collector triggers
    this; MTN's side then prompts the payer's phone for their MoMo PIN,
    and this record tracks the outcome.

    Supports TWO independent targets, exactly mirroring the platform's
    two ledgers:
      - `obligation` — a mandatory Ledger 1 contribution (own-family or
        general rate).
      - `funeral_event` (with `donor_name`/`received_by_member`) — a
        Ledger 2 gift/donation, which doesn't exist as a row yet because
        a gift is only ever created once payment is confirmed (unlike a
        ContributionObligation, which already exists before anyone pays
        it). Exactly one of `obligation` or `funeral_event` must be set —
        see `clean()`.

    Deliberately its own model rather than a field bolted onto either
    ContributionPayment or GiftDonation — a MoMo request can fail, time
    out, or sit PENDING before ever becoming a real payment, and none of
    that in-between state belongs on either ledger itself. Only a
    SUCCESSFUL request ever produces a real ContributionPayment or
    GiftDonation, via the exact same funerals.services.record_payment()
    / gifts.services.record_gift_donation() every other payment channel
    already goes through — see payments/services.py.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AWAITING_OTP = "awaiting_otp", "Awaiting OTP"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"

    class TargetType(models.TextChoices):
        CONTRIBUTION = "contribution", "Mandatory Contribution"
        GIFT = "gift", "Gift / Donation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    target_type = models.CharField(max_length=20, choices=TargetType.choices, default=TargetType.CONTRIBUTION)

    obligation = models.ForeignKey(
        "funerals.ContributionObligation", null=True, blank=True, on_delete=models.CASCADE, related_name="momo_requests"
    )

    # Only used when target_type == GIFT — there's no existing row to
    # attach a pending MoMo request to yet, so these carry everything
    # needed to create the GiftDonation once the payment clears.
    funeral_event = models.ForeignKey(
        "funerals.FuneralEvent", null=True, blank=True, on_delete=models.CASCADE, related_name="momo_gift_requests"
    )
    donor_name = models.CharField(max_length=255, blank=True)
    received_by_member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # MTN's own reference id for this request — required on every
    # subsequent status-check call, and used here as the client_op_id
    # for whichever ledger this finalizes into, so a MoMo payment can
    # never be double-recorded no matter how many times its status is
    # polled after it clears.
    reference_id = models.UUIDField(unique=True, default=uuid.uuid4)

    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_response = models.TextField(blank=True)

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(target_type="contribution", obligation__isnull=False, funeral_event__isnull=True)
                    | models.Q(target_type="gift", obligation__isnull=True, funeral_event__isnull=False)
                ),
                name="momo_request_has_exactly_one_target",
            )
        ]

    def __str__(self):
        return f"MoMo request {self.reference_id} — {self.amount} ({self.status})"

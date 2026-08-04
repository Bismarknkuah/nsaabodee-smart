import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class GiftDonation(models.Model):
    """
    Ledger 2 — Gift Donations. Deliberately its own model, its own table,
    and its own app: the master brief is explicit that mandatory
    contributions and gift donations must never be mixed. Nothing in this
    file references ContributionObligation/ContributionPayment, and
    nothing over there references this.

    A donation can be cash, a physical gift item, or both at once (e.g.
    "GH₵50 and a bag of rice") — `amount_cash` and `gift_item` /
    `estimated_item_value` are independent, not alternatives.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK = "bank", "Bank"
        OTHER = "other", "Other"
        NOT_APPLICABLE = "not_applicable", "Not Applicable (item only)"

    class DonorCategory(models.TextChoices):
        # The three ledgers this splits into for reporting: an ordinary
        # visiting sympathizer or well-wisher (GUEST); the town's chief
        # and elders, whose contributions a community wants tracked and
        # reported on separately out of respect for their standing
        # (TOWN_LEADER); and OTHER for everyone else who gives a gift —
        # most commonly a registered community member giving a gift on
        # top of their mandatory contribution, which is neither a
        # "guest" nor a "town leader" in the ceremonial sense.
        GUEST = "guest", "Guest"
        TOWN_LEADER = "town_leader", "Town Leader (King/Elder)"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    funeral_event = models.ForeignKey("funerals.FuneralEvent", on_delete=models.CASCADE, related_name="gift_donations")

    # Recipient is snapshotted from the funeral at creation time (usually
    # the deceased's family) rather than always inferred live, so a later
    # family rename/merge never rewrites who a past gift was recorded as
    # going to.
    recipient_family = models.ForeignKey("families.Family", on_delete=models.PROTECT, related_name="+")

    # The donor is NOT required to be a registered community member — a
    # sympathizer, a business, or someone from another town can give a
    # gift. If they ARE a member, linking donor_member lets their giving
    # history show up on their profile; donor_name/phone are always kept
    # too since they're what actually gets printed on the receipt.
    donor_name = models.CharField(max_length=255)
    donor_phone = models.CharField(max_length=20, blank=True)
    donor_member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="gift_donations_given"
    )
    donor_category = models.CharField(max_length=20, choices=DonorCategory.choices, default=DonorCategory.OTHER)

    # For a Guest specifically: where they've traveled from, and — the
    # detail that actually matters for a family wanting to know who to
    # thank — which of the deceased's relatives they attended because of
    # ("I'm here because of Kwame"). Free text, not a lookup against
    # Member: a visiting guest's connection is often to someone who
    # isn't in this system at all (an in-law from another town, a family
    # friend), so forcing a database match would make this unusable for
    # exactly the people it's meant to record.
    donor_hometown = models.CharField(max_length=255, blank=True)
    connected_relative_name = models.CharField(
        max_length=255, blank=True,
        help_text="The deceased's relative this guest attended on account of, as the cashier was told it.",
    )

    # Which registered donation-account holder physically received this
    # money on behalf of the bereaved family — see
    # DonationAccountRegistration below. Distinct from `collected_by`
    # (the User who operated the system to record the transaction):
    # received_by_member is the specific family-designated person the
    # money itself was handed to, which is what "any amount paid should
    # reflect on the person's dashboard" (the master brief's own framing
    # of transparency and accountability) is tracking. Optional — a
    # smaller funeral may not bother with formal donation-account
    # registration at all.
    received_by_member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="donations_received"
    )

    # Distinct from connected_relative_name (which relative of the
    # DECEASED they're here for): this is the donor's relationship to
    # the specific RECEIVER — "friend", "workmate", "in-law", "cousin".
    # The two can genuinely differ: a guest might be attending because
    # of one relative but choose to hand their gift to a different
    # registered receiver entirely. Free text for the same reason as
    # connected_relative_name — the real-world relationship someone
    # states rarely maps cleanly onto a fixed list of choices.
    relationship_to_recipient = models.CharField(
        max_length=100, blank=True,
        help_text="The donor's relationship to whoever received this gift (e.g. 'Friend', 'Cousin', 'Workmate').",
    )

    amount_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gift_item = models.CharField(max_length=255, blank=True, help_text="e.g. '2 bags of rice', 'a cow' — blank if cash only.")
    estimated_item_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    receipt_number = models.CharField(max_length=50, unique=True)

    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Idempotency key from the collecting device — same pattern as
    # ContributionPayment, for the same reason: an offline collector's
    # retried sync must never double-record a gift.
    client_op_id = models.UUIDField(unique=True, null=True, blank=True)

    given_at = models.DateTimeField(auto_now_add=True)
    printed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-given_at"]
        indexes = [
            models.Index(fields=["community", "funeral_event"]),
            models.Index(fields=["funeral_event", "donor_category"]),
            models.Index(fields=["given_at"]),
        ]

    def clean(self):
        if self.amount_cash <= 0 and not self.gift_item:
            raise ValidationError("A donation must have a cash amount, a gift item, or both.")
        if self.gift_item and self.estimated_item_value is None:
            raise ValidationError("A gift item needs an estimated value.")

    @property
    def total_value(self):
        return self.amount_cash + (self.estimated_item_value or 0)

    def __str__(self):
        return f"{self.donor_name} → {self.recipient_family.name} ({self.total_value})"


class DonationAccountRegistration(models.Model):
    """
    A person authorized to physically receive gift donations on behalf
    of a specific funeral's bereaved family — the master brief's own
    framing: "more than 1 person can receive for donation account, so
    all those who know will receive donations have to register."
    Registration is required BEFORE a gift can be attributed to that
    person (see gifts.services.record_gift_donation's validation) —
    that's what makes "who received what" an auditable fact rather than
    just trusting whoever happened to be holding cash at the time.

    Deliberately scoped to one funeral, not standing/permanent: a
    "temporary donation account," exactly as described — a person
    registered as a receiver for one funeral has no special status for
    any other funeral unless registered there too.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    funeral_event = models.ForeignKey(
        "funerals.FuneralEvent", on_delete=models.CASCADE, related_name="donation_account_registrations"
    )
    member = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="donation_account_registrations"
    )
    is_active = models.BooleanField(default=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(fields=["funeral_event", "member"], name="one_donation_registration_per_member_per_funeral")
        ]

    def __str__(self):
        return f"{self.member.full_name} — donation receiver for {self.funeral_event.deceased_name}"

"""
'Nsaabodeɛ Smart must not be limited to funeral contributions... any
family can also use it for welfare.' A genuinely parallel contribution
system to the funeral one (funerals.models.ContributionObligation/
ContributionPayment), deliberately mirroring its proven shape rather
than inventing a new one — same idea (a member owes a real, tracked
amount toward something specific, paid in one or more instalments),
generalized to any community-defined purpose instead of one tied to a
specific funeral, and with two distinct ways a "round" of billing can
be started.
"""
import uuid

from django.conf import settings
from django.db import models


class ContributionCategory(models.Model):
    """
    'The Community Administrator should be able to create unlimited
    contribution categories and configure...' — the reusable TEMPLATE
    a specific campaign is an instance of. Community Admin only,
    community-wide — a family cannot define its own category, only
    initiate a campaign under one the Community Admin has already set
    up (see ContributionCampaign below).
    """

    class Frequency(models.TextChoices):
        ONE_TIME = "one_time", "One-Time"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        ANNUAL = "annual", "Annual"

    class AmountType(models.TextChoices):
        FIXED = "fixed", "Fixed Amount"
        FLEXIBLE = "flexible", "Flexible Amount"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="contribution_categories")

    name = models.CharField(max_length=255)
    purpose = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=True)
    amount_type = models.CharField(max_length=20, choices=AmountType.choices, default=AmountType.FIXED)
    fixed_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    frequency = models.CharField(max_length=20, choices=Frequency.choices, default=Frequency.ONE_TIME)

    # "When a family head initiates it, it needs the approval of two
    # other family executives" — configurable per category rather than
    # a hardcoded constant, matching the same principle already
    # applied to funeral-opening approvals (tenants.Community.
    # required_funeral_approvals).
    required_family_approvals = models.PositiveSmallIntegerField(default=2)

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.community.name})"


class ContributionCampaign(models.Model):
    """
    One real "round" of billing under a category — 'monthly welfare
    contributions' isn't one campaign, it's a new one each month. Every
    WelfareObligation below belongs to exactly one campaign, which
    belongs to exactly one category, which is how "separate financial
    ledgers for each contribution category so that funds are never
    mixed" actually holds: filtering or grouping by category is always
    possible without ever touching another category's rows.

    family=None means community-wide ('when the community creates it,
    it affects all the community'); family set means exactly one
    family's own campaign ('when one family initiates it, it should
    only be within his jurisdiction') — obligations are only ever
    generated for that one family's own members, never anyone else's.
    """

    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        # 'Each family head should have the welfare contribution
        # features which has to be approved by the community admin
        # before it works for his community members.' Two distinct
        # gates for a family-initiated campaign, not one: the family's
        # own executives sign off first (existing, required_family_
        # approvals), landing here — then the community's own Community
        # Admin (or Temporary Admin, the same role) gives the final
        # sign-off before anyone is actually billed. A community-wide
        # campaign never passes through this state at all; it's active
        # immediately, the same as before.
        FAMILY_APPROVED = "family_approved", "Family-Approved, Awaiting Community Admin"
        ACTIVE = "active", "Active"
        REJECTED = "rejected", "Rejected"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(ContributionCategory, on_delete=models.CASCADE, related_name="campaigns")
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    family = models.ForeignKey(
        "families.Family", null=True, blank=True, on_delete=models.CASCADE, related_name="welfare_campaigns",
        help_text="Null for a community-wide campaign; set for a single family's own campaign.",
    )

    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        scope = self.family.name if self.family_id else "community-wide"
        return f"{self.title} ({scope})"


class CampaignApproval(models.Model):
    """
    Mirrors funerals.models.FuneralApproval exactly, but for a family's
    own executives rather than community-wide leadership — one row per
    distinct approver, counted toward the category's
    required_family_approvals before a family-initiated campaign
    actually activates and bills anyone.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(ContributionCampaign, on_delete=models.CASCADE, related_name="approvals")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["campaign", "approved_by"], name="one_welfare_approval_per_approver_per_campaign"),
        ]


class WelfareObligation(models.Model):
    """Mirrors funerals.models.ContributionObligation exactly — one row per (member, campaign)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    campaign = models.ForeignKey(ContributionCampaign, on_delete=models.CASCADE, related_name="obligations")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="welfare_obligations")

    expected_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["campaign", "member"], name="one_welfare_obligation_per_member_per_campaign"),
        ]

    @property
    def balance(self):
        return self.expected_amount - self.amount_paid

    @property
    def payment_status(self):
        if self.amount_paid <= 0:
            return "unpaid"
        if self.amount_paid < self.expected_amount:
            return "partial"
        return "paid"


class WelfarePayment(models.Model):
    """Mirrors funerals.models.ContributionPayment exactly — each instalment its own row."""

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK = "bank", "Bank"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obligation = models.ForeignKey(WelfareObligation, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices)
    receipt_number = models.CharField(max_length=50, unique=True)
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    client_op_id = models.UUIDField(unique=True, null=True, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]

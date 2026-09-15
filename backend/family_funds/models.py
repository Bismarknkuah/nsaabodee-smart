import uuid

from django.conf import settings
from django.db import models


class FamilyFund(models.Model):
    """
    A family's own, entirely private contribution scheme — "create their
    own contribution fund, which they can decide on any amount to pay,
    and that account shouldn't go to the community fund." Structurally
    isolated from every other ledger in this platform: no FK to
    ContributionObligation, GiftDonation, or anything community-wide.
    Multiple funds per family are allowed (a school-fees fund and a
    building fund can coexist) rather than forcing one undifferentiated
    pot.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey("families.Family", on_delete=models.CASCADE, related_name="funds")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.family.name} — {self.name}"


class FamilyFundContribution(models.Model):
    """
    Any member of the fund's own family paying ANY amount they choose —
    "decide on any amount to pay," no fixed rate, no minimum, unlike the
    community's mandatory Family/Community Ledgers. Gets the same
    receipt treatment (receipt_number, printable) as every other payment
    channel in this platform — see reports/receipts.py.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK = "bank", "Bank"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fund = models.ForeignKey(FamilyFund, on_delete=models.CASCADE, related_name="contributions")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="family_fund_contributions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    receipt_number = models.CharField(max_length=40, unique=True, blank=True)
    client_op_id = models.UUIDField(null=True, blank=True, unique=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]
        indexes = [models.Index(fields=["fund", "member"])]

    def __str__(self):
        return f"{self.member.full_name} -> {self.fund.name}: {self.amount}"


class FamilyFuneralExpense(models.Model):
    """
    "Any expenditure for the funeral will be documented... date an item
    was purchased, item name, the seller name, the contact of the
    seller, and the amount paid, and who paid the money." Scoped to a
    family AND a specific funeral — this is a family's own record of
    what it spent putting on a funeral, kept private the same way the
    Family Fund is, never merged into the community's own
    funeral_logistics.FuneralExpense (which is a separate, community
    -wide ledger the funeral committee manages — this one belongs to the
    family alone).

    "Anything bought has to be approved by the finance officer of the
    family" — every expense starts PENDING and only becomes real
    (counted, trusted) once the family's own treasurer (or Community
    Admin, for oversight) approves it. The secretary who recorded it and
    the family head can both see pending and rejected expenses too —
    "abusuapanin also oversees all activities" — but a pending expense
    is honestly labeled as not yet authorized, not silently treated the
    same as an approved one.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey("families.Family", on_delete=models.CASCADE, related_name="funeral_expenses")
    funeral_event = models.ForeignKey("funerals.FuneralEvent", on_delete=models.CASCADE, related_name="family_expenses")

    item_name = models.CharField(max_length=255)
    seller_name = models.CharField(max_length=255)
    seller_contact = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_purchased = models.DateField()
    paid_by_member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="funeral_expenses_paid",
        help_text="Which family member actually paid/disbursed the money for this purchase.",
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_purchased", "-created_at"]
        indexes = [models.Index(fields=["family", "funeral_event"])]

    def __str__(self):
        return f"{self.item_name} — {self.amount} ({self.status})"

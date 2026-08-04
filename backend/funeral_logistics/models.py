import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class FuneralExpense(models.Model):
    """
    The Expense Dashboard from the master brief: money spent BY the
    community FOR a funeral (catering, transport, coffin, venue, ...) —
    the mirror image of the contribution and gift ledgers, which are
    money coming IN. Kept as its own model/app rather than folded into
    `funerals` because its financial semantics are opposite in direction
    from both ledgers, and its own audit trail (who authorized this
    spend) matters independently of who paid what.
    """

    class Category(models.TextChoices):
        CATERING = "catering", "Catering"
        TRANSPORT = "transport", "Transport"
        COFFIN = "coffin", "Coffin"
        VENUE = "venue", "Venue / Canopy / Chairs"
        PRINTING = "printing", "Printing (posters, programs)"
        BURIAL_FEES = "burial_fees", "Cemetery / Burial Fees"
        OTHER = "other", "Other"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK = "bank", "Bank"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        # Deliberately separate from PaymentMethod above (HOW something
        # was or will be paid) — this is WHETHER it's actually been
        # settled. The spec's own list ("Cash Paid", "Mobile Money
        # Paid", "Bank Transfer") conflates the two; splitting them is
        # cleaner and actually answers "Credit payments create
        # liabilities" properly — a credit expense's payment_method
        # genuinely isn't decided yet, only its status is.
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        PAID = "paid", "Paid"
        PARTIAL = "partial", "Partially Paid"
        CREDIT = "credit", "Credit (Owed to Supplier)"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    funeral_event = models.ForeignKey("funerals.FuneralEvent", on_delete=models.CASCADE, related_name="expenses")

    description = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    voucher_number = models.CharField(max_length=50, unique=True)

    # "Item, Quantity, Unit price, Total amount" — all optional, since
    # not every real expense breaks down this way ("burial fees" is
    # just a lump sum with no unit price). When both are given, `amount`
    # is their product — see services.record_expense's auto-compute —
    # but `amount` alone (the existing, already-working path) is still
    # completely valid on its own.
    item_name = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    supplier_name = models.CharField(max_length=255, blank=True)
    buyer = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.TextField(blank=True)
    invoice = models.FileField(upload_to="expense_invoices/", null=True, blank=True)

    # "Payment status... Credit payments create liabilities." A brand
    # new expense defaults to PENDING_APPROVAL — the honest default,
    # since recording a spend and having it actually authorized are two
    # separate real-world moments — see services.decide_expense_status.
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_APPROVAL)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)

    incurred_on = models.DateField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    client_op_id = models.UUIDField(unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-incurred_on"]
        indexes = [models.Index(fields=["community", "funeral_event"])]

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Expense amount must be greater than zero.")

    def __str__(self):
        return f"{self.description} — {self.amount} ({self.funeral_event.deceased_name})"


class FuneralAttendance(models.Model):
    """
    The Attendance Dashboard from the master brief. An attendee is either
    a registered Member (checked off exactly once per funeral) or a
    guest recorded by name only — attendance tracking should never be a
    reason to force-register someone as a full community member.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    funeral_event = models.ForeignKey("funerals.FuneralEvent", on_delete=models.CASCADE, related_name="attendance_records")

    member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.CASCADE, related_name="funeral_attendance"
    )
    guest_name = models.CharField(max_length=255, blank=True)

    attended_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-attended_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["funeral_event", "member"],
                condition=models.Q(member__isnull=False),
                name="one_attendance_record_per_member_per_funeral",
            )
        ]
        indexes = [models.Index(fields=["community", "funeral_event"])]

    def clean(self):
        if not self.member_id and not self.guest_name.strip():
            raise ValidationError("An attendance record needs either a member or a guest name.")

    def __str__(self):
        return self.member.full_name if self.member_id else self.guest_name

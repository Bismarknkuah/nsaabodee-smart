"""
Expense tracking (money OUT) and attendance tracking for a funeral —
together with funerals.services (contributions) and gifts.services
(gift donations), this is what backs the five per-funeral dashboards the
master brief calls for: Bereaved (the FuneralEvent record itself),
Contribution, Gift, Expense, and Attendance.
"""

import secrets
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from funerals.models import FuneralEvent
from members.models import Member
from .models import FuneralAttendance, FuneralExpense


def _generate_voucher_number(community) -> str:
    prefix = f"{community.slug.upper()[:8]}-EXP-{timezone.now():%Y%m%d}"
    for _ in range(5):
        candidate = f"{prefix}-{secrets.token_hex(3).upper()}"
        if not FuneralExpense.objects.filter(voucher_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique voucher number; please retry.")


@transaction.atomic
def record_expense(
    *, funeral: FuneralEvent, description: str, category: str, incurred_on,
    amount: Decimal = None, quantity: int = None, unit_price: Decimal = None,
    payment_method: str = FuneralExpense.PaymentMethod.CASH,
    item_name: str = "", supplier_name: str = "", buyer=None, notes: str = "", invoice=None,
    recorded_by=None, client_op_id=None,
):
    """
    'Item, Quantity, Unit price, Total amount.' When both quantity and
    unit_price are given, amount is computed as their product — the
    honest, arithmetic-checked total rather than trusting two numbers
    to agree. Passing `amount` directly (the original, already-working
    path) is still completely valid on its own for expenses that don't
    break down into a unit price at all.
    """
    if client_op_id:
        existing = FuneralExpense.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing

    if amount is None:
        if quantity is None or unit_price is None:
            raise ValidationError("Either an amount, or both a quantity and a unit price, are required.")
        amount = Decimal(quantity) * unit_price

    expense = FuneralExpense(
        community=funeral.community,
        funeral_event=funeral,
        description=description.strip(),
        category=category,
        amount=amount,
        quantity=quantity,
        unit_price=unit_price,
        item_name=item_name.strip(),
        supplier_name=supplier_name.strip(),
        buyer=buyer,
        notes=notes.strip(),
        invoice=invoice,
        payment_method=payment_method,
        incurred_on=incurred_on,
        recorded_by=recorded_by,
        client_op_id=client_op_id,
    )
    expense.full_clean(exclude=["voucher_number"])

    try:
        expense.voucher_number = _generate_voucher_number(funeral.community)
        expense.save()
    except IntegrityError:
        if client_op_id:
            existing = FuneralExpense.objects.filter(client_op_id=client_op_id).first()
            if existing:
                return existing
        raise ValidationError("Could not save this expense — please retry.")

    return expense


def decide_expense_status(*, expense: FuneralExpense, status: str, amount_paid: Decimal = None, actor=None) -> FuneralExpense:
    """
    'Payment status... Credit payments create liabilities.' The same
    authority already required to record an expense in the first
    place (CanRecordExpenses, checked at the view) governs changing
    its status — a Community Admin, Treasurer, or Financial Secretary
    approves it out of Pending Approval, marks a Credit as later paid,
    or records a Partial payment's running total.

    'The system must enforce maker-checker (dual approval) controls
    for sensitive financial... operations' — whoever recorded this
    expense (the "maker") can never also be the one who approves it
    out of Pending Approval (the "checker"), even if they otherwise
    hold the authority to do so.
    """
    if status not in FuneralExpense.Status.values:
        raise ValidationError(f"'{status}' isn't a real expense status.")
    if status == FuneralExpense.Status.PARTIAL and amount_paid is None:
        raise ValidationError("A partial payment needs the amount actually paid so far.")
    if expense.status == FuneralExpense.Status.PENDING_APPROVAL and actor is not None and expense.recorded_by_id == actor.id:
        raise ValidationError("You recorded this expense — someone else must approve it.")

    expense.status = status
    if amount_paid is not None:
        if amount_paid < 0 or amount_paid > expense.amount:
            raise ValidationError("The amount paid must be between zero and the expense's total amount.")
        expense.amount_paid = amount_paid
    elif status == FuneralExpense.Status.PAID:
        expense.amount_paid = expense.amount
    elif status in (FuneralExpense.Status.CREDIT, FuneralExpense.Status.PENDING_APPROVAL, FuneralExpense.Status.CANCELLED):
        expense.amount_paid = Decimal("0")

    if status != FuneralExpense.Status.PENDING_APPROVAL:
        expense.approved_by = actor
        expense.approved_at = timezone.now()
    expense.save(update_fields=["status", "amount_paid", "approved_by", "approved_at"])
    return expense


def list_expense_liabilities(*, community) -> list:
    """'Credit payments create liabilities' — every expense the community currently owes a supplier for, community-wide, not just one funeral at a time."""
    return list(
        FuneralExpense.objects.filter(community=community, status__in=[FuneralExpense.Status.CREDIT, FuneralExpense.Status.PARTIAL])
        .select_related("funeral_event")
        .order_by("-incurred_on")
    )


def expense_summary(funeral: FuneralEvent) -> dict:
    """
    A cancelled expense never happened, financially speaking — it's
    excluded from the real total and category breakdown the same way
    a rejected payment reversal is excluded from collections. Still
    counted separately below so a cancelled record doesn't just
    silently vanish from the picture.
    """
    all_expenses = funeral.expenses.all()
    real_expenses = all_expenses.exclude(status=FuneralExpense.Status.CANCELLED)
    total = sum((e.amount for e in real_expenses), Decimal("0"))
    total_owed = sum((e.amount - e.amount_paid for e in real_expenses), Decimal("0"))
    by_category = {}
    for e in real_expenses:
        by_category[e.category] = by_category.get(e.category, Decimal("0")) + e.amount
    return {
        "funeral_id": str(funeral.id),
        "expense_count": real_expenses.count(),
        "cancelled_count": all_expenses.filter(status=FuneralExpense.Status.CANCELLED).count(),
        "total_expenses": str(total),
        "total_owed": str(total_owed),
        "by_category": {k: str(v) for k, v in by_category.items()},
    }


def community_expenses_overview(community) -> list:
    """
    'The funeral expenses should have its own link to be one of the
    multiple tasks.' A real, dedicated entry point into expenses
    across every currently active funeral, not something only
    reachable by first opening one specific funeral's own detail page
    — distinct from list_expense_liabilities above, which only ever
    shows outstanding/credit expenses; this shows every active
    funeral's real total, regardless of whether it's fully paid.
    """
    active_funerals = FuneralEvent.objects.filter(community=community, status=FuneralEvent.Status.ACTIVE)
    return [
        {**expense_summary(funeral), "deceased_name": funeral.deceased_name, "deceased_family_name": funeral.deceased_family.name}
        for funeral in active_funerals
    ]


@transaction.atomic
def record_attendance(*, funeral: FuneralEvent, member: Member | None = None, guest_name: str = "", recorded_by=None):
    if member is None and not guest_name.strip():
        raise ValidationError("Provide either a member or a guest name.")
    if member is not None and member.community_id != funeral.community_id:
        raise ValidationError("The member must belong to this community.")

    if member is not None:
        existing = FuneralAttendance.objects.filter(funeral_event=funeral, member=member).first()
        if existing:
            return existing  # already checked in — recording again is a no-op, not an error

    record = FuneralAttendance(
        community=funeral.community,
        funeral_event=funeral,
        member=member,
        guest_name="" if member is not None else guest_name.strip(),
        recorded_by=recorded_by,
    )
    record.full_clean()
    record.save()
    return record


def attendance_summary(funeral: FuneralEvent) -> dict:
    records = funeral.attendance_records.select_related("member")
    member_records = [r for r in records if r.member_id is not None]
    guest_records = [r for r in records if r.member_id is None]

    from contribution_rules.services import eligible_members_queryset
    obligated_count = eligible_members_queryset(funeral.community).count()

    return {
        "funeral_id": str(funeral.id),
        "members_attended": len(member_records),
        "obligated_member_count": obligated_count,
        "guests_attended": len(guest_records),
        "guest_names": [r.guest_name for r in guest_records],
    }


def funeral_financial_overview(funeral: FuneralEvent) -> dict:
    """
    A read-only aggregation across all three financial pictures for a
    funeral — mandatory contributions collected, gift cash collected, and
    expenses paid out — for a single "how did this funeral come out
    financially" figure. This NEVER merges the underlying ledgers or
    changes how any of the three record data; it only sums totals that
    already exist independently, the same way a bank statement's summary
    page doesn't merge your checking and savings accounts into one.
    """
    from funerals.services import funeral_summary
    from gifts.services import gift_summary

    contributions = funeral_summary(funeral)
    gifts = gift_summary(funeral)
    expenses = expense_summary(funeral)

    contributions_collected = Decimal(contributions["own_family"]["collected_total"]) + Decimal(
        contributions["general"]["collected_total"]
    )
    gift_cash_collected = Decimal(gifts["total_cash"])
    total_expenses = Decimal(expenses["total_expenses"])

    return {
        "funeral_id": str(funeral.id),
        "contributions_collected": str(contributions_collected),
        "gift_cash_collected": str(gift_cash_collected),
        "gift_estimated_item_value": gifts["total_estimated_item_value"],
        "total_expenses": str(total_expenses),
        "net_cash_position": str(contributions_collected + gift_cash_collected - total_expenses),
    }

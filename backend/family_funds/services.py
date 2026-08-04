"""
A family's entirely private contribution fund — no FK anywhere in this
module points at ContributionObligation, ContributionPayment, or
GiftDonation. That's deliberate: "that account shouldn't go to the
community fund" is enforced by this module simply never importing those
models, the same schema-level isolation gifts/ already uses to keep
Ledger 2 separate from Ledger 1.
"""

import secrets
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from members.models import Member
from .models import FamilyFund, FamilyFundContribution, FamilyFuneralExpense


def _generate_receipt_number(family) -> str:
    prefix = f"{family.slug.upper()[:12]}-FUND-{timezone.now():%Y%m%d}"
    for _ in range(5):
        candidate = f"{prefix}-{secrets.token_hex(3).upper()}"
        if not FamilyFundContribution.objects.filter(receipt_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique fund receipt number; please retry.")


def create_family_fund(*, family, name, description="", actor=None):
    fund = FamilyFund.objects.create(
        family=family, name=name.strip(), description=description.strip(), created_by=actor,
    )
    return fund


def deactivate_family_fund(*, fund: FamilyFund, actor=None):
    fund.is_active = False
    fund.save(update_fields=["is_active"])
    return fund


@transaction.atomic
def record_fund_contribution(*, fund: FamilyFund, member: Member, amount, payment_method=FamilyFundContribution.PaymentMethod.CASH,
                              recorded_by=None, client_op_id=None):
    if not fund.is_active:
        raise ValidationError("This fund is no longer active.")
    if member.family_id != fund.family_id:
        raise ValidationError("Only members of this family can contribute to its own fund.")
    if amount <= 0:
        raise ValidationError("Contribution amount must be greater than zero.")

    if client_op_id:
        existing = FamilyFundContribution.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing

    contribution = FamilyFundContribution(
        fund=fund, member=member, amount=amount, payment_method=payment_method,
        recorded_by=recorded_by, client_op_id=client_op_id,
    )
    contribution.full_clean(exclude=["receipt_number"])
    try:
        contribution.receipt_number = _generate_receipt_number(fund.family)
        contribution.save()
    except IntegrityError:
        if client_op_id:
            existing = FamilyFundContribution.objects.filter(client_op_id=client_op_id).first()
            if existing:
                return existing
        raise ValidationError("Could not save this contribution — please retry.")
    return contribution


def fund_summary(fund: FamilyFund) -> dict:
    from django.db.models import Sum
    contributions = fund.contributions.all()
    total = contributions.aggregate(total=Sum("amount"))["total"] or 0
    return {
        "fund_id": str(fund.id),
        "fund_name": fund.name,
        "is_active": fund.is_active,
        "contribution_count": contributions.count(),
        "contributor_count": contributions.values("member_id").distinct().count(),
        "total_collected": str(total),
    }


def funds_for_family(family):
    return FamilyFund.objects.filter(family=family)


# --- Family Funeral Expense Tracking (secretary records, treasurer approves) ---

def record_funeral_expense(*, family, funeral_event, item_name, seller_name, amount, date_purchased,
                            seller_contact="", paid_by_member=None, recorded_by=None):
    """
    'The family head is not allowed to purchase any items, his own is
    to review, reject or approve items bought.' Recording a purchase is
    deliberately narrower than "any family officer" (which is what
    grants read access to this family's own expenses) — the Head can
    review everything here, but can never be the one entering a new
    expense; that's Family Secretary/Treasurer, or Community Admin+.
    """
    if funeral_event.deceased_family_id != family.id:
        raise ValidationError("A family can only record expenses for its own funeral.")
    if paid_by_member is not None and paid_by_member.family_id != family.id:
        raise ValidationError("Whoever paid must be a member of this family.")
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if recorded_by is not None and not recorded_by.is_superuser and not recorded_by.can_manage_families():
        recorder_member = getattr(recorded_by, "member_profile", None)
        if recorder_member is not None and recorder_member.id == family.family_head_id:
            raise ValidationError("The Family Head reviews, approves, or rejects purchases — recording a new one is for Family Secretary or Treasurer.")

    expense = FamilyFuneralExpense.objects.create(
        family=family, funeral_event=funeral_event, item_name=item_name.strip(),
        seller_name=seller_name.strip(), seller_contact=seller_contact.strip(), amount=amount,
        date_purchased=date_purchased, paid_by_member=paid_by_member, recorded_by=recorded_by,
    )
    _notify_finance_officers_of_pending_expense(expense)
    return expense


def approve_funeral_expense(*, expense: FamilyFuneralExpense, actor=None):
    """"Anything bought has to be approved by the finance officer of the family" — this is that approval."""
    if expense.status != FamilyFuneralExpense.Status.PENDING:
        raise ValidationError("Only a pending expense can be approved.")
    expense.status = FamilyFuneralExpense.Status.APPROVED
    expense.approved_by = actor
    expense.approved_at = timezone.now()
    expense.save(update_fields=["status", "approved_by", "approved_at"])
    _notify_recorder_of_expense_decision(expense)
    return expense


def reject_funeral_expense(*, expense: FamilyFuneralExpense, actor=None, reason=""):
    if expense.status != FamilyFuneralExpense.Status.PENDING:
        raise ValidationError("Only a pending expense can be rejected.")
    expense.status = FamilyFuneralExpense.Status.REJECTED
    expense.approved_by = actor
    expense.approved_at = timezone.now()
    expense.rejection_reason = reason.strip()
    expense.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason"])
    _notify_recorder_of_expense_decision(expense)
    return expense


def _notify_finance_officers_of_pending_expense(expense: FamilyFuneralExpense):
    """
    "The finance officer should oversee... to see what's going on" — a
    finance officer who has to remember to keep checking a list is worse
    oversight than one who gets told the moment something needs their
    decision. Notifies both the treasurer and the head (whichever of
    them has an actual login linked) — either can approve, so either
    should know.
    """
    from notifications.models import Notification
    family = expense.family
    recipients = {
        member.linked_user for member in (family.family_treasurer, family.family_head)
        if member is not None and getattr(member, "linked_user_id", None)
    }
    message = (
        f"[{family.name}] New expense awaiting your approval: {expense.item_name} "
        f"(GH₵{expense.amount}) from {expense.seller_name}."
    )
    for user in recipients:
        notification = Notification.objects.create(
            community=family.community, category=Notification.Category.FAMILY_EXPENSE_APPROVAL,
            message=message, recipient_user=user, related_member=expense.paid_by_member,
        )
        _deliver(notification)


def _notify_recorder_of_expense_decision(expense: FamilyFuneralExpense):
    """Closes the loop for the secretary who recorded it — they shouldn't have to keep re-checking the list either."""
    if expense.recorded_by is None:
        return
    from notifications.models import Notification
    verdict = "approved" if expense.status == FamilyFuneralExpense.Status.APPROVED else "rejected"
    message = f"[{expense.family.name}] Your recorded expense '{expense.item_name}' was {verdict}."
    if expense.status == FamilyFuneralExpense.Status.REJECTED and expense.rejection_reason:
        message += f" Reason: {expense.rejection_reason}"
    notification = Notification.objects.create(
        community=expense.family.community, category=Notification.Category.FAMILY_EXPENSE_APPROVAL,
        message=message, recipient_user=expense.recorded_by, related_member=expense.paid_by_member,
    )
    _deliver(notification)


def _deliver(notification):
    """Same real-delivery path as notifications.services._deliver — async via Celery, never blocking the request that triggered it."""
    from communication.tasks import deliver_notification_task
    deliver_notification_task.delay(str(notification.id))


def funeral_expenses_for_family(family, funeral_event=None):
    qs = FamilyFuneralExpense.objects.filter(family=family).select_related("paid_by_member", "recorded_by", "approved_by")
    if funeral_event is not None:
        qs = qs.filter(funeral_event=funeral_event)
    return qs


def funeral_expenditure_summary(family, funeral_event=None) -> dict:
    """"The system should be able to calculate all expenditures for the funds spent" — split by
    approval status, since a pending expense isn't authorized spend yet, just a proposed one."""
    from django.db.models import Sum
    qs = funeral_expenses_for_family(family, funeral_event)

    def _bucket(status):
        matching = qs.filter(status=status)
        return {
            "count": matching.count(),
            "total": str(matching.aggregate(total=Sum("amount"))["total"] or 0),
        }

    return {
        "family_id": str(family.id),
        "pending": _bucket(FamilyFuneralExpense.Status.PENDING),
        "approved": _bucket(FamilyFuneralExpense.Status.APPROVED),
        "rejected": _bucket(FamilyFuneralExpense.Status.REJECTED),
        "total_all_recorded": str(qs.aggregate(total=Sum("amount"))["total"] or 0),
    }


def family_financial_overview(family, funeral_event=None) -> dict:
    """
    "Abusuapanin also oversees all activities" — one combined picture
    rather than making him piece it together from the Fund page and the
    Expenses page separately: everything the family's own funds have
    raised, against everything actually approved to be spent (pending
    expenses are deliberately excluded from `net_position` — they aren't
    real spend yet, just proposed), giving a genuine "how much do we
    actually have left" figure.
    """
    from django.db.models import Sum

    total_fund_contributions = FamilyFundContribution.objects.filter(fund__family=family).aggregate(
        total=Sum("amount")
    )["total"] or 0

    expenditure = funeral_expenditure_summary(family, funeral_event)

    total_approved_expenses = Decimal(expenditure["approved"]["total"])
    net_position = Decimal(str(total_fund_contributions)) - total_approved_expenses

    return {
        "family_id": str(family.id),
        "family_name": family.name,
        "total_fund_contributions": str(total_fund_contributions),
        "total_approved_expenses": str(total_approved_expenses),
        "total_pending_expenses": expenditure["pending"]["total"],
        "net_position": str(net_position),
    }

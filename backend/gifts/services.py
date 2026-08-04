"""
Ledger 2 — Gift Donations. Recording a gift never touches, reads, or
influences Ledger 1 (mandatory contributions) in any way — see
gifts.models.GiftDonation for why that separation is enforced at the
schema level, not just by convention.
"""

import secrets
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from funerals.models import FuneralEvent
from members.models import Member
from .models import DonationAccountRegistration, GiftDonation


def _generate_receipt_number(community) -> str:
    prefix = f"{community.slug.upper()[:8]}-GIFT-{timezone.now():%Y%m%d}"
    for _ in range(5):
        candidate = f"{prefix}-{secrets.token_hex(3).upper()}"
        if not GiftDonation.objects.filter(receipt_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique gift receipt number; please retry.")


@transaction.atomic
def record_gift_donation(
    *, funeral: FuneralEvent, donor_name: str, donor_phone: str = "", donor_member: Member | None = None,
    amount_cash: Decimal = Decimal("0"), gift_item: str = "", estimated_item_value: Decimal | None = None,
    payment_method: str = GiftDonation.PaymentMethod.CASH, collected_by=None, client_op_id=None,
    recipient_family=None, donor_category: str | None = None, donor_hometown: str = "",
    connected_relative_name: str = "", received_by_member: Member | None = None,
    relationship_to_recipient: str = "",
):
    if funeral.status == FuneralEvent.Status.CANCELLED:
        raise ValidationError("Cannot record a gift for a cancelled funeral.")

    if client_op_id:
        existing = GiftDonation.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing

    if donor_member is not None and donor_member.community_id != funeral.community_id:
        raise ValidationError("The donor's member record must belong to this community.")

    recipient = recipient_family or funeral.deceased_family
    if recipient.community_id != funeral.community_id:
        raise ValidationError("The recipient family must belong to this community.")

    # "All those who know will receive donations have to register of
    # donation account" — a gift can only be attributed to someone who
    # has actually registered as a receiver for THIS funeral. This is
    # what makes the accountability real rather than just a label: you
    # can't retroactively claim you received money you were never
    # authorized to receive in the first place.
    if received_by_member is not None:
        is_registered = DonationAccountRegistration.objects.filter(
            funeral_event=funeral, member=received_by_member, is_active=True
        ).exists()
        if not is_registered:
            raise ValidationError(
                f"{received_by_member.full_name} hasn't registered as a donation-account holder "
                "for this funeral yet — register them first, then attribute the gift to them."
            )

    # An item-only gift was never handed over as cash, so it shouldn't
    # silently inherit the "cash" default meant for cash donations — that
    # would misclassify its receipt as needing a physical cash handoff
    # when none occurred (see reports/receipts.py's delivery_channel).
    if amount_cash <= 0 and payment_method == GiftDonation.PaymentMethod.CASH:
        payment_method = GiftDonation.PaymentMethod.NOT_APPLICABLE

    # A donor with no Member record is, by default, a Guest (exactly the
    # "their name isn't in the database" case) — the cashier can still
    # explicitly mark them as a Town Leader instead. A donor who IS a
    # registered member defaults to "other," since a fellow member
    # giving an extra gift on top of their mandatory contribution isn't
    # ceremonially a "guest" or "town leader" unless someone says so.
    if donor_category is None:
        donor_category = GiftDonation.DonorCategory.OTHER if donor_member else GiftDonation.DonorCategory.GUEST

    donation = GiftDonation(
        community=funeral.community,
        funeral_event=funeral,
        recipient_family=recipient,
        donor_name=donor_name.strip(),
        donor_phone=donor_phone,
        donor_member=donor_member,
        donor_category=donor_category,
        donor_hometown=donor_hometown.strip(),
        connected_relative_name=connected_relative_name.strip(),
        received_by_member=received_by_member,
        relationship_to_recipient=relationship_to_recipient.strip(),
        amount_cash=amount_cash,
        gift_item=gift_item.strip(),
        estimated_item_value=estimated_item_value,
        payment_method=payment_method,
        collected_by=collected_by,
        client_op_id=client_op_id,
    )
    donation.full_clean(exclude=["receipt_number"])

    try:
        donation.receipt_number = _generate_receipt_number(funeral.community)
        donation.save()
    except IntegrityError:
        if client_op_id:
            existing = GiftDonation.objects.filter(client_op_id=client_op_id).first()
            if existing:
                return existing
        raise ValidationError("Could not save this gift donation — please retry.")

    return donation


def all_receivers_donation_lists(funeral: FuneralEvent) -> list[dict]:
    """
    "After the funeral all [receivers] should be able to print receipts
    to all those who received donations" — the family head/admin version:
    every registered receiver for this funeral, each with their own full
    donor list (same shape as donations_received_by_member's `entries`),
    grouped so a single printable statement can show "Adwoa's donors,
    then Yaw's donors" without mixing the two — donations to Adwoa are
    Adwoa's own accountability record, not something that gets blended
    into a shared pool just because they're printed together here.
    """
    registrations = DonationAccountRegistration.objects.filter(
        funeral_event=funeral, is_active=True
    ).select_related("member")

    result = []
    for reg in registrations:
        received = donations_received_by_member(reg.member, funeral=funeral)
        result.append({
            "member_id": str(reg.member_id),
            "member_name": reg.member.full_name,
            "donation_count": received["donation_count"],
            "total_received": received["total_received"],
            "entries": received["entries"],
        })
    return result


def gift_summary(funeral: FuneralEvent) -> dict:
    donations = funeral.gift_donations.all()
    total_cash = sum((d.amount_cash for d in donations), Decimal("0"))
    total_item_value = sum((d.estimated_item_value or Decimal("0") for d in donations), Decimal("0"))
    return {
        "funeral_id": str(funeral.id),
        "donation_count": donations.count(),
        "total_cash": str(total_cash),
        "total_estimated_item_value": str(total_item_value),
        "total_combined_value": str(total_cash + total_item_value),
    }


def donations_by_category(funeral: FuneralEvent) -> dict:
    """
    The guest/town-leader/other breakdown of Ledger 2 for one funeral —
    "the system should know the total amount received from guests [and]
    elders of the town" made concrete. Each bucket sums `total_value`
    (cash plus any estimated item value), matching how gift_summary()
    already reports combined value.
    """
    donations = funeral.gift_donations.select_related("donor_member")
    buckets = {}
    for category, _ in GiftDonation.DonorCategory.choices:
        matching = [d for d in donations if d.donor_category == category]
        buckets[category] = {
            "donor_count": len(matching),
            "total_value": str(sum((d.total_value for d in matching), Decimal("0"))),
        }
    return {"funeral_id": str(funeral.id), "by_category": buckets}


@transaction.atomic
def register_donation_account_holder(*, funeral: FuneralEvent, member: Member, actor=None) -> DonationAccountRegistration:
    """
    'No executive user role should have the button to receive
    donations, should be available for only members and it should be
    activated when the family heads approve it.' Two rules enforced
    here: the member being registered can never hold an executive role
    themselves (an ordinary Community Member, Guest, or Bereaved
    Family Rep only — an executive's own authority over funeral funds
    is a separate, already-audited thing; receiving personal gift cash
    on top of that is a real conflict of interest, not a convenience).
    And unless the Family Head of the member's own family is the one
    registering them, the registration starts inactive — a pending
    request, not yet a real donation-receiving capability — until that
    Family Head approves it (see approve_donation_account_registration
    below). is_active is what list_donation_account_holders already
    filters on, so a pending registration is invisible to anyone
    recording a gift until it's genuinely approved.
    """
    from accounts.models import EXECUTIVE_ROLES
    from .permissions import is_family_head_of

    if member.community_id != funeral.community_id:
        raise ValidationError("The member must belong to this community.")
    if member.linked_user_id and member.linked_user.role in EXECUTIVE_ROLES:
        raise ValidationError("An executive role can't be registered to receive donations — this is reserved for ordinary members.")

    is_head_registering = bool(actor and member.family_id and is_family_head_of(actor, member.family))

    existing = DonationAccountRegistration.objects.filter(funeral_event=funeral, member=member).first()
    if existing:
        if not existing.is_active and is_head_registering:
            existing.is_active = True
            existing.registered_by = actor
            existing.save(update_fields=["is_active", "registered_by"])
        return existing

    return DonationAccountRegistration.objects.create(
        community=funeral.community, funeral_event=funeral, member=member, registered_by=actor,
        is_active=is_head_registering,
    )


def approve_donation_account_registration(*, registration: DonationAccountRegistration, actor) -> DonationAccountRegistration:
    """'It should be activated when the family heads approve it.' Only that member's own Family Head — nobody else's approval satisfies this."""
    from .permissions import is_family_head_of

    if not (registration.member.family_id and is_family_head_of(actor, registration.member.family)):
        raise ValidationError("Only this member's own Family Head can approve their donation-account registration.")
    if not registration.is_active:
        registration.is_active = True
        registration.registered_by = actor
        registration.save(update_fields=["is_active", "registered_by"])
    return registration


@transaction.atomic
def deregister_donation_account_holder(*, funeral: FuneralEvent, member: Member):
    DonationAccountRegistration.objects.filter(funeral_event=funeral, member=member).update(is_active=False)


def list_donation_account_holders(funeral: FuneralEvent):
    return DonationAccountRegistration.objects.filter(funeral_event=funeral, is_active=True).select_related("member")


def list_pending_donation_account_registrations(family):
    """The Family Head's own approval queue — every registration awaiting their sign-off, across every funeral."""
    return DonationAccountRegistration.objects.filter(member__family=family, is_active=False).select_related("member", "funeral_event")


def donations_received_by_member(member: Member, funeral: FuneralEvent | None = None) -> dict:
    """
    "Any amount paid should reflect on the person's dashboard... for
    transparency and accountability" — every gift ever attributed to
    this member as its receiver, cash or MoMo alike (attribution doesn't
    depend on payment method). This is the data both the member's own
    dashboard and an auditor checking their honesty would look at — the
    same numbers, not two different views that could quietly drift apart.

    Returns both the per-funeral totals (`by_funeral`, unchanged shape)
    AND the full donor-by-donor `entries` list — "when printing or
    generating list of those who paid: the name, phone contact, where
    the gifter resides, the amount the gifter paid" is exactly what
    `entries` carries, one row per donation, ready to hand straight to a
    printable statement (see reports/pdf.py's donation_receiver_statement_pdf).
    Pass `funeral` to scope this to one funeral only (e.g. printing a
    single funeral's list) instead of a receiver's entire history.
    """
    donations = GiftDonation.objects.filter(received_by_member=member).select_related("funeral_event")
    if funeral is not None:
        donations = donations.filter(funeral_event=funeral)
    total = sum((d.total_value for d in donations), Decimal("0"))

    by_funeral: dict = {}
    entries = []
    for d in donations:
        bucket = by_funeral.setdefault(str(d.funeral_event_id), {
            "funeral_id": str(d.funeral_event_id),
            "deceased_name": d.funeral_event.deceased_name,
            "donation_count": 0,
            "total_value": Decimal("0"),
        })
        bucket["donation_count"] += 1
        bucket["total_value"] += d.total_value

        entries.append({
            "donor_name": d.donor_name,
            "donor_phone": d.donor_phone,
            "donor_hometown": d.donor_hometown,
            "relationship_to_recipient": d.relationship_to_recipient,
            "amount": str(d.total_value),
            "deceased_name": d.funeral_event.deceased_name,
            "date_of_death": d.funeral_event.date_of_death.isoformat() if hasattr(d.funeral_event.date_of_death, "isoformat") else str(d.funeral_event.date_of_death),
            "paid_on": d.given_at.date().isoformat(),
            "paid_at_time": d.given_at.time().strftime("%H:%M"),
            "receipt_number": d.receipt_number,
        })

    entries.sort(key=lambda e: (e["paid_on"], e["paid_at_time"]), reverse=True)

    return {
        "member_id": str(member.id),
        "member_name": member.full_name,
        "total_received": str(total),
        "donation_count": donations.count(),
        "by_funeral": [
            {**v, "total_value": str(v["total_value"])} for v in by_funeral.values()
        ],
        "entries": entries,
    }

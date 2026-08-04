"""
Business logic for funerals and the mandatory contribution ledger.

The single most important rule enforced here, straight from the brief:
every active member of the community is automatically obligated the
moment a funeral is created — nobody registers for it, nobody opts in.
Members of the deceased's own family pay the family's own rate; everyone
else pays the community's general rate by gender. Nothing about this
module ever mixes with Ledger 2 (gift donations) — that lives entirely
in a separate app/table.
"""

import secrets
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

from members.models import Member
from .models import ContributionObligation, ContributionPayment, FuneralApproval, FuneralCommitteePosition, FuneralDeskAssignment, FuneralEvent, FuneralMemberRateOverride, MemorialPage, MemorialTribute, PaymentReversal


@transaction.atomic
def create_funeral_event(
    *, community, deceased_name, deceased_gender, deceased_family,
    date_of_death, collection_start_date, burial_date=None, funeral_date=None,
    collection_end_date=None, own_family_amount=None, general_male_amount=None,
    general_female_amount=None, actor=None, deceased_date_of_birth=None,
):
    if deceased_family.community_id != community.id:
        raise ValidationError("The deceased's family must belong to this community.")
    if deceased_family.status != "active":
        raise ValidationError("Cannot hold a funeral for a deactivated or deleted family.")

    resolved_own_family_amount = (
        own_family_amount if own_family_amount is not None else deceased_family.standing_family_rate
    )
    if resolved_own_family_amount is None:
        raise ValidationError(
            f"'{deceased_family.name}' has no approved contribution rate yet. "
            "Approve a standing rate for this family first, or supply an amount for this funeral only."
        )

    funeral = FuneralEvent.objects.create(
        community=community,
        deceased_name=deceased_name,
        deceased_gender=deceased_gender,
        deceased_family=deceased_family,
        date_of_death=date_of_death,
        deceased_date_of_birth=deceased_date_of_birth,
        burial_date=burial_date,
        funeral_date=funeral_date,
        collection_start_date=collection_start_date,
        collection_end_date=collection_end_date,
        own_family_amount=resolved_own_family_amount,
        general_male_amount=(
            general_male_amount if general_male_amount is not None else community.default_general_male_amount
        ),
        general_female_amount=(
            general_female_amount if general_female_amount is not None else community.default_general_female_amount
        ),
        family_head_amount=community.default_family_head_amount,
        family_senior_amount=community.default_family_senior_amount,
        family_junior_amount=community.default_family_junior_amount,
        family_woman_amount=community.default_family_woman_amount,
        town_leader_amount=community.default_town_leader_amount,
        created_by=actor,
    )
    generate_obligations(funeral)
    return funeral


APPROVAL_ROLES = {"secretary", "chairman", "community_admin"}
# The default lives on Community.required_funeral_approvals now (see
# tenants/models.py) — "Configure approval workflows" means each
# community's own Admin can change this for their own workspace. This
# name stays only as the historical constant new communities inherit
# via the model field's own default=2.
REQUIRED_APPROVAL_COUNT = 2


def request_funeral_event(
    *, community, deceased_name, deceased_gender, deceased_family,
    date_of_death, collection_start_date, burial_date=None, funeral_date=None,
    collection_end_date=None, own_family_amount=None, general_male_amount=None,
    general_female_amount=None, actor=None, deceased_date_of_birth=None,
):
    """
    'Is the family head who will open the ledger when there's a
    funeral.' Creates the SAME kind of FuneralEvent create_funeral_event
    does — same rate snapshotting, same validation — except it starts in
    PENDING_APPROVAL and deliberately does NOT call generate_obligations:
    nobody is billed a single cedi until approve_funeral_opening() below
    has been called by two distinct qualifying people. This is the
    concrete meaning of "before every member is billed."
    """
    if deceased_family.community_id != community.id:
        raise ValidationError("The deceased's family must belong to this community.")
    if deceased_family.status != "active":
        raise ValidationError("Cannot hold a funeral for a deactivated or deleted family.")

    resolved_own_family_amount = (
        own_family_amount if own_family_amount is not None else deceased_family.standing_family_rate
    )
    if resolved_own_family_amount is None:
        resolved_own_family_amount = community.default_family_head_amount  # informational only; see FuneralEvent.own_family_amount docstring

    funeral = FuneralEvent.objects.create(
        community=community,
        deceased_name=deceased_name,
        deceased_gender=deceased_gender,
        deceased_family=deceased_family,
        date_of_death=date_of_death,
        deceased_date_of_birth=deceased_date_of_birth,
        burial_date=burial_date,
        funeral_date=funeral_date,
        collection_start_date=collection_start_date,
        collection_end_date=collection_end_date,
        status=FuneralEvent.Status.PENDING_APPROVAL,
        own_family_amount=resolved_own_family_amount,
        general_male_amount=(
            general_male_amount if general_male_amount is not None else community.default_general_male_amount
        ),
        general_female_amount=(
            general_female_amount if general_female_amount is not None else community.default_general_female_amount
        ),
        family_head_amount=community.default_family_head_amount,
        family_senior_amount=community.default_family_senior_amount,
        family_junior_amount=community.default_family_junior_amount,
        family_woman_amount=community.default_family_woman_amount,
        town_leader_amount=community.default_town_leader_amount,
        created_by=actor,
    )
    return funeral


@transaction.atomic
def approve_funeral_opening(*, funeral: FuneralEvent, approver) -> FuneralEvent:
    """
    Records one approval. The moment a SECOND distinct qualifying person
    has approved, the funeral goes live and every member is billed in
    the same instant (generate_obligations) — never before, and never
    partially. A third, fourth, etc. approval is accepted but has no
    further effect; re-approving after the funeral is already active is
    a harmless no-op rather than an error, since the safety property
    ("at least two people signed off") is already satisfied either way.

    'Under no circumstance shall a user be able to approve... their own
    official transactions... where a conflict of interest exists' —
    whoever requested this funeral's opening can never also be one of
    its required approvers, no matter what role they otherwise hold.
    """
    if funeral.status not in (FuneralEvent.Status.PENDING_APPROVAL, FuneralEvent.Status.ACTIVE):
        raise ValidationError(f"A funeral with status '{funeral.status}' cannot be approved.")
    if funeral.created_by_id == approver.id:
        raise ValidationError("You requested this funeral's opening — someone else must approve it.")

    FuneralApproval.objects.get_or_create(funeral_event=funeral, approved_by=approver)

    if funeral.status == FuneralEvent.Status.PENDING_APPROVAL:
        distinct_approvers = funeral.approvals.values("approved_by_id").distinct().count()
        if distinct_approvers >= funeral.community.required_funeral_approvals:
            funeral.status = FuneralEvent.Status.ACTIVE
            funeral.save(update_fields=["status", "updated_at"])
            generate_obligations(funeral)
            from audit_log.services import record_event
            record_event(
                category="funeral_opening", action="funeral_opening_approved", actor=approver, community=funeral.community,
                target_type="FuneralEvent", target_id=funeral.id, target_label=funeral.deceased_name,
                description=f"Funeral opening for {funeral.deceased_name} went live after {distinct_approvers} approvals.",
            )

    return funeral


def reject_funeral_opening(*, funeral: FuneralEvent, actor=None) -> FuneralEvent:
    if funeral.status != FuneralEvent.Status.PENDING_APPROVAL:
        raise ValidationError(f"A funeral with status '{funeral.status}' cannot be rejected — it was never pending approval.")
    funeral.status = FuneralEvent.Status.CANCELLED
    funeral.save(update_fields=["status", "updated_at"])
    from audit_log.services import record_event
    record_event(
        category="funeral_opening", action="funeral_opening_rejected", actor=actor, community=funeral.community,
        target_type="FuneralEvent", target_id=funeral.id, target_label=funeral.deceased_name,
        description=f"Funeral opening for {funeral.deceased_name} was rejected.",
    )
    return funeral


def funeral_approval_progress(funeral: FuneralEvent) -> dict:
    approvals = list(funeral.approvals.select_related("approved_by").order_by("approved_at"))
    required = funeral.community.required_funeral_approvals
    return {
        "funeral_id": str(funeral.id),
        "status": funeral.status,
        "required_approvals": required,
        "approvals": [{"approved_by": a.approved_by.username, "approved_at": a.approved_at.isoformat()} for a in approvals],
        "approval_count": len(approvals),
        "still_needed": max(0, required - len(approvals)),
    }


@transaction.atomic
def set_member_rate_overrides(*, funeral: FuneralEvent, overrides: dict, actor=None) -> list:
    """
    'The family head and secretary of the deceased family can set an
    amount for each member [of their own family] have to pay.' `overrides`
    is {member_id: amount}. Only while the funeral is still
    PENDING_APPROVAL — see generate_obligations, which is the only place
    these ever get read, at the moment the 2nd approval activates the
    funeral. Once active, obligations already exist and are the real
    source of truth; there would be nothing left for an override to do.
    """
    if funeral.status != FuneralEvent.Status.PENDING_APPROVAL:
        raise ValidationError(
            "Rate overrides can only be set while a funeral is still awaiting approval — "
            "once it's active, obligations have already been generated."
        )

    results = []
    for member_id, amount in overrides.items():
        try:
            member = Member.objects.get(id=member_id, community=funeral.community)
        except Member.DoesNotExist:
            raise ValidationError(f"Member {member_id} not found in this community.")
        if member.family_id != funeral.deceased_family_id:
            raise ValidationError(
                f"{member.full_name} isn't a member of {funeral.deceased_family.name} — "
                "you can only set custom amounts for your own family's members."
            )
        if amount < 0:
            raise ValidationError(f"The amount for {member.full_name} can't be negative.")

        override, _ = FuneralMemberRateOverride.objects.update_or_create(
            funeral_event=funeral, member=member, defaults={"amount": amount, "set_by": actor}
        )
        results.append(override)
    return results


def list_member_rate_overrides(funeral: FuneralEvent) -> list:
    return list(funeral.member_rate_overrides.select_related("member").order_by("member__full_name"))


_DESK_ASSIGNER_COMMUNITY_WIDE_ROLES = {"community_admin", "chairman", "secretary"}


def _can_assign_desk_workers_for(actor, funeral: FuneralEvent, desk_type: str) -> bool:
    """
    'Only the abusuapanin of each family can assign someone as a front
    desk officer or collector and it has to be approved by the
    community admin or temporary admin.' The Community, Elders, and
    Guest desk purposes all serve the WHOLE community (or its visiting
    guests), never just one family, so they stay Chairman/Secretary/
    Admin-only regardless of which funeral. The Family desk purpose is
    the one exception — narrowed to this specific family's own Head
    only (not Family Secretary too, unlike some other family-scoped
    authorities in this platform) — Community Admin+ can still open
    any desk type too, on any funeral, since that's also the approval
    authority a Family Head's own assignment is pending on.
    """
    if actor.is_superuser or actor.role in _DESK_ASSIGNER_COMMUNITY_WIDE_ROLES:
        return True
    if desk_type != FuneralDeskAssignment.DeskType.FAMILY:
        return False
    own_member = getattr(actor, "member_profile", None)
    return bool(
        own_member and own_member.family_id == funeral.deceased_family_id
        and actor.role == "family_head"
    )


@transaction.atomic
def assign_desk_worker(
    *, funeral: FuneralEvent, actor, desk_type: str, user=None,
    new_username: str = None, new_password: str = None, new_email: str = "",
) -> FuneralDeskAssignment:
    """
    'Head of the family should be able to add one or more users and
    assign them, some who could be a member or not.' Pass an existing
    `user` to appoint someone who already has a login, or
    `new_username`/`new_password` to create a fresh, otherwise
    unprivileged account on the spot for someone who has neither a
    Member profile nor a login yet — a trusted family friend recruited
    just for the day, exactly the case "could be a member or not" is
    describing. Either way, what actually grants desk access is this
    assignment row, not the person's ordinary platform role.

    A Family desk assignment starts inactive — a real pending request,
    granting no actual desk access yet (see funerals.permissions.
    is_desk_worker_for) — until the community's own Community Admin
    (or, for a temporary/rental community, its own Community Admin
    account, the same role) approves it. A Community/Elders/Guest desk,
    or a Family desk a Community Admin opens directly themselves, is
    active immediately: that authority already IS the approval this
    workflow otherwise waits for.
    """
    from accounts.models import Role, User

    if desk_type not in FuneralDeskAssignment.DeskType.values:
        raise ValidationError(f"'{desk_type}' isn't a valid desk type.")
    if not _can_assign_desk_workers_for(actor, funeral, desk_type):
        raise ValidationError(
            "Only the community's Chairman/Secretary/Admin can open a Community, Elders, or Guest "
            "desk. A Family desk can only be opened by this specific family's own head."
        )

    if user is None:
        if not (new_username and new_password):
            raise ValidationError("Provide either an existing user or a new username and password.")
        if User.objects.filter(username=new_username).exists():
            raise ValidationError(f"The username '{new_username}' is already taken.")
        user = User.objects.create_user(
            username=new_username, password=new_password, email=new_email,
            community=funeral.community, role=Role.GUEST,
        )
    elif user.community_id != funeral.community_id:
        raise ValidationError("The assigned user must belong to this community.")

    is_directly_approved = bool(desk_type != FuneralDeskAssignment.DeskType.FAMILY or actor.is_superuser or actor.role in _DESK_ASSIGNER_COMMUNITY_WIDE_ROLES)
    assignment, _ = FuneralDeskAssignment.objects.update_or_create(
        funeral_event=funeral, user=user, defaults={
            "desk_type": desk_type, "assigned_by": actor, "is_active": is_directly_approved,
            "approved_by": actor if is_directly_approved else None,
            "approved_at": timezone.now() if is_directly_approved else None,
        }
    )
    return assignment


def approve_desk_assignment(*, assignment: FuneralDeskAssignment, actor) -> FuneralDeskAssignment:
    """'It has to be approved by the community admin or temporary admin.'"""
    if not (actor.is_superuser or actor.role == "community_admin" and actor.community_id == assignment.funeral_event.community_id):
        raise ValidationError("Only this community's own Community Administrator can approve a front desk/collector assignment.")
    if not assignment.is_active:
        assignment.is_active = True
        assignment.approved_by = actor
        assignment.approved_at = timezone.now()
        assignment.save(update_fields=["is_active", "approved_by", "approved_at"])
    return assignment


def list_pending_desk_assignments(community):
    """The Community (or Temporary) Admin's own approval queue — every Family desk assignment awaiting their sign-off, across every funeral."""
    return FuneralDeskAssignment.objects.filter(
        funeral_event__community=community, desk_type=FuneralDeskAssignment.DeskType.FAMILY, is_active=False,
    ).select_related("user", "funeral_event")


def remove_desk_worker(*, funeral: FuneralEvent, user, actor) -> None:
    existing = FuneralDeskAssignment.objects.filter(funeral_event=funeral, user=user).first()
    if existing is None:
        return
    if not _can_assign_desk_workers_for(actor, funeral, existing.desk_type):
        raise ValidationError(
            "Only the community's Chairman/Secretary/Admin can remove someone from a Community, "
            "Elders, or Guest desk. A Family desk can only be managed by this family's own head."
        )
    existing.delete()


def list_desk_assignments(funeral: FuneralEvent) -> list:
    return list(funeral.desk_assignments.select_related("user").order_by("user__username"))


# Wider than approval authority on purpose: Treasurer/Financial
# Secretary handle payments day to day and are exactly who'd first
# notice a mistake worth reversing — but they can't approve their own
# request, matching the pattern below.
REVERSAL_REQUEST_ROLES = APPROVAL_ROLES | {"treasurer", "financial_secretary"}


def request_payment_reversal(*, payment: ContributionPayment, reason: str, actor) -> PaymentReversal:
    """'An authorized administrator should be able to initiate a reversal or correction' — the request step. Nothing about the payment or the obligation's balance changes yet; that only happens once a DIFFERENT authorized person approves it, below."""
    if not (actor.is_superuser or actor.role in REVERSAL_REQUEST_ROLES):
        raise ValidationError("Only the Treasurer, Financial Secretary, Secretary, Chairman, or Community Admin can request a payment reversal.")
    if not reason.strip():
        raise ValidationError("A reason is required — this becomes part of the permanent audit trail.")
    if PaymentReversal.objects.filter(payment=payment, status=PaymentReversal.Status.PENDING).exists():
        raise ValidationError("There's already a pending reversal request for this payment.")
    if PaymentReversal.objects.filter(payment=payment, status=PaymentReversal.Status.APPROVED).exists():
        raise ValidationError("This payment has already been reversed.")
    return PaymentReversal.objects.create(payment=payment, reason=reason.strip(), requested_by=actor)


@transaction.atomic
def approve_payment_reversal(*, reversal: PaymentReversal, actor, notes: str = "") -> PaymentReversal:
    """
    The only place a reversal actually takes effect. Requires a
    DIFFERENT person than whoever requested it — the same two-person
    principle already used before a funeral opens for billing — and the
    original ContributionPayment row is never touched: only the
    obligation's running total is corrected, using an F() expression so
    a concurrent payment landing at the same moment can never be
    silently overwritten.
    """
    if not (actor.is_superuser or actor.role in APPROVAL_ROLES):
        raise ValidationError("Only the Secretary, Chairman, Community Admin, or a Super/Platform Admin can approve a payment reversal.")
    if reversal.status != PaymentReversal.Status.PENDING:
        raise ValidationError("This reversal request has already been decided.")
    if reversal.requested_by_id == actor.id:
        raise ValidationError("A different authorized person must approve this — the same person can't request and approve their own reversal.")

    reversal.status = PaymentReversal.Status.APPROVED
    reversal.decided_by = actor
    reversal.decided_at = timezone.now()
    reversal.decision_notes = notes
    reversal.save()

    obligation = reversal.payment.obligation
    ContributionObligation.objects.filter(pk=obligation.pk).update(amount_paid=F("amount_paid") - reversal.payment.amount)

    from audit_log.services import record_event
    record_event(
        category="payment_reversal", action="payment_reversal_approved", actor=actor, community=reversal.payment.obligation.community,
        target_type="PaymentReversal", target_id=reversal.id, target_label=f"Payment of {reversal.payment.amount} reversed",
        description=f"Reversed a payment of {reversal.payment.amount}, requested by {reversal.requested_by.username}. Reason: {reversal.reason}",
    )
    return reversal


def reject_payment_reversal(*, reversal: PaymentReversal, actor, notes: str = "") -> PaymentReversal:
    if not (actor.is_superuser or actor.role in APPROVAL_ROLES):
        raise ValidationError("Only the Secretary, Chairman, Community Admin, or a Super/Platform Admin can decide a payment reversal.")
    if reversal.status != PaymentReversal.Status.PENDING:
        raise ValidationError("This reversal request has already been decided.")
    reversal.status = PaymentReversal.Status.REJECTED
    reversal.decided_by = actor
    reversal.decided_at = timezone.now()
    reversal.decision_notes = notes
    reversal.save()

    from audit_log.services import record_event
    record_event(
        category="payment_reversal", action="payment_reversal_rejected", actor=actor, community=reversal.payment.obligation.community,
        target_type="PaymentReversal", target_id=reversal.id, target_label=f"Payment of {reversal.payment.amount} reversal request",
        description=f"Declined to reverse a payment of {reversal.payment.amount}, requested by {reversal.requested_by.username}.",
    )
    return reversal


def list_reversal_requests(*, community, actor) -> list:
    if not (actor.is_superuser or actor.role in REVERSAL_REQUEST_ROLES):
        raise ValidationError("Only the Treasurer, Financial Secretary, Secretary, Chairman, or Community Admin can view reversal requests.")
    return list(
        PaymentReversal.objects.filter(payment__obligation__funeral_event__community=community)
        .select_related("payment", "requested_by", "decided_by")
    )


def _can_manage_memorial_page_for(actor, funeral: FuneralEvent) -> bool:
    """Same 'your own family, or community-wide' rule used for desk assignments and rate overrides — the deceased family's own Head/Secretary, or Community Admin+."""
    if actor.is_superuser or actor.role in _DESK_ASSIGNER_COMMUNITY_WIDE_ROLES:
        return True
    own_member = getattr(actor, "member_profile", None)
    return bool(
        own_member and own_member.family_id == funeral.deceased_family_id
        and actor.role in ("family_head", "family_secretary")
    )


@transaction.atomic
def create_or_update_memorial_page(
    *, funeral: FuneralEvent, actor, tribute_message: str = None, photo=None,
    show_contribution_total: bool = None, is_published: bool = None,
) -> MemorialPage:
    if not _can_manage_memorial_page_for(actor, funeral):
        raise ValidationError("Only this family's own head or secretary, or the community's Chairman/Secretary/Admin, can manage this funeral's memorial page.")

    page, _ = MemorialPage.objects.get_or_create(funeral_event=funeral, defaults={"created_by": actor})
    if tribute_message is not None:
        page.tribute_message = tribute_message
    if photo is not None:
        page.photo = photo
    if show_contribution_total is not None:
        page.show_contribution_total = show_contribution_total
    if is_published is not None:
        page.is_published = is_published
    page.save()
    return page


def get_public_memorial_page(funeral: FuneralEvent) -> dict | None:
    """
    The one genuinely public read in this whole platform. Returns None
    for a funeral with no page, or one that's been unpublished — never
    partial data, never a 'this exists but is private' hint either way.
    Deliberately never includes anything from the ledgers beyond, at
    most, ONE aggregate total the family explicitly opted into sharing —
    never a donor's name, never an amount, never which ledger it came from.
    """
    try:
        page = funeral.memorial_page
    except MemorialPage.DoesNotExist:
        return None
    if not page.is_published:
        return None

    from datetime import date

    def _as_date(value):
        # Same gotcha as funeral_daily_breakdown: a FuneralEvent
        # returned directly from .objects.create(date_of_death="...")
        # can still carry that raw string, not a converted date object,
        # until reloaded from the database.
        if value is None:
            return None
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    data = {
        "funeral_id": str(funeral.id),
        "deceased_name": funeral.deceased_name,
        "date_of_death": _as_date(funeral.date_of_death).isoformat() if funeral.date_of_death else None,
        "funeral_date": _as_date(funeral.funeral_date).isoformat() if funeral.funeral_date else None,
        "tribute_message": page.tribute_message,
        "photo_url": page.photo.url if page.photo else None,
        "tributes": [
            {"author_name": t.author_name, "message": t.message, "created_at": t.created_at.isoformat()}
            for t in page.tributes.filter(is_approved=True)
        ],
    }
    if page.show_contribution_total:
        contributions_total = ContributionPayment.objects.filter(obligation__funeral_event=funeral).aggregate(total=Sum("amount"))["total"] or 0
        gifts_total = funeral.gift_donations.aggregate(total=Sum("amount_cash"))["total"] or 0
        data["contribution_total"] = str(contributions_total + gifts_total)

    # "Guests to use to donate their gift or contribute" — a guest
    # scanning the QR code and landing here needs to actually know HOW
    # to send money, not just see a tribute wall. Only ever the
    # community's own designated payout account(s) — never a donor's
    # name, amount, or anything from the ledgers beyond the one opt-in
    # total above.
    from tenants.models import CommunityPayoutAccount
    data["payout_accounts"] = [
        {"account_type": a.account_type, "provider_name": a.provider_name, "account_number": a.account_number, "account_holder_name": a.account_holder_name}
        for a in CommunityPayoutAccount.objects.filter(community=funeral.community, is_active=True)
    ]
    return data


def submit_tribute(*, funeral: FuneralEvent, author_name: str, message: str) -> MemorialTribute:
    """Public — no login required, matching the page itself. Always created unapproved; never shows up anywhere public until the family or an admin approves it."""
    try:
        page = funeral.memorial_page
    except MemorialPage.DoesNotExist:
        raise ValidationError("This funeral doesn't have a memorial page yet.")
    if not page.is_published:
        raise ValidationError("This memorial page isn't available.")
    if not author_name.strip():
        raise ValidationError("Please include your name.")
    if not message.strip():
        raise ValidationError("Please include a message.")
    return MemorialTribute.objects.create(memorial_page=page, author_name=author_name.strip(), message=message.strip())


def list_all_tributes_for_management(*, funeral: FuneralEvent, actor) -> list:
    """The family/admin's own view — includes PENDING tributes too, not just approved ones, so there's something to actually moderate."""
    if not _can_manage_memorial_page_for(actor, funeral):
        raise ValidationError("Only this family's own head or secretary, or the community's Chairman/Secretary/Admin, can manage this funeral's tributes.")
    try:
        page = funeral.memorial_page
    except MemorialPage.DoesNotExist:
        return []
    return list(page.tributes.all())


def approve_tribute(*, tribute: MemorialTribute, actor) -> MemorialTribute:
    if not _can_manage_memorial_page_for(actor, tribute.memorial_page.funeral_event):
        raise ValidationError("Only this family's own head or secretary, or the community's Chairman/Secretary/Admin, can approve tributes.")
    tribute.is_approved = True
    tribute.save(update_fields=["is_approved"])
    return tribute


def reject_tribute(*, tribute: MemorialTribute, actor) -> None:
    if not _can_manage_memorial_page_for(actor, tribute.memorial_page.funeral_event):
        raise ValidationError("Only this family's own head or secretary, or the community's Chairman/Secretary/Admin, can remove tributes.")
    tribute.delete()


def _rate_for_with_override(funeral: FuneralEvent, member) -> tuple[str, "models.DecimalField"]:
    """
    Checks for a family-set per-member override (see
    FuneralMemberRateOverride / set_member_rate_overrides) before
    falling back to the community's own tiered defaults
    (FuneralEvent.rate_for). An override always keeps its rate_type as
    "own_family" — it only ever exists for members of the deceased's
    own family in the first place (see set_member_rate_overrides'
    validation), so there's no ambiguity about which ledger it belongs to.
    """
    override = funeral.member_rate_overrides.filter(member=member).first()
    if override is not None:
        return "own_family", override.amount
    return funeral.rate_for(member)


def generate_obligations(funeral: FuneralEvent):
    """
    Fan-out: one ContributionObligation per member ELIGIBLE under the
    community's contribution rules (see contribution_rules.services —
    by default that means active members only, but a community can
    reconfigure which member statuses are exempt), decided purely by
    whether the member's family matches the deceased's family. This is
    what makes enrollment automatic — there is no member-facing "join the
    ledger" step anywhere in the system.
    """
    from contribution_rules.services import eligible_members_queryset

    members = eligible_members_queryset(funeral.community)
    obligations = []
    for member in members:
        rate_type, amount = _rate_for_with_override(funeral, member)
        obligations.append(
            ContributionObligation(
                community=funeral.community,
                funeral_event=funeral,
                member=member,
                rate_type=rate_type,
                expected_amount=amount,
            )
        )
    # ignore_conflicts guards re-running this safely (e.g. a retried Celery
    # task) without creating duplicate obligations for the same member.
    ContributionObligation.objects.bulk_create(obligations, ignore_conflicts=True)


@transaction.atomic
def enroll_new_member_in_open_funerals(member: Member):
    """
    Call this right after a member is created (or reactivated, or has
    their family changed). If the community currently has one or more
    active funerals, the member is automatically added to each one's
    ledger too — "automatically registered" applies from the moment
    someone becomes a member, not only at the moment a funeral is created.
    """
    from contribution_rules.services import eligible_members_queryset

    if not eligible_members_queryset(member.community).filter(id=member.id).exists():
        return

    open_funerals = FuneralEvent.objects.filter(community=member.community, status=FuneralEvent.Status.ACTIVE)
    obligations = []
    for funeral in open_funerals:
        rate_type, amount = _rate_for_with_override(funeral, member)
        obligations.append(
            ContributionObligation(
                community=member.community, funeral_event=funeral, member=member,
                rate_type=rate_type, expected_amount=amount,
            )
        )
    ContributionObligation.objects.bulk_create(obligations, ignore_conflicts=True)


def _generate_receipt_number(community) -> str:
    today_prefix = f"{community.slug.upper()[:8]}-{timezone.now():%Y%m%d}"
    for _ in range(5):
        candidate = f"{today_prefix}-{secrets.token_hex(3).upper()}"
        if not ContributionPayment.objects.filter(receipt_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique receipt number; please retry.")


@transaction.atomic
def _find_older_unpaid_obligation(obligation: ContributionObligation):
    """
    'Members who owe or have debts have to pay before they can pay for
    new ones.' The oldest still-outstanding (unpaid or partial)
    obligation this same member has, from a funeral that started
    collecting strictly BEFORE this one's — never a same-day funeral
    (two families can genuinely hold funerals on the same day; neither
    should block the other), and never this obligation itself.
    """
    return (
        ContributionObligation.objects
        .filter(member=obligation.member, community=obligation.community)
        .exclude(id=obligation.id)
        .filter(amount_paid__lt=F("expected_amount"))
        .filter(funeral_event__collection_start_date__lt=obligation.funeral_event.collection_start_date)
        .select_related("funeral_event", "funeral_event__deceased_family")
        .order_by("funeral_event__collection_start_date")
        .first()
    )


def record_payment(
    *, obligation: ContributionObligation, amount: Decimal, method: str,
    collector=None, client_op_id=None,
):
    """
    Records one instalment against an obligation. Idempotent on
    `client_op_id`: if a collector's device retries a sync after a dropped
    connection, the same payment is never counted twice — the existing
    payment is simply returned instead of a new one being created.

    `expected_amount` is a MINIMUM, not a cap: someone can choose to pay
    more than their own-family or general rate requires, and the system
    accepts it (the excess is real income, tracked via
    `ContributionObligation.overpaid_amount`) — what's never allowed is
    settling for less than what's required, which is simply the existing
    "partial"/"unpaid" status doing its job.

    'Members who owe or have debts have to pay before they can pay for
    new ones.' If this member has an OLDER still-outstanding obligation
    (from a funeral that started collecting earlier than this one's),
    this payment is refused outright — see _find_older_unpaid_obligation
    — and the Financial Secretary plus that older debt's own Family Head
    are notified. Idempotent replays (client_op_id) are checked first,
    above, specifically so this new rule can never turn an already
    -succeeded, merely-retried payment into a rejection.
    """
    if client_op_id:
        existing = ContributionPayment.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing

    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    older_debt = _find_older_unpaid_obligation(obligation)
    if older_debt is not None:
        from notifications.services import notify_old_debt
        notify_old_debt(
            owed_to_family=older_debt.funeral_event.deceased_family,
            member=obligation.member,
            message=(
                f"{obligation.member.full_name} tried to contribute toward {obligation.funeral_event.deceased_name}'s "
                f"funeral but still owes {older_debt.balance} toward {older_debt.funeral_event.deceased_name}'s funeral "
                f"(started {older_debt.funeral_event.collection_start_date}) — that debt must be settled first."
            ),
        )
        raise ValidationError(
            f"{obligation.member.full_name} still owes {older_debt.balance} toward "
            f"{older_debt.funeral_event.deceased_name}'s funeral — settle that first before a new "
            f"contribution can be recorded."
        )

    try:
        payment = ContributionPayment.objects.create(
            obligation=obligation,
            amount=amount,
            method=method,
            receipt_number=_generate_receipt_number(obligation.community),
            collected_by=collector,
            client_op_id=client_op_id,
        )
    except IntegrityError:
        # Extremely rare race on receipt_number or client_op_id — safe to
        # just re-check for an existing idempotent payment and surface any
        # genuine conflict otherwise.
        if client_op_id:
            existing = ContributionPayment.objects.filter(client_op_id=client_op_id).first()
            if existing:
                return existing
        raise

    obligation.amount_paid = obligation.amount_paid + amount
    obligation.save(update_fields=["amount_paid", "updated_at"])

    from realtime.broadcast import broadcast_funeral_ledger_event
    broadcast_funeral_ledger_event(
        str(obligation.funeral_event_id), "payment_recorded",
        {
            "obligation_id": str(obligation.id),
            "member_name": obligation.member.full_name,
            "amount": str(amount),
            "new_balance": str(obligation.balance),
            "payment_status": obligation.payment_status,
        },
    )

    from ai_features.services import flag_suspicious_transactions_for_payment
    flag_suspicious_transactions_for_payment(payment)

    if obligation.payment_status == "paid":
        # Only worth telling anyone about if this was genuinely capable
        # of having blocked a newer payment (see _find_older_unpaid_obligation)
        # — an ordinary member with only ever this one obligation settling
        # it immediately is not "old debt" news to anyone.
        newer_obligation_exists = (
            ContributionObligation.objects
            .filter(member=obligation.member, community=obligation.community)
            .exclude(id=obligation.id)
            .filter(funeral_event__collection_start_date__gt=obligation.funeral_event.collection_start_date)
            .exists()
        )
        if newer_obligation_exists:
            from notifications.services import notify_old_debt
            notify_old_debt(
                owed_to_family=obligation.funeral_event.deceased_family,
                member=obligation.member,
                message=(
                    f"{obligation.member.full_name}'s outstanding debt toward "
                    f"{obligation.funeral_event.deceased_name}'s funeral has now been fully settled."
                ),
            )

    return payment


@transaction.atomic
def close_funeral_event(*, funeral: FuneralEvent, actor=None):
    if funeral.status != FuneralEvent.Status.ACTIVE:
        raise ValidationError("Only an active funeral can be closed.")
    funeral.status = FuneralEvent.Status.CLOSED
    funeral.save(update_fields=["status", "updated_at"])

    from members.services import evaluate_defaulters_for_closed_funeral
    evaluate_defaulters_for_closed_funeral(funeral)

    return funeral


def funeral_summary(funeral: FuneralEvent) -> dict:
    """
    Powers the "make it look great, not confusing" dashboard: a single
    clear breakdown of own-family payers vs. general payers, even while
    several other funerals are open for the same community at once.
    """
    obligations = funeral.obligations.select_related("member", "member__family")

    def _bucket(rate_type):
        qs = obligations.filter(rate_type=rate_type)
        expected = sum((o.expected_amount for o in qs), Decimal("0"))
        paid = sum((o.amount_paid for o in qs), Decimal("0"))
        return {
            "member_count": qs.count(),
            "expected_total": expected,
            "collected_total": paid,
            "outstanding_total": expected - paid,
            "fully_paid_count": sum(1 for o in qs if o.payment_status == "paid"),
            "partial_count": sum(1 for o in qs if o.payment_status == "partial"),
            "unpaid_count": sum(1 for o in qs if o.payment_status == "unpaid"),
        }

    return {
        "funeral_id": str(funeral.id),
        "deceased_name": funeral.deceased_name,
        "deceased_family": funeral.deceased_family.name,
        "own_family": _bucket(ContributionObligation.RateType.OWN_FAMILY),
        "general": _bucket(ContributionObligation.RateType.GENERAL),
    }


def recalculate_open_obligations_for_member(member):
    """
    Called whenever a member's family changes (transfer or merge) while a
    funeral is currently open. A member who moves into the deceased's
    family mid-collection should switch to the own-family rate (and vice
    versa) — this keeps that in sync without touching funerals that have
    already closed.

    Known limitation: if a member already paid more than their new
    expected amount (e.g. they paid the higher own-family rate, then
    transferred out to a family that only owes the lower general rate),
    this does not auto-refund; it leaves `amount_paid` untouched so the
    obligation shows an overpayment for a Treasurer to reconcile by hand
    rather than silently adjusting money already collected.
    """
    open_obligations = ContributionObligation.objects.filter(
        member=member, funeral_event__status=FuneralEvent.Status.ACTIVE
    ).select_related("funeral_event")
    for obligation in open_obligations:
        rate_type, amount = obligation.funeral_event.rate_for(member)
        if obligation.rate_type != rate_type or obligation.expected_amount != amount:
            obligation.rate_type = rate_type
            obligation.expected_amount = amount
            obligation.save(update_fields=["rate_type", "expected_amount", "updated_at"])


def generate_funeral_qr_code_base64(funeral: FuneralEvent) -> str:
    """
    'The community admin should be able to generate a barcode so that
    it can be printed and pasted for guests to use to donate their
    gift or contribute.' Same real QR generation already used for
    membership cards — a real, scannable image any phone camera can
    open, encoding funeral.qr_payload (the public Memorial Page).
    """
    import base64
    import io
    import qrcode

    img = qrcode.make(funeral.qr_payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _can_organize_committee_for(actor, funeral: FuneralEvent) -> bool:
    """
    Same authority boundary already proven for desk assignment — a
    funeral's committee is organized by community-wide leadership, or
    by the deceased's own family Head/Secretary, and nobody else.
    """
    if actor.is_superuser or actor.role in _DESK_ASSIGNER_COMMUNITY_WIDE_ROLES:
        return True
    own_member = getattr(actor, "member_profile", None)
    return bool(
        own_member and own_member.family_id == funeral.deceased_family_id
        and actor.role in ("family_head", "family_secretary")
    )


def appoint_committee_position(*, funeral: FuneralEvent, member, title: str, actor) -> FuneralCommitteePosition:
    """
    'Every funeral creates a committee workspace... Custom positions
    allowed.' Deliberately NOT a new platform role or a new payment
    -collecting authority — a committee member who also needs to
    record contributions or gifts still needs their own, separate
    desk assignment (see assign_desk_worker above). This is pure
    organizational record-keeping, the same principle already used
    for FamilyOfficerPosition.
    """
    if not _can_organize_committee_for(actor, funeral):
        raise ValidationError("Only community-wide leadership, or the deceased's own family Head/Secretary, can organize this funeral's committee.")
    title = title.strip()
    if not title:
        raise ValidationError("A title is required.")
    if member.community_id != funeral.community_id:
        raise ValidationError("The chosen committee member must belong to this community.")
    return FuneralCommitteePosition.objects.create(funeral_event=funeral, member=member, title=title, appointed_by=actor)


def remove_committee_position(*, position: FuneralCommitteePosition, actor) -> None:
    if not _can_organize_committee_for(actor, position.funeral_event):
        raise ValidationError("Only community-wide leadership, or the deceased's own family Head/Secretary, can organize this funeral's committee.")
    position.delete()


def list_committee_positions(*, funeral: FuneralEvent) -> list:
    """Visible to the whole community, like the desk assignments list already is — a committee is public organizational information, not a private record."""
    return list(funeral.committee_positions.select_related("member"))


def list_my_committee_positions(*, member) -> list:
    """'Each role receives only relevant dashboard' — the lightest-weight honest version of that: a member's own committee assignments, across every funeral in their community, surfaced in one place rather than twelve bespoke dashboards."""
    if member is None:
        return []
    return list(FuneralCommitteePosition.objects.filter(member=member).select_related("funeral_event"))

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
from .models import AsupedeObligation, AsupedePayment, ContributionObligation, ContributionPayment, FuneralApproval, FuneralCommitteePosition, FuneralDeskAssignment, FuneralEvent, FuneralMemberRateOverride, LedgerWallet, LedgerWalletTransaction, MemorialPage, MemorialTribute, PaymentReversal


@transaction.atomic
def create_funeral_event(
    *, community, deceased_name, deceased_gender, deceased_family,
    date_of_death, collection_start_date, burial_date=None, funeral_date=None,
    collection_end_date=None, own_family_amount=None, general_male_amount=None,
    general_female_amount=None, actor=None, deceased_date_of_birth=None, town_leader_amount=None,
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
        # 'When a king or queen or anyone from the town elders dies, the
        # community price can be set again.' The one funeral where this
        # actually matters is the Town Elder's own — an explicit
        # per-funeral override, the same "supply an amount for this
        # funeral only" flexibility own_family_amount above already has,
        # rather than always inheriting the community's standing default.
        town_leader_amount=(
            town_leader_amount if town_leader_amount is not None else community.default_town_leader_amount
        ),
        # 'The expected contribution may differ according to the
        # elder's official position.' Automatically inherited from the
        # community's own per-title defaults — no separate override
        # parameter needed here the way town_leader_amount above has,
        # since these are already-nullable community-wide settings a
        # Traditional Leader configures once, not a per-funeral choice.
        town_elder_chief_amount=community.default_town_elder_chief_amount,
        town_elder_queen_mother_amount=community.default_town_elder_queen_mother_amount,
        town_elder_linguist_amount=community.default_town_elder_linguist_amount,
        town_elder_other_amount=community.default_town_elder_other_amount,
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


@transaction.atomic
def request_funeral_event(
    *, community, deceased_name, deceased_gender, deceased_family,
    date_of_death, collection_start_date, burial_date=None, funeral_date=None,
    collection_end_date=None, own_family_amount=None, general_male_amount=None,
    general_female_amount=None, actor=None, deceased_date_of_birth=None, town_leader_amount=None,
    rep_member=None, rep_new_username: str = None, rep_new_password: str = None,
):
    """
    'Is the family head who will open the ledger when there's a
    funeral.' Creates the SAME kind of FuneralEvent create_funeral_event
    does — same rate snapshotting, same validation — except it starts in
    PENDING_APPROVAL and deliberately does NOT call generate_obligations:
    nobody is billed a single cedi until approve_funeral_opening() below
    has been called by two distinct qualifying people. This is the
    concrete meaning of "before every member is billed."

    'The deceased family head will submit a representative to the
    community committee... so the ledger opening has to ask for that
    person to be nominated.' When rep_member or rep_new_username/
    rep_new_password are provided, a Bereaved Rep nomination is created
    in the SAME transaction as the funeral request — see
    families.services.create_bereaved_rep for what happens next (starts
    pending, needs a Community Admin/Secretary/Chairman to approve).
    Deliberately optional: a Family Head can still request an opening
    without nominating anyone yet and use the separate Bereaved Rep
    flow on the Families page later.
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
        town_leader_amount=(
            town_leader_amount if town_leader_amount is not None else community.default_town_leader_amount
        ),
        town_elder_chief_amount=community.default_town_elder_chief_amount,
        town_elder_queen_mother_amount=community.default_town_elder_queen_mother_amount,
        town_elder_linguist_amount=community.default_town_elder_linguist_amount,
        town_elder_other_amount=community.default_town_elder_other_amount,
        created_by=actor,
    )

    if rep_member is not None or (rep_new_username and rep_new_password):
        from families.services import create_bereaved_rep
        create_bereaved_rep(
            family=deceased_family, actor=actor, member=rep_member,
            new_username=rep_new_username, new_password=rep_new_password,
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


_FAMILY_DESK_APPROVER_ROLES = {"family_secretary", "family_head"}
_COMMUNITY_DESK_APPROVER_ROLES = {"chairman", "secretary"}
# Still used by _can_manage_memorial_page_for and _can_organize_committee_for
# below — unrelated to desk/collector assignment, deliberately unaffected
# by that redesign.
_DESK_ASSIGNER_COMMUNITY_WIDE_ROLES = {"community_admin", "chairman", "secretary"}


def _can_assign_desk_workers_for(actor, funeral: FuneralEvent, desk_type: str) -> bool:
    """
    'Only the community treasurer, community admin and the family
    treasurer are only allow to create or remove collector or assigned
    collector.' Narrower than before on purpose — Chairman/Secretary
    and Family Head no longer directly open a desk themselves; they're
    the two required APPROVERS instead (see approve_desk_assignment).
    Community Admin+ can still open any desk type directly, on any
    funeral — that authority already is the approval this workflow
    otherwise waits on.
    """
    if actor.is_superuser or actor.role == "community_admin":
        return True
    if desk_type == FuneralDeskAssignment.DeskType.FAMILY:
        own_member = getattr(actor, "member_profile", None)
        return bool(own_member and own_member.family_id == funeral.deceased_family_id and actor.role == "family_treasurer")
    return actor.role == "treasurer" and actor.community_id == funeral.community_id


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

    Every Treasurer-initiated assignment starts inactive — a real
    pending request, granting no actual desk access yet (see
    funerals.permissions.is_desk_worker_for) — until BOTH of two
    specific, named roles approve it (Family Secretary and Family Head
    for a Family desk; Chairman and Secretary for a Community/Elders/
    Guest desk — see approve_desk_assignment). Only a Community Admin
    opening any desk type directly themselves is active immediately:
    that authority already IS the approval.
    """
    from accounts.models import Role, User

    if desk_type not in FuneralDeskAssignment.DeskType.values:
        raise ValidationError(f"'{desk_type}' isn't a valid desk type.")
    if not _can_assign_desk_workers_for(actor, funeral, desk_type):
        raise ValidationError(
            "Only this community's own Treasurer can open a Community, Elders, or Guest desk. "
            "A Family desk can only be opened by this specific family's own Treasurer. "
            "Community Admin can open any desk type directly."
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

    is_directly_approved = bool(actor.is_superuser or actor.role == "community_admin")
    assignment, _ = FuneralDeskAssignment.objects.update_or_create(
        funeral_event=funeral, user=user, defaults={
            "desk_type": desk_type, "assigned_by": actor, "is_active": is_directly_approved,
            "approved_by": actor if is_directly_approved else None,
            "approved_at": timezone.now() if is_directly_approved else None,
        }
    )
    return assignment


def approve_desk_assignment(*, assignment: FuneralDeskAssignment, actor) -> FuneralDeskAssignment:
    """
    'The family treasurer needs the approval of the family secretary
    and the family head... the community treasurer also needs the
    community chairman and the secretary to approve.' Two specific,
    named roles — not just any two people — must each individually
    approve before this activates. Recording this actor's own
    approval, then checking whether both required roles are now
    genuinely represented among everyone who's approved so far.
    """
    from .models import FuneralDeskAssignmentApproval

    if assignment.desk_type == FuneralDeskAssignment.DeskType.FAMILY:
        required_roles = _FAMILY_DESK_APPROVER_ROLES
        own_member = getattr(actor, "member_profile", None)
        eligible = bool(
            actor.is_superuser
            or (actor.role in required_roles and own_member and own_member.family_id == assignment.funeral_event.deceased_family_id)
        )
        role_description = "this family's own Secretary or Head"
    else:
        required_roles = _COMMUNITY_DESK_APPROVER_ROLES
        eligible = bool(actor.is_superuser or (actor.role in required_roles and actor.community_id == assignment.funeral_event.community_id))
        role_description = "this community's own Chairman or Secretary"

    if not eligible:
        raise ValidationError(f"Only {role_description} can approve this desk assignment.")
    if assignment.is_active:
        return assignment

    FuneralDeskAssignmentApproval.objects.get_or_create(
        desk_assignment=assignment, approved_by=actor, defaults={"approved_by_role": actor.role},
    )

    approved_roles = set(assignment.approvals.values_list("approved_by_role", flat=True))
    if required_roles.issubset(approved_roles) or actor.is_superuser:
        assignment.is_active = True
        assignment.approved_by = actor
        assignment.approved_at = timezone.now()
        assignment.save(update_fields=["is_active", "approved_by", "approved_at"])
    return assignment


def list_pending_desk_assignments_for(actor):
    """
    This specific person's own approval queue — every pending desk
    assignment where they're eligible to approve and haven't yet.
    Replaces the earlier Community-Admin-only queue, since approval
    authority now belongs to Family Secretary/Head and Chairman/
    Secretary instead.
    """
    own_member = getattr(actor, "member_profile", None)
    pending = FuneralDeskAssignment.objects.filter(is_active=False).exclude(approvals__approved_by=actor)

    if actor.is_superuser or actor.role == "community_admin":
        return pending.filter(funeral_event__community=actor.community).select_related("user", "funeral_event")
    if actor.role in _FAMILY_DESK_APPROVER_ROLES and own_member:
        return pending.filter(
            desk_type=FuneralDeskAssignment.DeskType.FAMILY, funeral_event__deceased_family_id=own_member.family_id,
        ).select_related("user", "funeral_event")
    if actor.role in _COMMUNITY_DESK_APPROVER_ROLES:
        return pending.filter(
            funeral_event__community=actor.community,
        ).exclude(desk_type=FuneralDeskAssignment.DeskType.FAMILY).select_related("user", "funeral_event")
    return FuneralDeskAssignment.objects.none()


def remove_desk_worker(*, funeral: FuneralEvent, user, actor) -> None:
    existing = FuneralDeskAssignment.objects.filter(funeral_event=funeral, user=user).first()
    if existing is None:
        return
    if not _can_assign_desk_workers_for(actor, funeral, existing.desk_type):
        raise ValidationError(
            "Only this community's own Treasurer or Admin can remove someone from a Community, "
            "Elders, or Guest desk. A Family desk can only be managed by this family's own Treasurer or Community Admin."
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
    """
    'An authorized administrator should be able to initiate a reversal
    or correction' — the request step. Nothing about the payment or the
    obligation's balance changes yet; that only happens once a
    DIFFERENT authorized person approves it, below.

    'Collectors should have access to edit, especially when they make
    mistakes.' Extended, deliberately narrowly: a Collector can request
    a reversal, but ONLY for a payment they themselves collected — not
    broad reversal authority over anyone's payment community-wide, just
    a real way to flag their own error the moment they catch it. Still
    goes through the same two-person approval below; this only ever
    grants the ability to REQUEST a correction, never to make one
    unilaterally.
    """
    is_collector_correcting_own_payment = actor.role == "collector" and payment.collected_by_id == actor.id
    if not (actor.is_superuser or actor.role in REVERSAL_REQUEST_ROLES or is_collector_correcting_own_payment):
        raise ValidationError("Only the Treasurer, Financial Secretary, Secretary, Chairman, Community Admin, or the Collector who took this specific payment can request a reversal.")
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


@transaction.atomic
def record_payments_across_active_funerals(*, member, method: str, collector_name: str, collector=None):
    """
    'Sometimes there can be more than two funerals and the collectors
    have to key their payment into the system — since it's a community
    ledger, community members are mandatory to pay all — so the system
    should be more efficient and friendly, so it can be faster.'

    Settles EVERY currently outstanding obligation this member has
    across every active funeral in one call, instead of a collector
    repeating the same search-and-submit for each funeral separately.
    Deliberately processes oldest funeral first (ascending
    collection_start_date) — the exact order _find_older_unpaid_obligation
    itself requires, so each payment in the batch genuinely clears the
    way for the next one rather than tripping the debt-priority check
    against a sibling payment from the very same batch.

    Reuses record_payment for every single obligation rather than
    duplicating its logic, so idempotency, the debt-priority rule, and
    suspicious-transaction flagging all apply here exactly as they do
    for a single payment — there is no separate, parallel code path to
    keep in sync. Always pays the exact balance owed on each obligation
    (never a lump sum split across them), so there's deliberately no
    credit_overpayment_to_wallet option here — that only makes sense
    for a single, specific amount tendered against a single obligation,
    which is what record_payment on its own already handles.

    Returns the list of ContributionPayment rows created, oldest funeral
    first. An empty list (nothing owed) is a valid, non-error result.
    """
    obligations = (
        ContributionObligation.objects
        .filter(member=member, community=member.community, funeral_event__status=FuneralEvent.Status.ACTIVE)
        .filter(amount_paid__lt=F("expected_amount"))
        .select_related("funeral_event")
        .order_by("funeral_event__collection_start_date")
    )
    payments = []
    for obligation in obligations:
        payment = record_payment(
            obligation=obligation, amount=obligation.balance, method=method,
            collector=collector, collector_name=collector_name,
        )
        payments.append(payment)
    return payments


def apply_wallet_to_obligation(*, obligation: ContributionObligation, amount: Decimal, actor=None) -> ContributionPayment:
    """
    Spending an existing wallet credit against a real obligation — the
    other half of the same feature: a credit that can never actually
    be used toward anything isn't a real credit. A genuine
    ContributionPayment record either way, method='wallet', so it
    shows in every ledger, receipt, and report exactly like any other
    payment — the member's own money, just paid in advance.
    """
    from members.services import debit_wallet

    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if amount > obligation.balance:
        raise ValidationError(f"Only {obligation.balance} is owed on this obligation — can't apply {amount} from the wallet.")

    debit_wallet(member=obligation.member, amount=amount, actor=actor, note=f"Applied to {obligation.funeral_event.deceased_name}'s funeral")

    payment = ContributionPayment.objects.create(
        obligation=obligation, amount=amount, method=ContributionPayment.Method.WALLET,
        receipt_number=_generate_receipt_number(obligation.community),
        collected_by=actor, collector_name="Wallet credit (self-service)",
    )
    obligation.amount_paid = obligation.amount_paid + amount
    obligation.save(update_fields=["amount_paid", "updated_at"])
    # A payment settled from a member's own pre-loaded wallet is still
    # real money landing against this specific ledger — it must route
    # to the matching community/family/town-elder wallet exactly like
    # every other payment method does, never a silent exception to
    # that rule just because the money came from a different source.
    credit_ledger_wallet_for_payment(payment=payment, amount=amount)
    return payment


def get_or_create_ledger_wallet(*, community, scope: str, family=None) -> "LedgerWallet":
    """'Created on first use' — matches MemberWallet's own convention rather than pre-creating a row for every community/family up front."""
    family_scoped = {LedgerWallet.Scope.FAMILY, LedgerWallet.Scope.ASUPEDE}
    lookup = {"community": community, "scope": scope, "family": family if scope in family_scoped else None}
    wallet, _ = LedgerWallet.objects.get_or_create(**lookup)
    return wallet


def credit_ledger_wallet_for_payment(*, payment: ContributionPayment, amount: Decimal) -> "LedgerWallet":
    """
    The routing rule itself — 'when a member pays for family
    contribution the money should go to family wallet, when town
    elder pays for contribution it should go to the town elders
    ledger, and when a member or guest pays to community ledger it
    should go to the community ledger.' Reads rate_type directly off
    the obligation this payment already belongs to — the same fact
    that already decided how much was owed, now deciding where the
    money that settled it actually lives.
    """
    obligation = payment.obligation
    scope = obligation.rate_type  # "own_family" | "general" | "town_elder" — matches LedgerWallet.Scope exactly
    family = obligation.funeral_event.deceased_family if scope == LedgerWallet.Scope.FAMILY else None

    wallet = get_or_create_ledger_wallet(community=obligation.community, scope=scope, family=family)
    LedgerWalletTransaction.objects.create(
        wallet=wallet, kind=LedgerWalletTransaction.Kind.CREDIT, amount=amount, source_payment=payment,
        note=f"Payment {payment.receipt_number} — {obligation.member.full_name} toward {obligation.funeral_event.deceased_name}'s funeral",
    )
    wallet.balance = wallet.balance + amount
    wallet.save(update_fields=["balance", "updated_at"])
    return wallet


# 'Each family should have their wallet being managed by the family
# treasurer... the town leader should also have their wallet as well.'
# Who may actually withdraw from (debit) each wallet scope — never
# Auditor for the community-wide one, matching the same review-only,
# never-action-taking authority already established for that role
# throughout this platform (dashboard.services._financial_officer_view).
_LEDGER_WALLET_WITHDRAWAL_ROLES = {
    LedgerWallet.Scope.COMMUNITY: {"community_admin", "treasurer", "financial_secretary"},
    LedgerWallet.Scope.FAMILY: {"family_head", "family_treasurer"},
    LedgerWallet.Scope.TOWN_ELDER: {"traditional_leader"},
    # 'Support the immediate family with the final burial preparations'
    # — the same people who already manage that family's ordinary
    # Ledger Wallet, since this money exists for that same family.
    LedgerWallet.Scope.ASUPEDE: {"family_head", "family_treasurer"},
}


def withdraw_from_ledger_wallet(*, wallet: "LedgerWallet", amount: Decimal, note: str, actor) -> "LedgerWallet":
    """
    The spending half of a Ledger Wallet — 'transparent since it's a
    transaction aspect,' so this is never a silent balance edit: every
    withdrawal is its own DEBIT transaction row, same as every credit
    already is. A wallet can never go negative — no withdrawal is ever
    allowed to exceed what's genuinely, currently held.
    """
    allowed_roles = _LEDGER_WALLET_WITHDRAWAL_ROLES[wallet.scope]
    if actor is not None and not actor.is_superuser and actor.role not in allowed_roles:
        raise ValidationError(f"'{actor.username}' isn't authorized to withdraw from this {wallet.get_scope_display()}.")
    if wallet.scope in (LedgerWallet.Scope.FAMILY, LedgerWallet.Scope.ASUPEDE) and actor is not None and not actor.is_superuser:
        own_member = getattr(actor, "member_profile", None)
        if not (own_member and own_member.family_id == wallet.family_id):
            raise ValidationError(f"'{actor.username}' can only withdraw from their own family's Ledger Wallet.")
    if amount <= 0:
        raise ValidationError("The withdrawal amount must be greater than zero.")
    if amount > wallet.balance:
        raise ValidationError(f"Only {wallet.balance} is available in this wallet — a withdrawal can never exceed the real balance held.")
    if not note.strip():
        raise ValidationError("A note explaining what this withdrawal is for is required — transparency for a real transaction.")

    LedgerWalletTransaction.objects.create(
        wallet=wallet, kind=LedgerWalletTransaction.Kind.DEBIT, amount=amount, note=note.strip(), actor=actor,
    )
    wallet.balance = wallet.balance - amount
    wallet.save(update_fields=["balance", "updated_at"])

    from audit_log.services import record_event
    record_event(
        category="role", action="ledger_wallet_withdrawal", actor=actor, community=wallet.community,
        target_type="LedgerWallet", target_id=wallet.id, target_label=str(wallet),
        description=f"'{actor.username if actor else 'system'}' withdrew {amount} from {wallet}: {note.strip()}",
    )
    return wallet


def list_ledger_wallet_transactions(*, wallet: "LedgerWallet"):
    return wallet.transactions.select_related("source_payment", "actor").all()


def ledger_wallets_for(*, actor):
    """
    Every Ledger Wallet this specific account is authorized to view —
    the same scoping _LEDGER_WALLET_WITHDRAWAL_ROLES already defines,
    since viewing and withdrawing are governed by the same underlying
    authority, never two rules that could quietly disagree. A
    Community Admin/Treasurer/Financial Secretary sees the community
    wallet; a Family Head/Treasurer sees only their own family's; the
    Traditional Leader sees the Town Elders wallet.
    """
    if actor is None or actor.community_id is None:
        return LedgerWallet.objects.none()
    if actor.is_superuser:
        return LedgerWallet.objects.filter(community=actor.community)

    if actor.role in _LEDGER_WALLET_WITHDRAWAL_ROLES[LedgerWallet.Scope.COMMUNITY]:
        return LedgerWallet.objects.filter(community=actor.community, scope=LedgerWallet.Scope.COMMUNITY)
    if actor.role in _LEDGER_WALLET_WITHDRAWAL_ROLES[LedgerWallet.Scope.TOWN_ELDER]:
        return LedgerWallet.objects.filter(community=actor.community, scope=LedgerWallet.Scope.TOWN_ELDER)
    if actor.role in _LEDGER_WALLET_WITHDRAWAL_ROLES[LedgerWallet.Scope.FAMILY]:
        own_member = getattr(actor, "member_profile", None)
        if own_member is None or own_member.family_id is None:
            return LedgerWallet.objects.none()
        return LedgerWallet.objects.filter(
            community=actor.community, scope__in=[LedgerWallet.Scope.FAMILY, LedgerWallet.Scope.ASUPEDE], family_id=own_member.family_id
        )
    return LedgerWallet.objects.none()


def record_payment(
    *, obligation: ContributionObligation, amount: Decimal, method: str,
    collector=None, client_op_id=None, collector_name: str = "", credit_overpayment_to_wallet: bool = False,
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

    'Any collector have to input in their names for them to know who
    they paid to.' A real, required name typed at the moment of
    collection — collected_by (the logged-in account) alone doesn't
    always identify who physically took the payment, since a desk
    assignment can genuinely be shared by more than one real person
    working the same table.

    'If he doesn't get change, money balance should be credited to the
    member's wallet.' When set, `amount` is what the member actually
    handed over — only what's genuinely still owed on THIS obligation is
    ever applied to it (so it settles at exactly "paid", never shows a
    confusing "overpaid"), and the real excess becomes a genuine,
    reusable wallet credit usable against a completely different, future
    obligation — not just a number stranded on this one via
    overpaid_amount.
    """
    if client_op_id:
        existing = ContributionPayment.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing
    if not collector_name.strip():
        raise ValidationError("The collector's own name is required when recording a payment.")

    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    if method == ContributionPayment.Method.WALLET:
        raise ValidationError("'Wallet credit' isn't a method to record here — use apply_wallet_to_obligation to actually spend a wallet balance.")

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

    # 'One person is not allowed to pay twice of each funeral, but can
    # decide to pay more than the required amount.' The two are
    # different things: paying GH₵60 in ONE payment when GH₵50 is owed
    # is a legitimate, allowed overpayment (already handled below); a
    # SECOND, separate payment against an obligation that's already
    # fully settled is "paying twice" — checked here, BEFORE this new
    # payment is even considered, using the balance as it stood before
    # this call. Deliberately checked after the idempotency short
    # -circuit above (so a genuine retry of an already-succeeded
    # payment still succeeds) but before the overpayment-to-wallet path
    # below, which already has its own, more specific message for this
    # same state.
    if obligation.balance <= 0 and not credit_overpayment_to_wallet:
        raise ValidationError(
            f"{obligation.member.full_name} has already fully paid toward {obligation.funeral_event.deceased_name}'s "
            f"funeral — a second, separate payment against the same obligation isn't allowed."
        )

    wallet_credit_amount = Decimal("0")
    amount_to_apply = amount
    if credit_overpayment_to_wallet and amount > obligation.balance:
        wallet_credit_amount = amount - obligation.balance
        amount_to_apply = obligation.balance
        if amount_to_apply <= 0:
            raise ValidationError("This obligation is already fully paid — there's nothing left to apply, only a wallet credit to record.")

    try:
        payment = ContributionPayment.objects.create(
            obligation=obligation,
            amount=amount_to_apply,
            method=method,
            receipt_number=_generate_receipt_number(obligation.community),
            collected_by=collector,
            collector_name=collector_name.strip(),
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

    obligation.amount_paid = obligation.amount_paid + amount_to_apply
    obligation.save(update_fields=["amount_paid", "updated_at"])

    # 'When a member pays for family contribution the money should go
    # to family wallet, when town elder pays for contribution it
    # should go to the town elders ledger, and when a member or guest
    # pays to community ledger it should go to the community ledger.'
    # Routed automatically off the SAME rate_type this obligation
    # already carries — never a second, separate decision that could
    # drift out of sync with what the obligation itself says. Credits
    # exactly amount_to_apply (the portion that actually settled this
    # obligation) — any excess routed to the member's own personal
    # wallet below is THEIR money, not this ledger's.
    credit_ledger_wallet_for_payment(payment=payment, amount=amount_to_apply)

    if wallet_credit_amount > 0:
        from members.services import credit_wallet
        credit_wallet(
            member=obligation.member, amount=wallet_credit_amount, actor=collector,
            note=f"No change given on payment {payment.receipt_number} for {obligation.funeral_event.deceased_name}'s funeral",
        )

    from realtime.broadcast import broadcast_funeral_ledger_event
    broadcast_funeral_ledger_event(
        str(obligation.funeral_event_id), "payment_recorded",
        {
            "obligation_id": str(obligation.id),
            "member_name": obligation.member.full_name,
            "amount": str(amount_to_apply),
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
        "town_elder": _bucket(ContributionObligation.RateType.TOWN_ELDER),
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


# ============================================================
# ASUPEDEƐ — the communal burial-morning token, kept genuinely
# separate from the mandatory Family/Community/Town Elder ledger.
# See funerals.models.AsupedeObligation for why this is its own
# model rather than a fourth ContributionObligation.RateType.
# ============================================================

def activate_asupede(*, funeral: FuneralEvent, amount: Decimal, collection_start=None, collection_end=None, actor=None) -> list:
    """
    'The funeral should therefore have enough information for the
    system to identify the relevant collection period' — a deliberate,
    explicit activation step rather than something every funeral gets
    automatically, since the exact burial-morning timing is often only
    known once the burial date itself is confirmed, well after the
    funeral's own ledger has already been open for days.

    Eligibility reuses eligible_members_queryset — 'the community
    should be able to determine who is expected to make the Asupedeɛ
    contribution... allow the eligibility policy to be configured' —
    the exact same, already-configurable mechanism the mandatory
    ledger's own enrollment already uses, rather than a second,
    parallel eligibility concept.

    Safe to call more than once on the same funeral (e.g. to correct
    the amount or window before any payment has been made) —
    get_or_create per member means re-running this never duplicates
    an existing obligation, only ever fills in newly-eligible members.
    """
    if amount <= 0:
        raise ValidationError("The Asupedeɛ amount must be greater than zero.")
    if collection_start and collection_end and collection_start >= collection_end:
        raise ValidationError("The Asupedeɛ collection window's start must be before its end.")

    from contribution_rules.services import eligible_members_queryset

    funeral.asupede_amount = amount
    funeral.asupede_collection_start = collection_start
    funeral.asupede_collection_end = collection_end
    funeral.save(update_fields=["asupede_amount", "asupede_collection_start", "asupede_collection_end"])

    obligations = []
    for member in eligible_members_queryset(funeral.community):
        obligations.append(
            AsupedeObligation(community=funeral.community, funeral_event=funeral, member=member, expected_amount=amount)
        )
    AsupedeObligation.objects.bulk_create(obligations, ignore_conflicts=True)

    from audit_log.services import record_event
    record_event(
        category="finance", action="asupede_activated", actor=actor, community=funeral.community,
        target_type="FuneralEvent", target_id=funeral.id, target_label=funeral.deceased_name,
        description=f"Asupedeɛ activated for {funeral.deceased_name}'s funeral at {amount}"
        + (f", collectible {collection_start} to {collection_end}" if collection_start else "")
        + (f" by '{actor.username}'." if actor else "."),
    )
    return list(funeral.asupede_obligations.all())


def _generate_asupede_receipt_number(community) -> str:
    prefix = f"{community.slug.upper()[:8]}-ASUPEDE-{timezone.now():%Y%m%d}"
    for _ in range(5):
        candidate = f"{prefix}-{secrets.token_hex(3).upper()}"
        if not AsupedePayment.objects.filter(receipt_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique Asupedeɛ receipt number; please retry.")


def record_asupede_payment(
    *, obligation: "AsupedeObligation", amount: Decimal, method: str,
    collector=None, collector_name: str = "", client_op_id=None,
) -> "AsupedePayment":
    """
    Mirrors funerals.services.record_payment's own rules exactly —
    minimum-not-cap, a required collector name, no second payment once
    already fully settled, full idempotency on client_op_id — plus the
    one genuinely new rule this ledger needs: a payment attempted
    outside the configured collection window is rejected outright.
    """
    if client_op_id:
        existing = AsupedePayment.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing

    funeral = obligation.funeral_event
    now = timezone.now()
    if funeral.asupede_collection_start and now < funeral.asupede_collection_start:
        raise ValidationError(
            f"Asupedeɛ collection for {funeral.deceased_name}'s funeral hasn't opened yet "
            f"(opens {funeral.asupede_collection_start})."
        )
    if funeral.asupede_collection_end and now > funeral.asupede_collection_end:
        raise ValidationError(
            f"Asupedeɛ collection for {funeral.deceased_name}'s funeral closed at {funeral.asupede_collection_end}."
        )

    if not collector_name.strip():
        raise ValidationError("The collector's own name is required when recording a payment.")
    if obligation.balance <= 0:
        raise ValidationError(
            f"{obligation.member.full_name} has already fully paid Asupedeɛ for {funeral.deceased_name}'s "
            f"funeral — a second, separate payment against the same obligation isn't allowed."
        )

    try:
        payment = AsupedePayment.objects.create(
            obligation=obligation, amount=amount, method=method,
            receipt_number=_generate_asupede_receipt_number(obligation.community),
            collected_by=collector, collector_name=collector_name.strip(), client_op_id=client_op_id,
        )
    except IntegrityError:
        if client_op_id:
            existing = AsupedePayment.objects.filter(client_op_id=client_op_id).first()
            if existing:
                return existing
        raise

    obligation.amount_paid = obligation.amount_paid + amount
    obligation.save(update_fields=["amount_paid", "updated_at"])

    # 'Support the immediate family with the final burial
    # preparations' — routed to that same family's Ledger Wallet, its
    # own distinct scope so it never gets folded into (or mistaken
    # for) the family's ordinary mandatory-contribution wallet.
    wallet = get_or_create_ledger_wallet(community=obligation.community, scope=LedgerWallet.Scope.ASUPEDE, family=funeral.deceased_family)
    LedgerWalletTransaction.objects.create(
        wallet=wallet, kind=LedgerWalletTransaction.Kind.CREDIT, amount=amount,
        note=f"Asupedeɛ {payment.receipt_number} — {obligation.member.full_name} toward {funeral.deceased_name}'s funeral",
    )
    wallet.balance = wallet.balance + amount
    wallet.save(update_fields=["balance", "updated_at"])

    return payment


def asupede_summary(funeral: FuneralEvent) -> dict:
    """'For each funeral, authorized users should be able to see a complete contribution overview' — the Asupedeɛ slice of it."""
    from django.db.models import Sum

    obligations = funeral.asupede_obligations.all()
    expected_total = obligations.aggregate(total=Sum("expected_amount"))["total"] or Decimal("0")
    paid_total = obligations.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
    return {
        "active": funeral.asupede_amount is not None,
        "amount": str(funeral.asupede_amount) if funeral.asupede_amount is not None else None,
        "collection_start": funeral.asupede_collection_start.isoformat() if funeral.asupede_collection_start else None,
        "collection_end": funeral.asupede_collection_end.isoformat() if funeral.asupede_collection_end else None,
        "obligation_count": obligations.count(),
        "expected_total": str(expected_total),
        "collected_total": str(min(paid_total, expected_total)),
        "outstanding_total": str(max(expected_total - paid_total, Decimal("0"))),
        "additional_support_total": str(max(paid_total - expected_total, Decimal("0"))),
    }


# ============================================================
# IN-LAW CONTRIBUTION — a request-and-approval workflow, the
# opposite of every other ledger's auto-enrollment. See
# funerals.models.InLawContributionRequest for why this targets a
# whole family rather than an individual member.
# ============================================================

# Who may INITIATE a request — 'the deceased family should be able to
# initiate an In-Law Contribution Request' — the deceased's own
# family leadership, or any community-wide executive acting on the
# family's behalf.
_IN_LAW_REQUEST_ROLES = {"family_head", "family_secretary", "family_treasurer", "community_admin", "chairman", "secretary"}
# Who may APPROVE — the same community-wide executive authority
# already governing every other contribution rule on this platform
# (contribution_rules.permissions.CanManageContributionRules),
# deliberately never the requesting family itself — 'only after
# approval should the system generate the actual financial
# obligation,' and approving your own request would defeat the point
# of a separate approval step entirely.
_IN_LAW_APPROVAL_ROLES = {"community_admin", "chairman", "secretary"}


def request_in_law_contribution(
    *, funeral: FuneralEvent, in_law_family, relationship: str, requested_amount: Decimal, reason: str = "", actor,
) -> "InLawContributionRequest":
    """'The request should identify: Funeral, Deceased, Deceased family, In-law family, Relevant relationship, Requested amount, Reason/notes.'"""
    from .models import InLawContributionRequest

    if actor is not None and not actor.is_superuser and actor.role not in _IN_LAW_REQUEST_ROLES:
        raise ValidationError(f"'{actor.username}' isn't authorized to request an In-Law contribution.")
    if actor is not None and not actor.is_superuser and actor.role in ("family_head", "family_secretary", "family_treasurer"):
        own_member = getattr(actor, "member_profile", None)
        if not (own_member and own_member.family_id == funeral.deceased_family_id):
            raise ValidationError(f"'{actor.username}' can only request an In-Law contribution for their own family's funeral.")
    if in_law_family.id == funeral.deceased_family_id:
        raise ValidationError("The in-law family must be a different family from the deceased's own family.")
    if in_law_family.community_id != funeral.community_id:
        raise ValidationError("The in-law family must be in the same community as this funeral.")
    if requested_amount <= 0:
        raise ValidationError("The requested amount must be greater than zero.")
    if not relationship.strip():
        raise ValidationError("The relevant relationship must be described.")

    request = InLawContributionRequest.objects.create(
        community=funeral.community, funeral_event=funeral, in_law_family=in_law_family,
        relationship=relationship.strip(), requested_amount=requested_amount, reason=reason.strip(), requested_by=actor,
    )

    from audit_log.services import record_event
    record_event(
        category="finance", action="in_law_contribution_requested", actor=actor, community=funeral.community,
        target_type="Family", target_id=in_law_family.id, target_label=in_law_family.name,
        description=f"In-Law contribution of {requested_amount} requested from '{in_law_family.name}' for {funeral.deceased_name}'s funeral ({relationship})"
        + (f" by '{actor.username}'." if actor else "."),
    )
    return request


@transaction.atomic
def decide_in_law_contribution_request(*, request: "InLawContributionRequest", actor, decision: str) -> "InLawContributionRequest":
    """
    'Only after approval should the system generate the actual
    financial obligation.' Approving is what actually creates the
    InLawObligation — rejecting simply closes the request with
    nothing further generated at all.
    """
    from .models import InLawContributionRequest, InLawObligation

    if request.status != InLawContributionRequest.Status.PENDING:
        raise ValidationError(f"This request is already {request.status} — there's nothing left to decide.")
    if actor is not None and not actor.is_superuser and actor.role not in _IN_LAW_APPROVAL_ROLES:
        raise ValidationError(f"'{actor.username}' isn't authorized to approve or reject an In-Law contribution request.")
    if decision not in ("approve", "reject"):
        raise ValidationError(f"'{decision}' isn't a real decision — expected 'approve' or 'reject'.")

    request.status = InLawContributionRequest.Status.APPROVED if decision == "approve" else InLawContributionRequest.Status.REJECTED
    request.decided_by = actor
    request.decided_at = timezone.now()
    request.save(update_fields=["status", "decided_by", "decided_at"])

    from audit_log.services import record_event
    if decision == "approve":
        InLawObligation.objects.create(
            request=request, community=request.community, funeral_event=request.funeral_event,
            in_law_family=request.in_law_family, expected_amount=request.requested_amount,
        )
        record_event(
            category="finance", action="in_law_contribution_approved", actor=actor, community=request.community,
            target_type="Family", target_id=request.in_law_family.id, target_label=request.in_law_family.name,
            description=f"In-Law contribution of {request.requested_amount} from '{request.in_law_family.name}' approved"
            + (f" by '{actor.username}'." if actor else "."),
        )
    else:
        record_event(
            category="finance", action="in_law_contribution_rejected", actor=actor, community=request.community,
            target_type="Family", target_id=request.in_law_family.id, target_label=request.in_law_family.name,
            description=f"In-Law contribution request from '{request.in_law_family.name}' rejected"
            + (f" by '{actor.username}'." if actor else "."),
        )
    return request


def _generate_in_law_receipt_number(community) -> str:
    from .models import InLawPayment
    prefix = f"{community.slug.upper()[:8]}-INLAW-{timezone.now():%Y%m%d}"
    for _ in range(5):
        candidate = f"{prefix}-{secrets.token_hex(3).upper()}"
        if not InLawPayment.objects.filter(receipt_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate a unique In-Law receipt number; please retry.")


def record_in_law_payment(
    *, obligation: "InLawObligation", amount: Decimal, method: str,
    collector=None, collector_name: str = "", paid_by_member=None, client_op_id=None,
) -> "InLawPayment":
    """Same minimum-not-cap, required-collector-name, no-double-payment rules as every other ledger's own record_payment."""
    from .models import InLawPayment

    if client_op_id:
        existing = InLawPayment.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing
    if not collector_name.strip():
        raise ValidationError("The collector's own name is required when recording a payment.")
    if paid_by_member is not None and paid_by_member.family_id != obligation.in_law_family_id:
        raise ValidationError(f"{paid_by_member.full_name} isn't a member of {obligation.in_law_family.name} — this is that family's own obligation.")
    if obligation.balance <= 0:
        raise ValidationError(
            f"{obligation.in_law_family.name} has already fully paid their In-Law contribution for "
            f"{obligation.funeral_event.deceased_name}'s funeral — a second, separate payment isn't allowed."
        )

    try:
        payment = InLawPayment.objects.create(
            obligation=obligation, amount=amount, method=method,
            receipt_number=_generate_in_law_receipt_number(obligation.community),
            collected_by=collector, collector_name=collector_name.strip(), paid_by_member=paid_by_member, client_op_id=client_op_id,
        )
    except IntegrityError:
        if client_op_id:
            existing = InLawPayment.objects.filter(client_op_id=client_op_id).first()
            if existing:
                return existing
        raise

    obligation.amount_paid = obligation.amount_paid + amount
    obligation.save(update_fields=["amount_paid", "updated_at"])
    return payment


def list_in_law_requests(*, funeral: FuneralEvent):
    return list(funeral.in_law_requests.select_related("in_law_family", "requested_by").all())


def in_law_summary(funeral: FuneralEvent) -> dict:
    """'For each funeral, authorized users should be able to see a complete contribution overview' — the In-Law slice of it, across every request regardless of its decision so far."""
    from django.db.models import Sum

    from .models import InLawObligation

    requests = funeral.in_law_requests.all()
    obligations = InLawObligation.objects.filter(funeral_event=funeral)
    expected_total = obligations.aggregate(total=Sum("expected_amount"))["total"] or Decimal("0")
    paid_total = obligations.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
    return {
        "request_count": requests.count(),
        "pending_count": requests.filter(status="pending").count(),
        "approved_count": requests.filter(status="approved").count(),
        "rejected_count": requests.filter(status="rejected").count(),
        "expected_total": str(expected_total),
        "collected_total": str(min(paid_total, expected_total)),
        "outstanding_total": str(max(expected_total - paid_total, Decimal("0"))),
    }

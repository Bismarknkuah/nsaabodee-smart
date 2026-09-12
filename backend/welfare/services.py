from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    CampaignApproval,
    ContributionCampaign,
    ContributionCategory,
    WelfareObligation,
    WelfarePayment,
    WelfareRequest,
)

COMMUNITY_WIDE_INITIATION_ROLES = {"community_admin", "chairman", "secretary"}


# --- Categories ------------------------------------------------------------

def create_contribution_category(
    *, community, name: str, purpose: str = "", is_mandatory: bool = True,
    amount_type: str = ContributionCategory.AmountType.FIXED, fixed_amount: Decimal = None,
    frequency: str = ContributionCategory.Frequency.ONE_TIME, required_family_approvals: int = 2, actor=None,
) -> ContributionCategory:
    """'The Community Administrator should be able to create unlimited contribution categories.'"""
    if actor is not None and not actor.is_superuser and actor.role != "community_admin":
        raise ValidationError("Only the Community Administrator can create a contribution category.")
    if amount_type == ContributionCategory.AmountType.FIXED and not fixed_amount:
        raise ValidationError("A fixed-amount category needs a real fixed amount.")
    if required_family_approvals < 1:
        raise ValidationError("At least one family approval must be required.")

    return ContributionCategory.objects.create(
        community=community, name=name.strip(), purpose=purpose.strip(), is_mandatory=is_mandatory,
        amount_type=amount_type, fixed_amount=fixed_amount, frequency=frequency,
        required_family_approvals=required_family_approvals, created_by=actor,
    )


def deactivate_contribution_category(*, category: ContributionCategory, actor=None) -> ContributionCategory:
    if actor is not None and not actor.is_superuser and actor.role != "community_admin":
        raise ValidationError("Only the Community Administrator can deactivate a contribution category.")
    category.is_active = False
    category.save(update_fields=["is_active"])
    return category


def list_categories(community):
    return ContributionCategory.objects.filter(community=community, is_active=True)


# --- Campaign initiation -----------------------------------------------------

def _eligible_members_for(campaign: ContributionCampaign):
    """
    Two independent decisions, applied in order: which population is
    even IN SCOPE (family vs community, unchanged from before), then
    WHICH of those eligible members are actually targeted
    (target_type — 'do not confuse owner with contributors'). A
    campaign left at the default ALL_ELIGIBLE behaves exactly as
    every campaign did before target_type existed.
    """
    from contribution_rules.services import eligible_members_queryset
    from .models import CampaignTargetMember

    members = eligible_members_queryset(campaign.community)
    if campaign.family_id:
        # "When one family initiates it, it should only be within his
        # jurisdiction" — never any other family's members, no matter
        # how the campaign was created.
        members = members.filter(family_id=campaign.family_id)

    if campaign.target_type == ContributionCampaign.TargetType.TOWN_ELDERS:
        return members.filter(is_town_leader=True)
    if campaign.target_type == ContributionCampaign.TargetType.SELECTED_MEMBERS:
        selected_ids = CampaignTargetMember.objects.filter(campaign=campaign).values_list("member_id", flat=True)
        return members.filter(id__in=selected_ids)
    return members


@transaction.atomic
def generate_welfare_obligations(campaign: ContributionCampaign):
    """
    Fan-out: one WelfareObligation per eligible member — but only for
    a MANDATORY category. 'A voluntary campaign must NOT create a
    debt-like outstanding balance unless the business rules explicitly
    say so.' Pre-generating an obligation for every eligible member
    under a voluntary campaign would do exactly that — every member
    would show a balance owed on a campaign nobody has actually
    promised to pay anything toward. See record_voluntary_contribution
    below for how a voluntary campaign is actually paid into instead:
    an obligation is created only for someone who chooses to give,
    the moment they give, for exactly what they give.
    """
    if not campaign.category.is_mandatory:
        return 0
    members = _eligible_members_for(campaign)
    obligations = [
        WelfareObligation(community=campaign.community, campaign=campaign, member=member, expected_amount=campaign.amount)
        for member in members
    ]
    WelfareObligation.objects.bulk_create(obligations, ignore_conflicts=True)
    return len(obligations)


@transaction.atomic
def set_campaign_target_members(*, campaign: ContributionCampaign, member_ids: list, actor) -> int:
    """
    'Never allow scope to be changed casually after obligations have
    already been generated.' Same principle applied to WHO a campaign
    targets, not just its family/community scope — only settable
    while no obligation exists yet for this campaign at all, matching
    every other pre-activation-only rate/rule change on this platform.
    Replaces the whole list each call rather than incrementally
    adding/removing, so the set of targeted members is always exactly
    what was last specified — never an accumulation of stale entries.
    """
    from .models import CampaignTargetMember

    if campaign.obligations.exists():
        raise ValidationError("This campaign has already generated obligations — its targeted members can no longer be changed.")
    if not _is_authorized_for_campaign_administration(actor, campaign):
        raise ValidationError(f"'{actor.username}' isn't authorized to set this campaign's targeted members.")

    from members.models import Member
    members = Member.objects.filter(id__in=member_ids, community=campaign.community)
    if campaign.family_id:
        outside_family = members.exclude(family_id=campaign.family_id)
        if outside_family.exists():
            raise ValidationError("Every targeted member must belong to this campaign's own family.")

    CampaignTargetMember.objects.filter(campaign=campaign).delete()
    rows = [CampaignTargetMember(campaign=campaign, member=member, added_by=actor) for member in members]
    CampaignTargetMember.objects.bulk_create(rows)
    return len(rows)


@transaction.atomic
def initiate_community_campaign(*, category: ContributionCategory, title: str, amount: Decimal = None, due_date=None, actor) -> ContributionCampaign:
    """
    'When the community creates it, it affects all the community.' No
    approval step — community-wide leadership initiating IS the
    authority, the same way creating a funeral or an announcement
    doesn't need a second sign-off from itself. Active immediately;
    obligations generated for every eligible member community-wide.
    """
    if not actor.is_superuser and actor.role not in COMMUNITY_WIDE_INITIATION_ROLES:
        raise ValidationError("Only Community Admin, Chairman, or Secretary can start a community-wide contribution campaign.")
    if category.community_id != actor.community_id and not actor.is_superuser:
        raise ValidationError("This category doesn't belong to your community.")

    real_amount = _resolve_amount(category, amount)
    campaign = ContributionCampaign.objects.create(
        category=category, community=category.community, family=None, title=title.strip(),
        amount=real_amount, due_date=due_date, status=ContributionCampaign.Status.ACTIVE, initiated_by=actor,
    )
    generate_welfare_obligations(campaign)

    from notifications.services import notify_eligible_members_of_campaign
    notify_eligible_members_of_campaign(members=_eligible_members_for(campaign), campaign_title=campaign.title, community=campaign.community)

    from audit_log.services import record_event
    record_event(
        category="community", action="welfare_campaign_started", actor=actor, community=category.community,
        target_type="ContributionCampaign", target_id=campaign.id, target_label=campaign.title,
        description=f"Community-wide contribution campaign '{campaign.title}' started under '{category.name}'.",
    )
    return campaign


@transaction.atomic
def initiate_family_campaign(*, category: ContributionCategory, family, title: str, amount: Decimal = None, due_date=None, actor) -> ContributionCampaign:
    """
    'Any family can also use it for welfare, so when a family head
    initiates it, it needs the approval of two other family executives
    before his family members get billed... it should only be within
    his jurisdiction.' Starts PENDING_APPROVAL — no obligations exist
    yet, nobody is billed, until enough of the family's OWN executives
    (not the initiator) approve it. See decide_family_campaign below.
    """
    if actor.role != "family_head":
        raise ValidationError("Only a Family Head can initiate a family's own contribution campaign.")
    own_member = getattr(actor, "member_profile", None)
    if own_member is None or own_member.family_id != family.id:
        raise ValidationError("You can only initiate a campaign for your own family.")
    if category.community_id != family.community_id:
        raise ValidationError("This category doesn't belong to your community.")

    real_amount = _resolve_amount(category, amount)
    campaign = ContributionCampaign.objects.create(
        category=category, community=family.community, family=family, title=title.strip(),
        amount=real_amount, due_date=due_date, status=ContributionCampaign.Status.PENDING_APPROVAL, initiated_by=actor,
    )
    from audit_log.services import record_event
    record_event(
        category="community", action="welfare_campaign_requested", actor=actor, community=family.community,
        target_type="ContributionCampaign", target_id=campaign.id, target_label=campaign.title,
        description=f"'{family.name}' Family Head requested a '{category.name}' contribution campaign — awaiting {category.required_family_approvals} approval(s).",
    )
    return campaign


def _resolve_amount(category: ContributionCategory, amount: Decimal = None) -> Decimal:
    if category.amount_type == ContributionCategory.AmountType.FIXED:
        return category.fixed_amount
    if not amount or amount <= 0:
        raise ValidationError(f"'{category.name}' is a flexible-amount category — a real amount must be given.")
    return amount


# --- Family approval workflow -------------------------------------------------

def _is_this_familys_other_executive(user, family) -> bool:
    """
    'Two other family executives' — the family's own Secretary or
    Treasurer (the direct, named leadership fields on Family), or
    anyone holding a FamilyOfficerPosition for this family. Community-
    wide leadership can also approve, the same "reaches anywhere"
    authority they already have over every other family-scoped action.
    Never the campaign's own initiator — that's enforced separately.
    """
    if user.is_superuser or user.role in COMMUNITY_WIDE_INITIATION_ROLES:
        return True
    own_member = getattr(user, "member_profile", None)
    if own_member is None or own_member.family_id != family.id:
        return False
    if family.family_secretary_id == own_member.id or family.family_treasurer_id == own_member.id:
        return True
    from families.models import FamilyOfficerPosition
    return FamilyOfficerPosition.objects.filter(family=family, member=own_member).exists()


@transaction.atomic
def decide_family_campaign(*, campaign: ContributionCampaign, actor, approve: bool = True) -> ContributionCampaign:
    """
    Records one approval (or a rejection) toward a family-initiated
    campaign's required threshold. Meeting the threshold moves the
    campaign to FAMILY_APPROVED, not ACTIVE — 'it has to be approved
    by the community admin before it works for his community members'
    is a second, separate gate (see
    approve_family_campaign_by_community_admin below); nobody is
    billed off the family's own sign-off alone.
    """
    if campaign.family_id is None:
        raise ValidationError("Only a family-initiated campaign goes through this approval workflow.")
    if campaign.status != ContributionCampaign.Status.PENDING_APPROVAL:
        raise ValidationError(f"This campaign is '{campaign.status}' — it isn't waiting for approval.")
    if campaign.initiated_by_id == actor.id:
        raise ValidationError("The campaign's own initiator can't also approve it — it needs someone else's sign-off.")
    if not _is_this_familys_other_executive(actor, campaign.family):
        raise ValidationError("Only this family's own Secretary, Treasurer, an appointed officer, or community leadership can decide this.")

    if not approve:
        campaign.status = ContributionCampaign.Status.REJECTED
        campaign.save(update_fields=["status"])
        return campaign

    CampaignApproval.objects.get_or_create(campaign=campaign, approved_by=actor)
    distinct_approvals = campaign.approvals.values("approved_by_id").distinct().count()
    if distinct_approvals >= campaign.category.required_family_approvals:
        campaign.status = ContributionCampaign.Status.FAMILY_APPROVED
        campaign.save(update_fields=["status"])
        from audit_log.services import record_event
        record_event(
            category="community", action="welfare_campaign_family_approved", actor=actor, community=campaign.community,
            target_type="ContributionCampaign", target_id=campaign.id, target_label=campaign.title,
            description=f"'{campaign.title}' approved by {distinct_approvals} family executive(s) — awaiting the Community Administrator's final sign-off before {campaign.family.name}'s members are billed.",
        )
    return campaign


def approve_family_campaign_by_community_admin(*, campaign: ContributionCampaign, actor, approve: bool = True) -> ContributionCampaign:
    """
    'Each family head should have the welfare contribution features
    which has to be approved by the community admin before it works
    for his community members.' The second, final gate — only after
    this does anyone actually get billed. Only this specific
    community's own Community Admin (or superuser) can decide it; a
    Temporary/rental community's own Community Admin account is the
    same role, so this already covers that case without any special
    handling. A campaign the family's own executives already approved
    can still be rejected here — otherwise a Community Admin who
    disagrees (the amount, the category, anything) would have no way
    to actually stop it, leaving it stuck in FAMILY_APPROVED forever.
    """
    if campaign.family_id is None:
        raise ValidationError("Only a family-initiated campaign goes through this approval step.")
    if campaign.status != ContributionCampaign.Status.FAMILY_APPROVED:
        raise ValidationError(f"This campaign is '{campaign.status}' — it must be approved by the family's own executives first.")
    if not (actor.is_superuser or (actor.role == "community_admin" and actor.community_id == campaign.community_id)):
        raise ValidationError("Only this community's own Community Administrator can give final approval.")

    from audit_log.services import record_event
    if not approve:
        campaign.status = ContributionCampaign.Status.REJECTED
        campaign.save(update_fields=["status"])
        record_event(
            category="community", action="welfare_campaign_rejected", actor=actor, community=campaign.community,
            target_type="ContributionCampaign", target_id=campaign.id, target_label=campaign.title,
            description=f"'{campaign.title}' rejected by the Community Administrator after the family's own executives had already approved it.",
        )
        return campaign

    campaign.status = ContributionCampaign.Status.ACTIVE
    campaign.save(update_fields=["status"])
    generate_welfare_obligations(campaign)

    from notifications.services import notify_eligible_members_of_campaign
    notify_eligible_members_of_campaign(members=_eligible_members_for(campaign), campaign_title=campaign.title, community=campaign.community)

    record_event(
        category="community", action="welfare_campaign_approved", actor=actor, community=campaign.community,
        target_type="ContributionCampaign", target_id=campaign.id, target_label=campaign.title,
        description=f"'{campaign.title}' given final approval by the Community Administrator — {campaign.family.name}'s members now billed.",
    )
    return campaign


def list_pending_community_admin_welfare_approvals(community):
    """The Community (or Temporary) Admin's own final-approval queue — every family campaign whose own executives have already signed off."""
    return ContributionCampaign.objects.filter(
        community=community, family__isnull=False, status=ContributionCampaign.Status.FAMILY_APPROVED,
    ).select_related("family", "category")


def campaign_approval_progress(campaign: ContributionCampaign) -> dict:
    approvals = list(campaign.approvals.select_related("approved_by").order_by("approved_at"))
    required = campaign.category.required_family_approvals
    return {
        "campaign_id": str(campaign.id),
        "status": campaign.status,
        "required_approvals": required,
        "approvals": [{"approved_by": a.approved_by.username, "approved_at": a.approved_at.isoformat()} for a in approvals],
        "still_needed": max(0, required - len(approvals)),
    }


# --- Payments -----------------------------------------------------------------

def _generate_voucher_number(community) -> str:
    import random
    return f"WLF-{community.slug[:6].upper()}-{random.randint(100000, 999999)}"


@transaction.atomic
def record_welfare_payment(*, obligation: WelfareObligation, amount: Decimal, method: str, collector=None, client_op_id=None) -> WelfarePayment:
    """
    Mirrors funerals.services.record_payment — with one real
    distinction this platform's own funeral ledger never needed:
    'campaigns should support Fixed contribution (every eligible
    contributor contributes the defined amount) OR Minimum
    contribution (the defined amount is the minimum)... member can
    contribute GHS 50, GHS 100, GHS 500.' A FIXED category genuinely
    caps at the exact amount; a FLEXIBLE category's amount is a
    minimum only — paying more must be allowed, exactly like every
    other minimum-not-cap ledger on this platform.
    """
    if client_op_id:
        existing = WelfarePayment.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    if obligation.balance <= 0 and obligation.campaign.category.amount_type == ContributionCategory.AmountType.FIXED:
        raise ValidationError("This obligation is already fully paid.")
    if amount > obligation.balance and obligation.campaign.category.amount_type == ContributionCategory.AmountType.FIXED:
        raise ValidationError(f"That's more than the {obligation.balance} still owed on this fixed-amount obligation.")

    payment = WelfarePayment.objects.create(
        obligation=obligation, amount=amount, method=method, collected_by=collector, client_op_id=client_op_id,
        receipt_number=_generate_voucher_number(obligation.community),
    )
    obligation.amount_paid = obligation.amount_paid + amount
    obligation.save(update_fields=["amount_paid", "updated_at"])
    return payment


def record_voluntary_contribution(
    *, campaign: ContributionCampaign, member, amount: Decimal, method: str, collector=None, client_op_id=None,
) -> WelfarePayment:
    """
    'A voluntary campaign must NOT create a debt-like outstanding
    balance.' No pre-existing obligation to pay against — one is
    created here, on demand, for exactly what this member actually
    gives, so expected_amount and amount_paid always land equal and
    balance is always zero: nothing ever shows as outstanding for a
    voluntary contributor, no matter how much or how little they give.
    """
    if campaign.category.is_mandatory:
        raise ValidationError(f"'{campaign.title}' is a mandatory campaign — use record_welfare_payment against its own generated obligation instead.")
    if amount <= 0:
        raise ValidationError("Contribution amount must be greater than zero.")
    if member.family_id and campaign.family_id and member.family_id != campaign.family_id:
        raise ValidationError(f"{member.full_name} isn't a member of {campaign.family.name} — this campaign is that family's own.")

    if client_op_id:
        existing = WelfarePayment.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing

    obligation, _ = WelfareObligation.objects.get_or_create(
        campaign=campaign, member=member, defaults={"community": campaign.community, "expected_amount": Decimal("0")},
    )
    payment = WelfarePayment.objects.create(
        obligation=obligation, amount=amount, method=method, collected_by=collector, client_op_id=client_op_id,
        receipt_number=_generate_voucher_number(campaign.community),
    )
    # Expected always tracks paid exactly — never a balance owed.
    obligation.amount_paid = obligation.amount_paid + amount
    obligation.expected_amount = obligation.amount_paid
    obligation.save(update_fields=["amount_paid", "expected_amount", "updated_at"])
    return payment


# ============================================================
# WELFARE REQUESTS — money going OUT of a fund. See
# welfare.models.WelfareRequest for why this links to a
# ContributionCampaign rather than a second fund concept.
# ============================================================

def _is_authorized_for_campaign_administration(user, campaign: ContributionCampaign) -> bool:
    """Same authority already governing CampaignObligationsView/RecordWelfarePaymentView — community-wide leadership, or the owning family's own executives for a family-scoped campaign."""
    if user.is_superuser or user.role in {"community_admin", "chairman", "secretary", "treasurer", "financial_secretary"}:
        return True
    if campaign.family_id:
        own_member = getattr(user, "member_profile", None)
        if own_member and own_member.family_id == campaign.family_id and user.role in {"family_head", "family_secretary", "family_treasurer"}:
            return True
    return False


def submit_welfare_request(
    *, campaign: ContributionCampaign, requester, amount_requested: Decimal, reason: str, supporting_info: str = "", actor=None,
) -> WelfareRequest:
    """
    'A family member may request support from their family fund' /
    'a community member may request support from a community fund.'
    The requester must actually be eligible under this campaign's own
    scope — a Family A member can't request against Family B's fund
    just because they know its ID.
    """
    if campaign.family_id and requester.family_id != campaign.family_id:
        raise ValidationError(f"{requester.full_name} isn't a member of {campaign.family.name} — this fund is that family's own.")
    if requester.community_id != campaign.community_id:
        raise ValidationError(f"{requester.full_name} isn't a member of this community.")
    if amount_requested <= 0:
        raise ValidationError("The requested amount must be greater than zero.")
    if not reason.strip():
        raise ValidationError("A reason must be given for this request.")

    request = WelfareRequest.objects.create(
        community=campaign.community, campaign=campaign, requester=requester,
        amount_requested=amount_requested, reason=reason.strip(), supporting_info=supporting_info.strip(),
    )
    from audit_log.services import record_event
    record_event(
        category="community", action="welfare_request_submitted", actor=actor, community=campaign.community,
        target_type="Member", target_id=requester.id, target_label=requester.full_name,
        description=f"{requester.full_name} requested {amount_requested} from '{campaign.title}' ({reason.strip()[:100]}).",
    )
    return request


@transaction.atomic
def decide_welfare_request(*, request: WelfareRequest, actor, approve: bool, amount_approved: Decimal = None, rejection_reason: str = "") -> WelfareRequest:
    """'The existence of the request does not automatically mean money has been disbursed' — approval alone, never disbursement."""
    from django.utils import timezone

    if request.status != WelfareRequest.Status.PENDING:
        raise ValidationError(f"This request is already {request.status} — there's nothing left to decide.")
    if not _is_authorized_for_campaign_administration(actor, request.campaign):
        raise ValidationError(f"'{actor.username}' isn't authorized to decide this fund's welfare requests.")

    if approve:
        real_amount = amount_approved if amount_approved is not None else request.amount_requested
        if real_amount <= 0 or real_amount > request.amount_requested:
            raise ValidationError(f"The approved amount must be greater than zero and no more than the {request.amount_requested} requested.")
        request.status = WelfareRequest.Status.APPROVED
        request.amount_approved = real_amount
    else:
        if not rejection_reason.strip():
            raise ValidationError("A reason must be given when rejecting a welfare request.")
        request.status = WelfareRequest.Status.REJECTED
        request.rejection_reason = rejection_reason.strip()

    request.approved_by = actor
    request.decided_at = timezone.now()
    request.save(update_fields=["status", "amount_approved", "approved_by", "decided_at", "rejection_reason"])

    from audit_log.services import record_event
    record_event(
        category="community", action=f"welfare_request_{request.status}", actor=actor, community=request.community,
        target_type="Member", target_id=request.requester.id, target_label=request.requester.full_name,
        description=f"{request.requester.full_name}'s welfare request " + (f"approved for {request.amount_approved}." if approve else f"rejected ({request.rejection_reason})."),
    )
    return request


@transaction.atomic
def disburse_welfare_request(*, request: WelfareRequest, actor, amount: Decimal = None) -> WelfareRequest:
    """
    'Collection -> Verification -> Approval -> Disbursement ->
    Recipient acknowledgement -> Audit.' A controlled, explicit step —
    never inferred from approval alone.
    """
    from django.utils import timezone

    if request.status != WelfareRequest.Status.APPROVED:
        raise ValidationError(f"Only an approved request can be disbursed — this one is {request.status}.")
    if not _is_authorized_for_campaign_administration(actor, request.campaign):
        raise ValidationError(f"'{actor.username}' isn't authorized to disburse this fund's welfare requests.")

    real_amount = amount if amount is not None else request.amount_approved
    if real_amount <= 0 or real_amount > request.amount_approved:
        raise ValidationError(f"The disbursed amount must be greater than zero and no more than the {request.amount_approved} approved.")

    request.status = WelfareRequest.Status.DISBURSED
    request.amount_disbursed = real_amount
    request.disbursed_by = actor
    request.disbursed_at = timezone.now()
    request.save(update_fields=["status", "amount_disbursed", "disbursed_by", "disbursed_at"])

    from audit_log.services import record_event
    record_event(
        category="finance", action="welfare_request_disbursed", actor=actor, community=request.community,
        target_type="Member", target_id=request.requester.id, target_label=request.requester.full_name,
        description=f"{real_amount} disbursed to {request.requester.full_name} for their welfare request.",
    )
    return request


def acknowledge_welfare_disbursement(*, request: WelfareRequest, actor) -> WelfareRequest:
    """The requester themselves confirming they actually received the money — never assumed just because a disbursement was recorded."""
    from django.utils import timezone

    if request.status != WelfareRequest.Status.DISBURSED:
        raise ValidationError("Only a disbursed request can be acknowledged.")
    own_member = getattr(actor, "member_profile", None)
    if not (actor.is_superuser or (own_member and own_member.id == request.requester_id)):
        raise ValidationError("Only the requester themselves can acknowledge receiving this disbursement.")
    if request.acknowledged_at is not None:
        raise ValidationError("This disbursement has already been acknowledged.")

    request.acknowledged_at = timezone.now()
    request.save(update_fields=["acknowledged_at"])
    return request


def list_welfare_requests_for(*, campaign: ContributionCampaign, actor):
    """Same visibility rule as CampaignObligationsView — community-wide leadership or the owning family's own executives see every request; anyone else sees only their own."""
    qs = WelfareRequest.objects.filter(campaign=campaign).select_related("requester")
    if _is_authorized_for_campaign_administration(actor, campaign):
        return qs
    own_member = getattr(actor, "member_profile", None)
    return qs.filter(requester=own_member) if own_member else qs.none()

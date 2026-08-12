from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    CampaignApproval,
    ContributionCampaign,
    ContributionCategory,
    WelfareObligation,
    WelfarePayment,
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
    from contribution_rules.services import eligible_members_queryset

    members = eligible_members_queryset(campaign.community)
    if campaign.family_id:
        # "When one family initiates it, it should only be within his
        # jurisdiction" — never any other family's members, no matter
        # how the campaign was created.
        members = members.filter(family_id=campaign.family_id)
    return members


@transaction.atomic
def generate_welfare_obligations(campaign: ContributionCampaign):
    """Fan-out: one WelfareObligation per eligible member, mirroring funerals.services.generate_obligations exactly."""
    members = _eligible_members_for(campaign)
    obligations = [
        WelfareObligation(community=campaign.community, campaign=campaign, member=member, expected_amount=campaign.amount)
        for member in members
    ]
    WelfareObligation.objects.bulk_create(obligations, ignore_conflicts=True)
    return len(obligations)


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
    """Mirrors funerals.services.record_payment exactly."""
    if client_op_id:
        existing = WelfarePayment.objects.filter(client_op_id=client_op_id).first()
        if existing:
            return existing
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    if obligation.balance <= 0:
        raise ValidationError("This obligation is already fully paid.")
    if amount > obligation.balance:
        raise ValidationError(f"That's more than the {obligation.balance} still owed on this obligation.")

    payment = WelfarePayment.objects.create(
        obligation=obligation, amount=amount, method=method, collected_by=collector, client_op_id=client_op_id,
        receipt_number=_generate_voucher_number(obligation.community),
    )
    obligation.amount_paid = obligation.amount_paid + amount
    obligation.save(update_fields=["amount_paid", "updated_at"])
    return payment

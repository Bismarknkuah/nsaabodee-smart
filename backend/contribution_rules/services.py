"""
Community-wide contribution rule governance: the general (non-own-family)
rates, which member statuses are exempt entirely, and the defaulter
escalation thresholds. Own-family rates themselves are still owned by
families.services (recommend/approve/reject) — this module is what ties
everything into ONE place an administrator can see and edit, and is what
funerals.services consults when deciding who owes what.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from families.models import Family
from tenants.models import Community
from .models import DefaulterPolicy, GeneralRateChangeLog, MemberStatusRule


def get_defaulter_policy(community: Community) -> DefaulterPolicy:
    policy, _ = DefaulterPolicy.objects.get_or_create(community=community)
    return policy


@transaction.atomic
def update_defaulter_thresholds(*, community, warning, high_warning, flag, actor=None):
    if not (0 < warning < high_warning < flag):
        raise ValidationError(
            "Thresholds must strictly increase: warning < high warning < flag, and warning must be at least 1."
        )
    policy = get_defaulter_policy(community)
    policy.warning_threshold = warning
    policy.high_warning_threshold = high_warning
    policy.flag_threshold = flag
    policy.save()
    return policy


def is_status_exempt(community: Community, status: str) -> bool:
    override = MemberStatusRule.objects.filter(community=community, status=status).first()
    if override is not None:
        return override.is_exempt
    return status in MemberStatusRule.DEFAULT_EXEMPT_STATUSES


@transaction.atomic
def set_status_exemption(*, community, status, is_exempt, actor=None):
    rule, _ = MemberStatusRule.objects.update_or_create(
        community=community, status=status, defaults={"is_exempt": is_exempt, "updated_by": actor},
    )
    return rule


def eligible_members_queryset(community: Community):
    """
    Every member NOT in a status the community has exempted from mandatory
    contributions entirely. By default that's inactive and deceased
    members — only active members are obligated — but this is exactly the
    "Member Status" factor the master brief calls out, so a community can
    reconfigure it (e.g. to also collect from inactive members) without
    any code change.
    """
    from members.models import Member

    exempt_statuses = {s for s in ["active", "inactive", "deceased"] if is_status_exempt(community, s)}
    return Member.objects.filter(community=community).exclude(status__in=exempt_statuses)


@transaction.atomic
def update_general_rates(*, community: Community, male_amount: Decimal, female_amount: Decimal, actor=None, reason=""):
    if male_amount <= 0 or female_amount <= 0:
        raise ValidationError("General contribution amounts must be greater than zero.")

    GeneralRateChangeLog.objects.create(
        community=community,
        old_male_amount=community.default_general_male_amount,
        old_female_amount=community.default_general_female_amount,
        new_male_amount=male_amount,
        new_female_amount=female_amount,
        reason=reason,
        changed_by=actor,
    )
    community.default_general_male_amount = male_amount
    community.default_general_female_amount = female_amount
    community.save(update_fields=["default_general_male_amount", "default_general_female_amount"])
    return community


def update_family_tier_rates(
    *, community: Community, head_amount: Decimal, senior_amount: Decimal,
    junior_amount: Decimal, woman_amount: Decimal, town_leader_amount: Decimal,
):
    """
    'Adjust or increase the minimum amount paid' — the same secretary
    permission that already covers the general rates now covers these
    five tiered ones too (see contribution_rules/permissions.py). Every
    NEW funeral opened after this call uses the new numbers; every
    already-open or already-closed funeral keeps exactly what was
    snapshotted onto it when it was created (see FuneralEvent's own
    docstring on why rates are never retroactively rewritten).
    """
    for label, amount in [
        ("family head", head_amount), ("family senior (uncle)", senior_amount),
        ("family junior (nephew)", junior_amount), ("family woman", woman_amount),
        ("town leader", town_leader_amount),
    ]:
        if amount <= 0:
            raise ValidationError(f"The {label} contribution amount must be greater than zero.")

    community.default_family_head_amount = head_amount
    community.default_family_senior_amount = senior_amount
    community.default_family_junior_amount = junior_amount
    community.default_family_woman_amount = woman_amount
    community.default_town_leader_amount = town_leader_amount
    community.save(update_fields=[
        "default_family_head_amount", "default_family_senior_amount",
        "default_family_junior_amount", "default_family_woman_amount", "default_town_leader_amount",
    ])
    return community


def list_rules(community: Community) -> dict:
    """
    The single-view read model for the Contribution Rules dashboard: every
    family's own rate (approved + pending), the community's general rates
    and their history, exemption rules, and defaulter thresholds — all in
    one response so an administrator never has to hunt across screens to
    understand how a contribution amount gets decided.
    """
    families = Family.objects.filter(community=community, status="active").order_by("name")
    policy = get_defaulter_policy(community)
    overrides = {r.status: r.is_exempt for r in MemberStatusRule.objects.filter(community=community)}

    all_statuses = ["active", "inactive", "deceased"]
    exemptions = [
        {"status": s, "is_exempt": overrides.get(s, s in MemberStatusRule.DEFAULT_EXEMPT_STATUSES),
         "is_default": s not in overrides}
        for s in all_statuses
    ]

    return {
        "general_rates": {
            "male_amount": str(community.default_general_male_amount),
            "female_amount": str(community.default_general_female_amount),
        },
        "family_tier_rates": {
            "head_amount": str(community.default_family_head_amount),
            "senior_amount": str(community.default_family_senior_amount),
            "junior_amount": str(community.default_family_junior_amount),
            "woman_amount": str(community.default_family_woman_amount),
            "town_leader_amount": str(community.default_town_leader_amount),
        },
        "family_rates": [
            {
                "family_id": str(f.id),
                "family_name": f.name,
                "standing_rate": str(f.standing_family_rate) if f.standing_family_rate is not None else None,
                "recommended_rate": str(f.recommended_family_rate) if f.recommended_family_rate is not None else None,
            }
            for f in families
        ],
        "member_status_exemptions": exemptions,
        "defaulter_thresholds": {
            "warning": policy.warning_threshold,
            "high_warning": policy.high_warning_threshold,
            "flag": policy.flag_threshold,
        },
    }


def preview_obligations(*, community: Community, deceased_family: Family) -> dict:
    """
    Dry-run: shows exactly what every active, non-exempt member would owe
    if a funeral were created right now for this family, WITHOUT creating
    anything. Lets an administrator sanity-check the rules before
    committing to a real funeral and its ledger.
    """
    if deceased_family.standing_family_rate is None:
        own_family_amount = None
    else:
        own_family_amount = deceased_family.standing_family_rate

    members = eligible_members_queryset(community)

    own_family_count = 0
    general_male_count = 0
    general_female_count = 0
    for m in members:
        if m.family_id == deceased_family.id:
            own_family_count += 1
        elif m.gender == "male":
            general_male_count += 1
        else:
            general_female_count += 1

    return {
        "own_family_amount": str(own_family_amount) if own_family_amount is not None else None,
        "own_family_member_count": own_family_count,
        "general_male_amount": str(community.default_general_male_amount),
        "general_male_member_count": general_male_count,
        "general_female_amount": str(community.default_general_female_amount),
        "general_female_member_count": general_female_count,
        "requires_one_off_amount": own_family_amount is None,
    }

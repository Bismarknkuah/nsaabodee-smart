"""
Community-wide contribution rule governance: the general (non-own-family)
rates, which member statuses are exempt entirely, and the defaulter
escalation thresholds. Own-family rates themselves are still owned by
families.services (recommend/approve/reject) — this module is what ties
everything into ONE place an administrator can see and edit, and is what
funerals.services consults when deciding who owes what.
"""

from datetime import date, timedelta
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


def _years_ago(from_date: date, years: int) -> date:
    """
    Safe date.replace(year=...) — a plain replace() crashes on Feb 29
    when the target year isn't a leap year ('day is out of range for
    month'). Falls back to Feb 28 in that one rare case rather than
    leaving a latent crash risk in the age-eligibility math below,
    which runs this every single day this platform is in use.
    """
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        return from_date.replace(year=from_date.year - years, day=28)


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


def family_position_rate_for(community: Community, position: str):
    """
    Returns the configured Decimal amount for this FamilyPosition, or
    None if the community has never configured one for it — the
    caller (FuneralEvent.rate_for) falls back to the coarser
    gender/family_seniority tiers in that case, exactly matching
    family_position itself being optional and additive.
    """
    from .models import FamilyPositionRate

    rate = FamilyPositionRate.objects.filter(community=community, position=position).first()
    return rate.amount if rate is not None else None


@transaction.atomic
def set_family_position_rate(*, community, position: str, amount, actor=None):
    from .models import FamilyPositionRate

    if amount <= 0:
        raise ValidationError(f"The rate for '{position}' must be greater than zero.")
    rate, _ = FamilyPositionRate.objects.update_or_create(
        community=community, position=position, defaults={"amount": amount, "updated_by": actor},
    )
    return rate


def eligible_members_queryset(community: Community):
    """
    Every member NOT in a status the community has exempted from mandatory
    contributions entirely. By default that's inactive and deceased
    members — only active members are obligated — but this is exactly the
    "Member Status" factor the master brief calls out, so a community can
    reconfigure it (e.g. to also collect from inactive members) without
    any code change.

    'Once a community member gets to 20 years and he's not schooling
    or an apprentice he has to mandatory pay for contribution... even
    if the person is a student or an apprentice and more than 25
    years should still have to pay.' Combined here as a second,
    independent exclusion — expressed as pure date arithmetic (two
    fixed cutoff dates: today minus 20 years, today minus 25 years)
    rather than a Python-side loop over every member's age, so this
    stays a single, efficient query regardless of community size.

    A member with NO recorded date_of_birth is never excluded by age —
    'the software must not hardcode a universal rule' cuts the other
    way here too: silently exempting every member who simply hasn't
    had their birth date entered yet would be its own dangerous
    assumption, and would quietly shrink an existing community's
    obligated membership the moment this feature shipped. Missing
    birth-date data is exactly the kind of gap this platform's own
    principle ('provide an authorized classification/verification
    mechanism rather than silently guessing') means addressing through
    members_needing_age_review below, not through a silent exemption.
    """
    from django.db.models import Q

    from members.models import Member

    exempt_statuses = {s for s in ["active", "inactive", "deceased"] if is_status_exempt(community, s)}
    today = date.today()
    cutoff_20 = _years_ago(today, 20)
    cutoff_25 = _years_ago(today, 25)

    return (
        Member.objects.filter(community=community)
        .exclude(status__in=exempt_statuses)
        .exclude(date_of_birth__gt=cutoff_20)  # genuinely under 20
        .exclude(Q(date_of_birth__gt=cutoff_25) & Q(occupation_status__in=["student", "apprentice"]))  # 20-24 AND still student/apprentice
    )


def is_contribution_eligible_by_age(member, as_of_date=None) -> bool:
    """
    The same rule as eligible_members_queryset's age exclusions above,
    expressed for a single, already-loaded member — used by
    members_needing_age_review and anywhere else that already has a
    Member instance in hand rather than needing a fresh query.
    """
    as_of_date = as_of_date or date.today()
    if member.date_of_birth is None:
        return True  # never silently exempt for missing data — see the docstring above
    age = as_of_date.year - member.date_of_birth.year - (
        (as_of_date.month, as_of_date.day) < (member.date_of_birth.month, member.date_of_birth.day)
    )
    if age < 20:
        return False
    if age < 25 and member.occupation_status in ("student", "apprentice"):
        return False
    return True


def members_needing_age_review(community: Community):
    """
    'Once the community member gets to 20 years the system should
    fetch them out for each family executive to update their data.'
    Members whose occupation_status genuinely needs a fresh look from
    their Family Head/Secretary — not a one-time notification, since
    both facts this depends on (age crossing 20, and whether someone
    is still a student/apprentice) change on their own over time:

      - Turning 20 this year: this is the first year their age alone
        could make them obligated — whoever registered them as a
        minor may never have set occupation_status at all.
      - Currently 20-24 AND recorded as student/apprentice: their
        exemption is time-limited by definition (it disappears at 25
        regardless) and status-dependent (it disappears the moment
        they finish school/training) — worth a periodic check, not a
        one-off.
      - Turning 25 this year while still recorded as student/apprentice:
        about to become obligated regardless of occupation_status —
        'even if the person is a student or an apprentice and more
        than 25 years should still have to pay.'

    Members with no recorded date_of_birth are deliberately excluded
    from this list — they need their birth date entered first, which
    is a data-completeness gap, not an age-review one; see
    members_missing_birth_date for that, separate concern.
    """
    from members.models import Member

    today = date.today()
    turning_20_cutoff_start = _years_ago(today, 21) + timedelta(days=1)
    turning_20_cutoff_end = _years_ago(today, 20)
    turning_25_cutoff_start = _years_ago(today, 26) + timedelta(days=1)
    turning_25_cutoff_end = _years_ago(today, 25)

    from django.db.models import Q

    return (
        Member.objects.filter(community=community, date_of_birth__isnull=False)
        .filter(
            Q(date_of_birth__gte=turning_20_cutoff_start, date_of_birth__lte=turning_20_cutoff_end)
            | Q(date_of_birth__gt=turning_25_cutoff_end, date_of_birth__lte=_years_ago(today, 20), occupation_status__in=["student", "apprentice"])
            | Q(date_of_birth__gte=turning_25_cutoff_start, date_of_birth__lte=turning_25_cutoff_end, occupation_status__in=["student", "apprentice"])
        )
        .distinct()
        .order_by("date_of_birth")
    )


def members_missing_birth_date(community: Community):
    """
    'Registration requires a lot of information' — every member the
    age-eligibility rule above can't evaluate at all yet, because
    nobody ever recorded when they were born. Surfaced separately from
    members_needing_age_review since this is a data-completeness gap
    (go get the actual date), not an age-crossing-a-threshold event.
    """
    from members.models import Member

    return Member.objects.filter(community=community, date_of_birth__isnull=True, status="active")


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


def set_town_elder_rate(*, community: Community, amount: Decimal, actor) -> Community:
    """
    'It is being managed by the king and he set price for each for
    them, so the town leader/king is the head of the community's
    elders' ledger.' Deliberately its own function, not folded into
    update_family_tier_rates below — that one is Community Admin/
    Chairman/Secretary's shared authority over the family-tier rates;
    the Town Elders' own rate is specifically the Traditional Leader's
    (the chief's) call, a genuinely different authority than the one
    over ordinary family contributions. Every NEW funeral opened after
    this call uses the new rate; already-open or closed funerals keep
    exactly what was snapshotted onto them when they were created —
    the same "never retroactive" rule every rate change on this
    platform already follows.
    """
    from accounts.models import Role

    if actor is not None and not actor.is_superuser and actor.role != Role.TRADITIONAL_LEADER:
        raise ValidationError("Only the Traditional Leader (chief) can set the Town Elders' contribution rate.")
    if amount <= 0:
        raise ValidationError("The Town Elders' contribution amount must be greater than zero.")

    community.default_town_leader_amount = amount
    community.save(update_fields=["default_town_leader_amount"])
    return community


def set_town_elder_per_title_rates(
    *, community: Community, chief_amount=None, queen_mother_amount=None,
    linguist_amount=None, other_amount=None, actor,
) -> Community:
    """
    The same Traditional-Leader-only authority as set_town_elder_rate
    above, extended to 'the expected contribution may differ according
    to the elder's official position.' Every argument is optional and
    independent — a chief can configure just one title at a time, or
    all four together; passing None (the default) for a title leaves
    whatever is already configured for it completely untouched, never
    silently reset. See FuneralEvent.town_elder_amount_for for the
    exact resolution order this feeds into.
    """
    from accounts.models import Role

    if actor is not None and not actor.is_superuser and actor.role != Role.TRADITIONAL_LEADER:
        raise ValidationError("Only the Traditional Leader (chief) can set the Town Elders' per-title contribution rates.")

    updates = {
        "default_town_elder_chief_amount": chief_amount,
        "default_town_elder_queen_mother_amount": queen_mother_amount,
        "default_town_elder_linguist_amount": linguist_amount,
        "default_town_elder_other_amount": other_amount,
    }
    fields_to_update = []
    for field_name, value in updates.items():
        if value is not None:
            if value <= 0:
                raise ValidationError(f"'{field_name}' must be greater than zero.")
            setattr(community, field_name, value)
            fields_to_update.append(field_name)
    if fields_to_update:
        community.save(update_fields=fields_to_update)
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

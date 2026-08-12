"""
Member registration, search, digital membership card / QR generation, and
the automatic defaulter escalation described in the master brief:

    miss 1 contribution  -> Warning
    miss 2 contributions -> High Warning
    miss 3 contributions -> Flagged: highlighted, Family Head + Treasurer
                             notified, added to the Defaulters Dashboard

Thresholds are configurable per community (contribution_rules.services).
"A missed contribution" means: an obligation on a funeral whose collection
has CLOSED, that the member never paid anything toward at all. A partial
payment is not treated as a miss — only a fully unpaid obligation on a
now-closed funeral counts.
"""

import base64
import io

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from contribution_rules.services import get_defaulter_policy
from .models import Member


def find_possible_duplicates(*, community, full_name, phone=""):
    """
    Simple, transparent duplicate check (name + phone) rather than a black
    -box ML matcher — a collector can see exactly why two records were
    flagged as possibly the same person and decide for themselves. This
    NEVER blocks registration; it's advisory, returned alongside the new
    member so a collector or admin can merge/investigate afterwards.
    """
    candidates = Member.objects.filter(community=community, full_name__iexact=full_name.strip())
    if phone:
        candidates = candidates | Member.objects.filter(community=community, phone=phone)
    return list(candidates.distinct())


@transaction.atomic
def register_member(
    *, community, full_name, gender, family=None, date_of_birth=None, occupation="",
    phone="", email="", address="", ghana_card_number=None, photo=None,
    emergency_contact_name="", emergency_contact_phone="", registered_by=None,
    force_despite_duplicate=False, family_seniority=None, is_town_leader=False,
):
    if family is not None and family.community_id != community.id:
        raise ValidationError("The chosen family must belong to this community.")
    # "Family head should only [be] allowed to register his family
    # members, not new families." Same jurisdiction boundary as task
    # assignment — a Family Head's authority stops at their own
    # family; Community Admin, Chairman, Secretary, and Collector
    # register community-wide with no such restriction. Family
    # Secretary also has registration authority (MEMBER_REGISTRATION_ROLES)
    # and is equally family-scoped, not community-wide — the same
    # restriction applies to both, not just the Head.
    if registered_by is not None and registered_by.role in ("family_head", "family_secretary"):
        own_family_id = getattr(getattr(registered_by, "member_profile", None), "family_id", None)
        if own_family_id is None or family is None or family.id != own_family_id:
            raise ValidationError("A Family Head or Family Secretary can only register members into their own family.")
    if ghana_card_number:
        if Member.objects.filter(community=community, ghana_card_number=ghana_card_number).exists():
            raise ValidationError("A member with this Ghana Card number is already registered in this community.")

    # "One person should not be added twice" — an EXACT match on name AND
    # phone (not just a fuzzy/advisory hint) is blocked outright rather
    # than just flagged, since a matching name plus a matching phone
    # number together is about as strong a signal of "this is the same
    # person" as this platform can get without a national ID on every
    # record. `force_despite_duplicate` exists for the genuine edge case
    # of two real people who happen to share both — a deliberate,
    # explicit override, not a default anyone stumbles into by accident.
    if phone and not force_despite_duplicate:
        exact_match = Member.objects.filter(
            community=community, full_name__iexact=full_name.strip(), phone=phone,
        ).first()
        if exact_match:
            raise ValidationError(
                f"{exact_match.full_name} is already registered with this phone number "
                f"(membership number {exact_match.membership_number}). If this is genuinely "
                f"a different person, resubmit with force_despite_duplicate=true."
            )

    try:
        member = Member.objects.create(
            community=community,
            family=family,
            full_name=full_name.strip(),
            gender=gender,
            date_of_birth=date_of_birth,
            occupation=occupation,
            phone=phone,
            email=email,
            address=address,
            ghana_card_number=ghana_card_number,
            photo=photo,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            registered_by=registered_by,
            family_seniority=family_seniority or Member.FamilySeniority.JUNIOR,
            is_town_leader=is_town_leader,
        )
    except IntegrityError as exc:
        raise ValidationError("Could not register this member — please check the Ghana Card number and try again.") from exc

    # The post_save signal (members/signals.py) handles auto-enrollment
    # into any currently-open funerals; nothing further needed here.
    return member


@transaction.atomic
def update_member(*, member: Member, actor=None, **fields):
    allowed = {
        "full_name", "gender", "date_of_birth", "occupation", "phone", "email", "address",
        "ghana_card_number", "photo", "emergency_contact_name", "emergency_contact_phone", "status",
        "family_seniority", "is_town_leader",
    }
    for key, value in fields.items():
        if key not in allowed:
            raise ValidationError(f"'{key}' cannot be updated through this action.")
        setattr(member, key, value)
    try:
        member.full_clean(exclude=["membership_number"])
        member.save()
    except IntegrityError as exc:
        raise ValidationError("This Ghana Card number is already registered to another member.") from exc
    return member


FAMILY_SCOPED_MEMBER_ROLES = {"family_head", "family_secretary", "family_treasurer"}


def search_members(*, community, query="", family_id=None, status=None, defaulter_tier=None, actor=None):
    """
    'Family head or executive shouldn't have access to other families'
    information or members' information. When a family head or
    executive search for a member, they should only see their members
    not other members from a different family.' Community-wide roles
    (Community Admin, Chairman, Secretary, Treasurer, Financial
    Secretary, Auditor, Collector, Traditional Leader, etc.) keep
    their existing, legitimate community-wide visibility unchanged —
    this narrowing is specifically for FAMILY-level executives (Family
    Head, Family Secretary, Family Treasurer), whose own authority is
    already scoped to their own family everywhere else in this
    platform. Their own family is enforced here regardless of any
    `family_id` filter they might otherwise try to pass — they can
    never widen their own view by asking for a different family's id.
    """
    qs = Member.objects.filter(community=community).select_related("family")

    if actor is not None and not actor.is_superuser and actor.role in FAMILY_SCOPED_MEMBER_ROLES:
        own_member = getattr(actor, "member_profile", None)
        if own_member is None or own_member.family_id is None:
            return qs.none()
        family_id = own_member.family_id

    if query:
        qs = qs.filter(
            models_q_full_name_or_phone_or_card(query)
        )
    if family_id:
        qs = qs.filter(family_id=family_id)
    if status:
        qs = qs.filter(status=status)
    if defaulter_tier:
        qs = qs.filter(defaulter_tier=defaulter_tier)
    return qs


def models_q_full_name_or_phone_or_card(query):
    from django.db.models import Q
    return Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(ghana_card_number__icontains=query)


def generate_qr_code_base64(member: Member) -> str:
    import qrcode

    img = qrcode.make(member.qr_payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@transaction.atomic
def link_member_to_user(*, member: Member, user, actor=None):
    """
    Ties a Member profile to a User login so that member can see their
    own "My Receipts" dashboard. Deliberately an administrator action
    (not member self-service) since verifying "this login really is this
    resident" needs a real identity check this platform doesn't have a
    mechanism for yet (see the Communication Module notes for the same
    underlying gap).
    """
    if user.community_id != member.community_id:
        raise ValidationError("The user account must belong to the same community as the member.")
    existing = Member.objects.filter(linked_user=user).exclude(id=member.id).first()
    if existing:
        raise ValidationError(f"This user account is already linked to '{existing.full_name}'.")

    member.linked_user = user
    member.save(update_fields=["linked_user", "updated_at"])
    return member


# Every community-level role a Community Admin can grant — deliberately
# excludes Role.PLATFORM_ADMIN, which is platform-level and must never
# be something a Community Admin can hand to anyone (that would be a
# genuine privilege-escalation path into the platform tier).
ASSIGNABLE_COMMUNITY_ROLES = [
    "community_admin", "traditional_leader", "chairman", "secretary",
    "treasurer", "financial_secretary", "auditor", "collector",
    "family_head", "family_secretary", "family_treasurer",
    "community_member", "guest", "bereaved_rep", "notification_officer",
]


def revoke_role_from_member(*, member: Member, actor) -> "User":
    """
    'Assign and revoke roles and permissions.' Mechanically the same
    path as assign_role_to_member(role="community_member") — Community
    Member is already the genuine baseline, no-special-powers role —
    but given its own clear name, its own audit wording, and its own
    obvious place in the UI, rather than requiring an admin to already
    know that picking "Community Member" from a role dropdown IS how
    you revoke something.
    """
    if not member.linked_user_id:
        raise ValidationError(f"{member.full_name} doesn't have a login to revoke a role from.")
    old_role = member.linked_user.role
    if old_role == "community_member":
        raise ValidationError(f"{member.full_name} is already a plain Community Member — there's no elevated role to revoke.")

    user = assign_role_to_member(member=member, role="community_member", actor=actor)

    from audit_log.services import record_event
    record_event(
        category="role", action="role_revoked", actor=actor, community=actor.community,
        target_type="User", target_id=user.id, target_label=user.username,
        description=f"{member.full_name}'s '{old_role}' role was revoked by {actor.username}, returning them to Community Member.",
        metadata={"revoked_role": old_role, "member_id": str(member.id)},
    )
    return user


@transaction.atomic
def assign_role_to_member(*, member: Member, role: str, actor, username: str = None, password: str = None):
    """
    'There should be specific roles to select when the community admin
    wants to assign a role or task to someone — [they] should have more
    options as he supervises and manages the community system.' The
    genuinely missing piece: until now, a role was only ever set once,
    at account-creation time (onboarding a Family Head, adding a
    Community Admin) — there was no way to promote an EXISTING member
    to a new role afterward. Community Admin only, and community-wide
    (unlike task assignment, which a Family Head can also do, but only
    within their own family) — granting a platform role is squarely
    "supervising and managing the community system," not something a
    narrower role should hold.

    If the member already has a login, this changes that login's role.
    If they don't yet, a username/password creates one on the spot and
    links it — the same "member or not yet, doesn't matter" flexibility
    already used for desk assignments.
    """
    from accounts.models import Role, User

    if actor.role != "community_admin":
        raise ValidationError("Only the Community Admin can assign roles.")
    if member.community_id != actor.community_id:
        raise ValidationError("You can only assign roles to members of your own community.")
    if role not in ASSIGNABLE_COMMUNITY_ROLES:
        raise ValidationError(f"'{role}' isn't a role the Community Admin can assign.")

    if member.linked_user_id:
        user = member.linked_user
        old_role = user.role
        user.role = role
        user.save(update_fields=["role"])
        from audit_log.services import record_event
        record_event(
            category="role", action="role_changed", actor=actor, community=actor.community,
            target_type="User", target_id=user.id, target_label=user.username,
            description=f"{member.full_name}'s role changed from '{old_role}' to '{role}' by {actor.username}.",
            metadata={"old_role": old_role, "new_role": role, "member_id": str(member.id)},
        )
        return user

    if not username or not password:
        raise ValidationError("This member doesn't have a login yet — a username and password are needed to create one.")
    if User.objects.filter(username=username).exists():
        raise ValidationError(f"The username '{username}' is already taken.")
    user = User.objects.create_user(username=username, password=password, community=actor.community, role=role)
    member.linked_user = user
    member.save(update_fields=["linked_user", "updated_at"])
    from audit_log.services import record_event
    record_event(
        category="role", action="role_assigned", actor=actor, community=actor.community,
        target_type="User", target_id=user.id, target_label=user.username,
        description=f"{member.full_name} granted the role '{role}' and a new login ('{username}') by {actor.username}.",
        metadata={"new_role": role, "member_id": str(member.id)},
    )
    return user


@transaction.atomic
def unlink_member_from_user(*, member: Member, actor=None):
    member.linked_user = None
    member.save(update_fields=["linked_user", "updated_at"])
    return member


def digital_membership_card(member: Member) -> dict:
    """Everything the frontend/mobile needs to render the printable digital membership card."""
    return {
        "member_id": str(member.id),
        "membership_number": member.membership_number,
        "full_name": member.full_name,
        "family_name": member.family.name if member.family else None,
        "status": member.status,
        "photo_url": member.photo.url if member.photo else None,
        "qr_code_base64": generate_qr_code_base64(member),
    }


# --- Defaulter escalation -------------------------------------------------

def _missed_contribution_count(member: Member) -> int:
    from funerals.models import ContributionObligation, FuneralEvent
    return ContributionObligation.objects.filter(
        member=member,
        funeral_event__status=FuneralEvent.Status.CLOSED,
        amount_paid=0,
    ).count()


@transaction.atomic
def evaluate_defaulter_status(member: Member):
    """
    Recompute one member's missed-contribution count and defaulter tier.
    Returns (member, tier_changed, previous_tier) so the caller can decide
    whether to fire notifications (only on an actual escalation, not every
    time this is recalculated).
    """
    policy = get_defaulter_policy(member.community)
    missed = _missed_contribution_count(member)
    new_tier = policy.tier_for(missed)
    previous_tier = member.defaulter_tier

    from django.utils import timezone
    member.missed_contributions_count = missed
    member.defaulter_tier = new_tier
    member.defaulter_evaluated_at = timezone.now()
    member.save(update_fields=["missed_contributions_count", "defaulter_tier", "defaulter_evaluated_at", "updated_at"])

    tier_changed = new_tier != previous_tier
    return member, tier_changed, previous_tier


TIER_SEVERITY = {"none": 0, "warning": 1, "high_warning": 2, "flagged": 3}


def evaluate_defaulters_for_closed_funeral(funeral):
    """
    Called right after a funeral's collection closes. Every member with an
    obligation on it gets their defaulter status recalculated; anyone who
    just escalated to a worse tier (and especially anyone who just hit
    "flagged") gets Family Head + Treasurer notified and is added to the
    Defaulters Dashboard, per the master brief.
    """
    from notifications.services import notify_family_head, notify_treasurers

    newly_escalated = []
    for obligation in funeral.obligations.select_related("member", "member__family"):
        member, tier_changed, previous_tier = evaluate_defaulter_status(obligation.member)
        if tier_changed and TIER_SEVERITY[member.defaulter_tier] > TIER_SEVERITY[previous_tier]:
            newly_escalated.append(member)
            message = (
                f"{member.full_name} has missed {member.missed_contributions_count} "
                f"contribution(s) and is now marked '{member.get_defaulter_tier_display()}'."
            )
            if member.family:
                notify_family_head(family=member.family, member=member, message=message)
            if member.defaulter_tier == Member.DefaulterTier.FLAGGED:
                notify_treasurers(community=member.community, member=member, message=message)
    return newly_escalated

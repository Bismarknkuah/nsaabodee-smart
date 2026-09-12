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
from django.utils import timezone

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
    mother_name="", father_name="", hometown="", marital_status="", spouse_name="",
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
    # restriction applies to both, not just the Head. Family
    # Registration Officer — 'each family will have their registration
    # officer, who will register for only his family members' — is a
    # dedicated role with the exact same family-scoped restriction.
    if registered_by is not None and registered_by.role in ("family_head", "family_secretary", "family_registration_officer"):
        own_family_id = getattr(getattr(registered_by, "member_profile", None), "family_id", None)
        if own_family_id is None or family is None or family.id != own_family_id:
            raise ValidationError("A Family Head, Family Secretary, or Family Registration Officer can only register members into their own family.")
    # 'Registration officer who will register the town elders' — this
    # role's jurisdiction is elders specifically, not the ordinary
    # community roster; registering anyone else is simply outside
    # what this desk is for.
    if registered_by is not None and registered_by.role == "town_registration_officer" and not is_town_leader:
        raise ValidationError("A Town Elders Registration Officer can only register town elders.")
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
            mother_name=mother_name,
            father_name=father_name,
            hometown=hometown,
            marital_status=marital_status,
            spouse_name=spouse_name,
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
        "family_seniority", "is_town_leader", "town_elder_title",
        "mother_name", "father_name", "hometown", "marital_status", "spouse_name",
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


FAMILY_SCOPED_MEMBER_ROLES = {"family_head", "family_secretary", "family_treasurer", "family_registration_officer"}


SORT_OPTIONS = {
    "name": "full_name",
    "family": "family__name",
    "age": "-date_of_birth",  # oldest first, matching how "sort by age" is normally read
    "age_youngest_first": "date_of_birth",
    "gender": "gender",
    "status": "status",
    "membership_number": "membership_number",
}


def search_members(*, community, query="", family_id=None, status=None, defaulter_tier=None, gender=None, sort_by=None, actor=None):
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

    'Executives should have different types to sort members either by
    family, male, female, surname, age and many more option.' gender
    is a genuine filter (show only one gender); sort_by governs
    ordering — there's no separate surname field in this platform, so
    "sort by surname" sorts by full_name alphabetically, the closest
    honest match to what's actually stored.
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
    if gender:
        qs = qs.filter(gender=gender)
    if sort_by and sort_by in SORT_OPTIONS:
        qs = qs.order_by(SORT_OPTIONS[sort_by])
    else:
        qs = qs.order_by("full_name")
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


def credit_wallet(*, member: Member, amount, note: str = "", actor=None) -> "MemberWallet":
    """
    'If he doesn't get change, money balance should be credited to the
    member's wallet.' Creates the wallet on first use rather than
    requiring every member to have one up front.
    """
    from decimal import Decimal

    from .models import MemberWallet, WalletTransaction

    if amount <= 0:
        raise ValidationError("Credit amount must be greater than zero.")
    wallet, _ = MemberWallet.objects.get_or_create(member=member)
    wallet.balance = wallet.balance + Decimal(amount)
    wallet.save(update_fields=["balance", "updated_at"])
    WalletTransaction.objects.create(wallet=wallet, kind=WalletTransaction.Kind.CREDIT, amount=amount, note=note, actor=actor)
    return wallet


def debit_wallet(*, member: Member, amount, note: str = "", actor=None) -> "MemberWallet":
    """Applying existing wallet credit toward a real obligation — never allowed to go negative."""
    from decimal import Decimal

    from .models import MemberWallet, WalletTransaction

    if amount <= 0:
        raise ValidationError("Debit amount must be greater than zero.")
    try:
        wallet = MemberWallet.objects.get(member=member)
    except MemberWallet.DoesNotExist:
        raise ValidationError(f"{member.full_name} has no wallet credit to use.")
    if wallet.balance < Decimal(amount):
        raise ValidationError(f"{member.full_name} only has {wallet.balance} in wallet credit, not {amount}.")
    wallet.balance = wallet.balance - Decimal(amount)
    wallet.save(update_fields=["balance", "updated_at"])
    WalletTransaction.objects.create(wallet=wallet, kind=WalletTransaction.Kind.DEBIT, amount=amount, note=note, actor=actor)
    return wallet


def get_wallet_balance(member: Member):
    from decimal import Decimal

    from .models import MemberWallet

    wallet = MemberWallet.objects.filter(member=member).first()
    return wallet.balance if wallet else Decimal("0")


def bulk_register_members(*, community, rows: list[dict], actor) -> dict:
    """
    'Executive should have access to upload data when necessary...
    each family should have access to their database and they can
    download it or upload to update it.' Two things a single upload
    can now do, decided per row: a row with a "membership_number"
    matching an existing member in this community UPDATES that
    member's own record — the genuine round trip a re-uploaded export
    file needs — while every other row still registers a brand new
    member exactly as before. Each row goes through the exact same
    register_member()/update_member() every other write on this
    platform already goes through — the same duplicate detection, the
    same Family Head/Secretary/Registration-Officer own-family-only
    restriction, the same everything. One bad row never aborts the
    whole batch; each row succeeds or fails on its own, and every
    failure is reported with its row number and reason so the person
    uploading can fix just that row and retry, rather than guessing
    which of 50 rows was the problem.

    Each dict in `rows` is expected to have (at minimum) "full_name"
    and "gender" for a new registration, or just "membership_number"
    plus whichever fields are actually changing for an update;
    "family_name" is resolved by exact, case-insensitive name lookup
    within this community — a Family Head or Family Secretary doesn't
    need to provide one at all, since register_member already locks
    them to their own family regardless of what's given.
    """
    from families.models import Family

    is_family_scoped = actor is not None and actor.role in ("family_head", "family_secretary", "family_registration_officer")
    own_family = None
    if is_family_scoped:
        own_family = getattr(getattr(actor, "member_profile", None), "family", None)

    # The exact set of fields update_member will actually accept —
    # matches members.services.update_member's own allowlist, since
    # this is the same write path, not a second one that could drift.
    updatable_string_fields = (
        "full_name", "gender", "occupation", "phone", "email", "address", "ghana_card_number",
        "mother_name", "father_name", "hometown", "marital_status", "spouse_name",
        "emergency_contact_name", "emergency_contact_phone",
    )

    created = []
    updated = []
    errors = []
    for i, row in enumerate(rows, start=1):
        membership_number = (row.get("membership_number") or "").strip()

        if membership_number:
            qs = Member.objects.filter(community=community, membership_number=membership_number)
            if is_family_scoped:
                qs = qs.filter(family_id=own_family.id if own_family else None)
            existing = qs.first()
            if existing is None:
                errors.append({
                    "row": i, "full_name": row.get("full_name", ""),
                    "error": f"No member with membership number \"{membership_number}\" found in your accessible records.",
                })
                continue
            # Whatever non-empty fields the row actually provides,
            # passed straight through — update_member is idempotent
            # (re-setting an unchanged value is harmless), which
            # avoids any fragile type comparison against the
            # existing record's own current value (a stored None vs.
            # an uploaded empty string are not the same "no change").
            changes = {
                field: (row.get(field) or "").strip()
                for field in updatable_string_fields
                if row.get(field) and (row.get(field) or "").strip()
            }
            if not changes:
                updated.append({"row": i, "member_id": str(existing.id), "full_name": existing.full_name, "note": "No changes given."})
                continue
            try:
                update_member(member=existing, actor=actor, **changes)
                updated.append({"row": i, "member_id": str(existing.id), "full_name": existing.full_name})
            except ValidationError as exc:
                errors.append({"row": i, "full_name": existing.full_name, "error": str(exc.message) if hasattr(exc, "message") else str(exc)})
            continue

        full_name = (row.get("full_name") or "").strip()
        gender = (row.get("gender") or "").strip().lower()
        if not full_name or gender not in ("male", "female"):
            errors.append({"row": i, "full_name": full_name, "error": "full_name and a valid gender (male/female) are required for a new registration."})
            continue

        family = own_family
        family_name = (row.get("family_name") or "").strip()
        if not is_family_scoped and family_name:
            family = Family.objects.filter(community=community, name__iexact=family_name, status="active").first()
            if family is None:
                errors.append({"row": i, "full_name": full_name, "error": f"No active family named \"{family_name}\" found in this community."})
                continue

        try:
            member = register_member(
                community=community, full_name=full_name, gender=gender, family=family,
                phone=(row.get("phone") or "").strip(),
                email=(row.get("email") or "").strip(),
                occupation=(row.get("occupation") or "").strip(),
                address=(row.get("address") or "").strip(),
                mother_name=(row.get("mother_name") or "").strip(),
                father_name=(row.get("father_name") or "").strip(),
                hometown=(row.get("hometown") or "").strip(),
                marital_status=(row.get("marital_status") or "").strip(),
                spouse_name=(row.get("spouse_name") or "").strip(),
                registered_by=actor,
            )
            created.append({"row": i, "member_id": str(member.id), "full_name": member.full_name})
        except ValidationError as exc:
            errors.append({"row": i, "full_name": full_name, "error": str(exc.message) if hasattr(exc, "message") else str(exc)})

    return {
        "created_count": len(created), "updated_count": len(updated), "error_count": len(errors),
        "created": created, "updated": updated, "errors": errors,
    }


_TOWN_ELDER_TRANSFER_ROLES = {"community_admin", "chairman", "secretary", "traditional_leader"}


def transfer_to_town_elder(*, member: Member, title: str, actor) -> Member:
    """
    'Since you become a town elder the community admin or community
    executive should be able to transfer you to be part of the town
    elders ledger.' Deliberately a dedicated, more narrowly-gated
    action than the general update_member — becoming a Town Elder is a
    community-wide recognition, not a routine edit, so it's not left
    open to every role update_member's own broader permission would
    otherwise allow (e.g. a Family Head editing their own family's
    member records).

    Marking a member is_town_leader=True is what actually moves them
    onto the separate Town Elders ledger — see FuneralEvent.rate_for,
    which now resolves them to rate_type="town_elder", their own kind,
    never "general" — for every NEW funeral opened after this call;
    same "never retroactive" rule every other rate change on this
    platform already follows.
    """
    from .models import Member as _Member

    if actor is not None and not actor.is_superuser and actor.role not in _TOWN_ELDER_TRANSFER_ROLES:
        raise ValidationError("Only a Community Admin, Chairman, Secretary, or the Traditional Leader can transfer a member to the Town Elders ledger.")
    if title not in _Member.TownElderTitle.values:
        raise ValidationError(f"'{title}' isn't a recognized town elder title.")

    member.is_town_leader = True
    member.town_elder_title = title
    member.save(update_fields=["is_town_leader", "town_elder_title"])

    from audit_log.services import record_event
    record_event(
        category="role", action="transferred_to_town_elder", actor=actor, community=member.community,
        target_type="Member", target_id=member.id, target_label=member.full_name,
        description=f"'{member.full_name}' transferred to the Town Elders ledger as {dict(_Member.TownElderTitle.choices).get(title, title)}"
        + (f" by '{actor.username}'." if actor else "."),
    )
    return member


def remove_from_town_elder(*, member: Member, actor) -> Member:
    """
    The symmetric counterpart to transfer_to_town_elder above — 'the
    town leader should also have user management... to manage the
    town elders ledger' includes taking someone off it, not only
    adding them. Same authority as the transfer itself; membership in
    this group is a single, reversible fact, not two separately
    -gated actions. Never retroactive, matching every other rate
    change on this platform: any funeral already open when this is
    called keeps whatever rate_type its obligation was generated
    with — only NEW funerals opened afterward see this member back
    at the ordinary family/general rate.
    """
    if actor is not None and not actor.is_superuser and actor.role not in _TOWN_ELDER_TRANSFER_ROLES:
        raise ValidationError("Only a Community Admin, Chairman, Secretary, or the Traditional Leader can remove a member from the Town Elders ledger.")
    if not member.is_town_leader:
        raise ValidationError(f"{member.full_name} isn't currently a Town Elder.")

    member.is_town_leader = False
    member.town_elder_title = None
    member.save(update_fields=["is_town_leader", "town_elder_title"])

    from audit_log.services import record_event
    record_event(
        category="role", action="removed_from_town_elder", actor=actor, community=member.community,
        target_type="Member", target_id=member.id, target_label=member.full_name,
        description=f"'{member.full_name}' removed from the Town Elders ledger"
        + (f" by '{actor.username}'." if actor else "."),
    )
    return member


# 'The collectors should be in 4 categories.' Who may NOMINATE each
# type — the account creator, before any approval has happened.
COLLECTOR_NOMINATION_ROLES = {
    "general": {"chairman", "community_admin"},
    "family": {"family_head"},
    "donation": {"family_head"},
    "town_elder": {"traditional_leader"},
}

# 'For transparency, when one creates an account he needs other
# executives to approve it before that account can start collecting
# money. For the family, he needs family treasurer and secretary to
# confirm. Same as the community needs treasurer and secretary or
# chairman to confirm. The town elders need other two executives to
# confirm.' Each entry is a set of REQUIRED role-groups — a nomination
# is fully approved once at least one distinct approver from EVERY
# group in its list has signed off. A group with more than one role in
# it (e.g. {"secretary", "chairman"} for General) means "any one of
# these", not "all of these".
COLLECTOR_APPROVAL_RULES = {
    "general": [{"treasurer"}, {"secretary", "chairman"}],
    "family": [{"family_treasurer"}, {"family_secretary"}],
    "donation": [{"family_treasurer"}, {"family_secretary"}],
    "town_elder": [{"community_admin", "chairman", "secretary", "treasurer"}, {"community_admin", "chairman", "secretary", "treasurer"}],
}


def nominate_collector(*, member: Member, collector_type: str, actor, scoped_family=None) -> "CollectorNomination":
    """
    Step one of two — creates the pending nomination; the member's own
    role does NOT change yet (still whatever it was before), and they
    cannot collect a single payment until decide_collector_nomination
    below has gathered every required approval.
    """
    from .models import CollectorNomination

    if collector_type not in CollectorNomination.CollectorType.values:
        raise ValidationError(f"'{collector_type}' isn't a recognized collector category.")
    allowed_nominators = COLLECTOR_NOMINATION_ROLES[collector_type]
    if actor is not None and not actor.is_superuser and actor.role not in allowed_nominators:
        raise ValidationError(f"Only {' or '.join(sorted(allowed_nominators))} can nominate a {collector_type} collector.")
    if member.community_id != actor.community_id and not actor.is_superuser:
        raise ValidationError("You can only nominate a member of your own community.")

    if collector_type in ("family", "donation"):
        own_member = getattr(actor, "member_profile", None)
        own_family_id = own_member.family_id if own_member else None
        if own_family_id is None:
            raise ValidationError("You need your own family assignment to nominate a collector for it.")
        if member.family_id != own_family_id:
            raise ValidationError("A Family Head can only nominate a collector from within their own family.")
        scoped_family = own_member.family

    if CollectorNomination.objects.filter(member=member, status=CollectorNomination.Status.PENDING).exists():
        raise ValidationError(f"{member.full_name} already has a pending collector nomination.")

    nomination = CollectorNomination.objects.create(
        community=member.community, member=member, collector_type=collector_type,
        scoped_family=scoped_family, nominated_by=actor,
    )

    from audit_log.services import record_event
    record_event(
        category="role", action="collector_nominated", actor=actor, community=member.community,
        target_type="Member", target_id=member.id, target_label=member.full_name,
        description=f"'{member.full_name}' nominated as a {collector_type} collector by '{actor.username if actor else 'system'}' — awaiting approval.",
    )
    return nomination


def _nomination_approvers_satisfied(nomination) -> bool:
    """
    True once every required "slot" in COLLECTOR_APPROVAL_RULES has its
    own, distinct approver — a genuine matching, not just role-set
    overlap. This distinction matters specifically for Town Elder,
    where both slots share the exact same eligible-role set: overlap
    alone would let ONE approver satisfy both slots at once, silently
    turning "two other executives" into "one." Greedy assignment is
    correct here since every rule has at most two slots.
    """
    approvals = nomination.approvals.filter(decision="approve").select_related("decided_by")
    approvers = [a.decided_by for a in approvals]
    required_groups = COLLECTOR_APPROVAL_RULES[nomination.collector_type]

    used_approver_ids = set()
    for group in required_groups:
        match = next((a for a in approvers if a.id not in used_approver_ids and a.role in group), None)
        if match is None:
            return False
        used_approver_ids.add(match.id)
    return True


def _can_decide_nomination(actor, nomination) -> bool:
    if actor.is_superuser:
        return True
    required_groups = COLLECTOR_APPROVAL_RULES[nomination.collector_type]
    eligible_roles = set().union(*required_groups)
    if actor.role not in eligible_roles:
        return False
    if nomination.collector_type in ("family", "donation"):
        own_member = getattr(actor, "member_profile", None)
        return bool(own_member and nomination.scoped_family_id and own_member.family_id == nomination.scoped_family_id)
    return actor.community_id == nomination.community_id


@transaction.atomic
def decide_collector_nomination(*, nomination: "CollectorNomination", actor, decision: str) -> "CollectorNomination":
    """
    Step two — one executive's own vote. 'Reject' ends the nomination
    outright (a single rejection is final, not just one dissenting
    vote among many — an account under a transparency review that
    anyone involved objects to shouldn't need to be talked into
    existence by outvoting them). 'Approve' records this specific
    person's confirmation and, only once EVERY required role-group
    has a distinct approver on record, actually promotes the member's
    login to role=collector — never before that point, matching 'that
    account can start collecting money' only after full approval.
    """
    from .models import CollectorApproval, CollectorNomination

    if nomination.status != CollectorNomination.Status.PENDING:
        raise ValidationError(f"This nomination is already {nomination.status} — there's nothing left to decide.")
    if not _can_decide_nomination(actor, nomination):
        raise ValidationError(f"'{actor.username}' isn't one of the required approvers for this {nomination.collector_type} collector nomination.")
    if nomination.approvals.filter(decided_by=actor).exists():
        raise ValidationError(f"'{actor.username}' has already decided on this nomination.")
    if decision not in CollectorApproval.Decision.values:
        raise ValidationError(f"'{decision}' isn't a real decision — expected 'approve' or 'reject'.")

    CollectorApproval.objects.create(nomination=nomination, decided_by=actor, decision=decision)

    from audit_log.services import record_event

    if decision == CollectorApproval.Decision.REJECT:
        nomination.status = CollectorNomination.Status.REJECTED
        nomination.decided_at = timezone.now()
        nomination.save(update_fields=["status", "decided_at"])
        record_event(
            category="role", action="collector_nomination_rejected", actor=actor, community=nomination.community,
            target_type="Member", target_id=nomination.member_id, target_label=nomination.member.full_name,
            description=f"'{actor.username}' rejected {nomination.member.full_name}'s {nomination.collector_type} collector nomination.",
        )
        return nomination

    if _nomination_approvers_satisfied(nomination):
        nomination.status = CollectorNomination.Status.APPROVED
        nomination.decided_at = timezone.now()
        nomination.save(update_fields=["status", "decided_at"])

        member = nomination.member
        if member.linked_user_id:
            member.linked_user.role = "collector"
            member.linked_user.save(update_fields=["role"])
        record_event(
            category="role", action="collector_nomination_approved", actor=actor, community=nomination.community,
            target_type="Member", target_id=member.id, target_label=member.full_name,
            description=f"{member.full_name}'s {nomination.collector_type} collector nomination fully approved — now able to collect.",
        )
    else:
        record_event(
            category="role", action="collector_nomination_partially_approved", actor=actor, community=nomination.community,
            target_type="Member", target_id=nomination.member_id, target_label=nomination.member.full_name,
            description=f"'{actor.username}' approved {nomination.member.full_name}'s {nomination.collector_type} collector nomination — still awaiting more approvals.",
        )
    return nomination


def list_collector_nominations(*, community, actor):
    """Every nomination this actor is entitled to see: their own community's, always — this is oversight/transparency data, not restricted to only the specific approvers."""
    from .models import CollectorNomination

    if actor is not None and not actor.is_superuser and actor.community_id != community.id:
        raise ValidationError("You can only view your own community's collector nominations.")
    return list(
        CollectorNomination.objects.filter(community=community)
        .select_related("member", "nominated_by", "scoped_family")
        .prefetch_related("approvals__decided_by")
    )

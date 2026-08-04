"""
Business logic for the Family Management Module.

Kept out of views.py/serializers.py so the rules (what a merge actually
does, what deactivation blocks, etc.) live in one auditable place and are
unit-testable without spinning up HTTP requests.

All functions here assume the caller has already been permission-checked
(see permissions.py) and operate strictly within a single `community` —
none of them ever take data across a community boundary.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Family, FamilyAuditLog


def _log(*, community, family, action, actor, detail=None):
    FamilyAuditLog.objects.create(
        community=community,
        family=family,
        action=action,
        actor=actor,
        detail=detail or {},
    )


@transaction.atomic
def create_family(*, community, name, description="", actor=None):
    if Family.objects.filter(community=community, name__iexact=name, status=Family.Status.ACTIVE).exists():
        raise ValidationError(f"An active family named '{name}' already exists in this community.")

    family = Family.objects.create(
        community=community, name=name, description=description, created_by=actor
    )
    _log(community=community, family=family, action=FamilyAuditLog.Action.CREATED, actor=actor,
         detail={"name": name})
    return family


@transaction.atomic
def register_family_with_head(
    *, community, name, description="", actor=None,
    head_full_name, head_gender, head_username, head_password,
    head_phone="", head_email="", head_ghana_card_number=None, head_address="",
    head_occupation="", head_date_of_birth=None, head_photo=None,
):
    """
    'When a new family is created, the system must require the
    registration of the Family Head as part of the process... created
    automatically and linked to the newly created family.' The
    recommended, real-world way to create a family from now on — but
    deliberately built ON TOP OF create_family/register_member/
    assign_family_head rather than duplicating any of their logic, and
    create_family itself is left completely untouched and still
    directly callable, so every existing test and internal flow that
    creates a family without a head up front (seeding, migrations,
    scenarios where the head genuinely isn't known yet) keeps working
    exactly as it did before this existed.

    Fully atomic: if creating the head's login account fails (e.g. the
    username is already taken), the family itself is rolled back too —
    never a family left stranded with no head because of a partial failure.
    """
    from accounts.models import Role, User
    from members import services as member_services

    family = create_family(community=community, name=name, description=description, actor=actor)

    head_member = member_services.register_member(
        community=community, full_name=head_full_name, gender=head_gender, family=family,
        date_of_birth=head_date_of_birth, occupation=head_occupation, phone=head_phone, email=head_email,
        address=head_address, ghana_card_number=head_ghana_card_number, photo=head_photo,
        registered_by=actor,
    )

    try:
        head_user = User.objects.create_user(
            username=head_username, password=head_password, community=community, role=Role.FAMILY_HEAD,
        )
    except Exception as exc:
        raise ValidationError(f"Could not create the Family Head's login — {exc}") from exc

    member_services.link_member_to_user(member=head_member, user=head_user, actor=actor)
    assign_family_head(family=family, member=head_member, actor=actor)

    return family, head_member, head_user


@transaction.atomic
def rename_family(*, family: Family, new_name: str, actor=None):
    if family.status != Family.Status.ACTIVE:
        raise ValidationError("Only active families can be renamed.")

    if Family.objects.filter(
        community=family.community, name__iexact=new_name, status=Family.Status.ACTIVE
    ).exclude(pk=family.pk).exists():
        raise ValidationError(f"An active family named '{new_name}' already exists in this community.")

    old_name = family.name
    family.name = new_name
    family.slug = ""  # force re-slugify on save
    family.save()
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.RENAMED, actor=actor,
         detail={"old_name": old_name, "new_name": new_name})
    return family


@transaction.atomic
def merge_families(*, source: Family, target: Family, actor=None):
    """
    Merge `source` into `target`. All active members of `source` are
    transferred to `target`. `source` is marked MERGED and its
    `merged_into` pointer is set to `target` so history is never lost.
    Both families must belong to the same community.
    """
    if source.pk == target.pk:
        raise ValidationError("Cannot merge a family into itself.")
    if source.community_id != target.community_id:
        raise ValidationError("Cannot merge families across different communities.")
    if source.status != Family.Status.ACTIVE or target.status != Family.Status.ACTIVE:
        raise ValidationError("Both families must be active to merge.")

    moved_members = list(source.members.filter(status="active"))
    moved_member_ids = [m.id for m in moved_members]
    source.members.filter(status="active").update(family=target)

    from funerals.services import recalculate_open_obligations_for_member
    for member in moved_members:
        member.family_id = target.id  # reflect the update we just made in bulk
        recalculate_open_obligations_for_member(member)

    if source.family_head_id and not target.family_head_id:
        target.family_head_id = source.family_head_id
        target.save(update_fields=["family_head"])

    source.status = Family.Status.MERGED
    source.merged_into = target
    source.save(update_fields=["status", "merged_into", "updated_at"])

    _log(community=source.community, family=source, action=FamilyAuditLog.Action.MERGED, actor=actor,
         detail={"merged_into": str(target.id), "target_name": target.name,
                 "members_moved": [str(m) for m in moved_member_ids]})
    return target


@transaction.atomic
def deactivate_family(*, family: Family, actor=None):
    if family.status != Family.Status.ACTIVE:
        raise ValidationError("Only active families can be deactivated.")
    family.status = Family.Status.DEACTIVATED
    family.deactivated_at = timezone.now()
    family.save(update_fields=["status", "deactivated_at", "updated_at"])
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.DEACTIVATED, actor=actor)
    return family


@transaction.atomic
def reactivate_family(*, family: Family, actor=None):
    if family.status != Family.Status.DEACTIVATED:
        raise ValidationError("Only deactivated families can be reactivated.")
    if Family.objects.filter(
        community=family.community, name__iexact=family.name, status=Family.Status.ACTIVE
    ).exclude(pk=family.pk).exists():
        raise ValidationError(
            "Cannot reactivate: another active family already uses this name. Rename first."
        )
    family.status = Family.Status.ACTIVE
    family.deactivated_at = None
    family.save(update_fields=["status", "deactivated_at", "updated_at"])
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.REACTIVATED, actor=actor)
    return family


@transaction.atomic
def delete_family(*, family: Family, actor=None, force=False):
    """
    Soft-delete only. A family with active members can never be hard- or
    soft-deleted unless `force=True` — and even then its members are not
    deleted, they simply become family-less pending reassignment, because a
    funeral/contribution ledger may reference them historically.
    """
    active_members = family.members.filter(status="active")
    if active_members.exists() and not force:
        raise ValidationError(
            f"Family has {active_members.count()} active member(s). "
            "Transfer or merge them out before deleting, or pass force=True."
        )
    if force:
        active_members.update(family=None)

    family.status = Family.Status.DELETED
    family.deleted_at = timezone.now()
    family.save(update_fields=["status", "deleted_at", "updated_at"])
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.DELETED, actor=actor,
         detail={"forced": force})
    return family


@transaction.atomic
def transfer_members(*, member_ids, target_family: Family, actor=None):
    """Move a specific list of members into target_family (does not require
    them all to share the same source family)."""
    from members.models import Member  # local import avoids app-loading cycles

    members = Member.objects.filter(id__in=member_ids, community=target_family.community)
    if members.count() != len(set(member_ids)):
        raise ValidationError("One or more members were not found in this community.")

    from funerals.services import recalculate_open_obligations_for_member

    for member in members:
        source_family = member.family
        member.family = target_family
        member.save(update_fields=["family"])
        recalculate_open_obligations_for_member(member)
        if source_family:
            _log(community=target_family.community, family=source_family,
                 action=FamilyAuditLog.Action.MEMBER_TRANSFERRED_OUT, actor=actor,
                 detail={"member_id": str(member.id), "to_family": str(target_family.id)})
        _log(community=target_family.community, family=target_family,
             action=FamilyAuditLog.Action.MEMBER_TRANSFERRED_IN, actor=actor,
             detail={"member_id": str(member.id), "from_family": str(source_family.id) if source_family else None})

    return members


@transaction.atomic
def recommend_family_rate(*, family: Family, amount, actor=None):
    """
    A Family Head proposes the amount their own members should pay when a
    funeral is held for their own family. This does NOT take effect on its
    own — it only becomes the operative `standing_family_rate` once a
    Community Administrator approves it. This mirrors the master spec:
    "Recommend Internal Family Contribution Amounts (subject to community
    approval if configured)."
    """
    if amount <= 0:
        raise ValidationError("The recommended amount must be greater than zero.")
    family.recommended_family_rate = amount
    family.save(update_fields=["recommended_family_rate", "updated_at"])
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.RATE_RECOMMENDED,
         actor=actor, detail={"amount": str(amount)})
    return family


@transaction.atomic
def approve_family_rate(*, family: Family, actor=None, amount=None):
    """
    Approve the family's recommended rate (or a Community-Admin-chosen
    `amount` overriding the recommendation) as the new standing rate.
    Existing funerals already in progress are untouched — they keep the
    rate they were created with — only *future* funerals for this family
    will use the newly approved rate.
    """
    final_amount = amount if amount is not None else family.recommended_family_rate
    if final_amount is None:
        raise ValidationError("There is no recommended rate to approve, and no amount was supplied.")
    if final_amount <= 0:
        raise ValidationError("The approved amount must be greater than zero.")

    family.standing_family_rate = final_amount
    family.recommended_family_rate = None
    family.save(update_fields=["standing_family_rate", "recommended_family_rate", "updated_at"])
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.RATE_APPROVED,
         actor=actor, detail={"amount": str(final_amount)})
    return family


@transaction.atomic
def reject_family_rate(*, family: Family, actor=None, reason=""):
    if family.recommended_family_rate is None:
        raise ValidationError("There is no recommended rate to reject.")
    rejected_amount = family.recommended_family_rate
    family.recommended_family_rate = None
    family.save(update_fields=["recommended_family_rate", "updated_at"])
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.RATE_REJECTED,
         actor=actor, detail={"amount": str(rejected_amount), "reason": reason})
    return family


@transaction.atomic
def assign_family_head(*, family: Family, member, actor=None):
    if member.family_id != family.id:
        raise ValidationError("The chosen family head must already be a member of this family.")
    family.family_head = member
    family.save(update_fields=["family_head", "updated_at"])
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.HEAD_ASSIGNED, actor=actor,
         detail={"member_id": str(member.id)})
    return family


def assign_family_officer(*, family: Family, member, officer_role: str, actor=None):
    """
    "Abusuapanin can assign any of his members to use like secretary and
    finance dashboards" — delegates day-to-day Family Fund management to
    a specific member, without touching their platform-wide accounts.Role
    at all. `officer_role` is "secretary" or "treasurer".
    """
    if officer_role not in ("secretary", "treasurer"):
        raise ValidationError("officer_role must be 'secretary' or 'treasurer'.")
    if member.family_id != family.id:
        raise ValidationError("The chosen officer must already be a member of this family.")

    if officer_role == "secretary":
        family.family_secretary = member
        family.save(update_fields=["family_secretary", "updated_at"])
    else:
        family.family_treasurer = member
        family.save(update_fields=["family_treasurer", "updated_at"])

    _log(community=family.community, family=family, action=FamilyAuditLog.Action.OFFICER_ASSIGNED, actor=actor,
         detail={"member_id": str(member.id), "officer_role": officer_role})


def appoint_family_officer_position(*, family: Family, member, title: str, actor=None) -> "FamilyOfficerPosition":
    """
    'Family Head can create: Assistant Family Head... Organizer,
    Welfare Officer, Youth Leader, Women's Leader, Communication
    Officer, Auditor... Custom positions allowed.' Same authority as
    assign_family_officer above (the family's own Head, or Community
    Admin+) — the permission check itself lives in
    CanAssignFamilyOfficer, not duplicated here. Genuinely a real
    record, not a platform role: this never touches accounts.Role or
    grants any new login capability.
    """
    from .models import FamilyOfficerPosition

    title = title.strip()
    if not title:
        raise ValidationError("A title is required.")
    if member.family_id != family.id:
        raise ValidationError("The chosen officer must already be a member of this family.")

    position = FamilyOfficerPosition.objects.create(family=family, member=member, title=title, appointed_by=actor)
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.OFFICER_POSITION_APPOINTED, actor=actor,
         detail={"member_id": str(member.id), "title": title, "position_id": str(position.id)})
    return position


def remove_family_officer_position(*, position: "FamilyOfficerPosition", actor=None) -> None:
    family = position.family
    _log(community=family.community, family=family, action=FamilyAuditLog.Action.OFFICER_POSITION_REMOVED, actor=actor,
         detail={"member_id": str(position.member_id), "title": position.title, "position_id": str(position.id)})
    position.delete()


def list_family_officer_positions(*, family: Family) -> list:
    """Every family officer position is community-wide visible — the same transparency already given to Family Head/Secretary/Treasurer on the Family serializer."""
    return list(family.officer_positions.select_related("member"))
    return family


def is_family_officer(user, family: Family) -> bool:
    """
    Gates access to a family's own Family Fund — "one family head
    shouldn't get access to other families' activities." True only for
    THIS family's own head/secretary/treasurer (matched via the
    requesting user's linked Member — see members.services.link_member_to_user),
    or Community Admin+/superuser for the same platform-oversight tier
    used everywhere else in this platform.
    """
    if user.is_superuser or user.can_manage_families():
        return True
    member = getattr(user, "member_profile", None)
    if member is None:
        return False
    return member.id in (family.family_head_id, family.family_secretary_id, family.family_treasurer_id)


def is_family_finance_officer(user, family: Family) -> bool:
    """
    "Anything bought has to be approved by the finance officer of the
    family... the abusuapanin can also make approval of pay as he's the
    head of the family" — approval authority belongs to the family's own
    treasurer (the day-to-day finance officer) OR the family head
    himself (ultimate authority over his own family's affairs), never
    the secretary who recorded the expense in the first place, and never
    another family's officers. Community Admin+ keeps the same
    platform-oversight tier used everywhere else in this platform.
    """
    if user.is_superuser or user.can_manage_families():
        return True
    member = getattr(user, "member_profile", None)
    return bool(member and member.id in (family.family_treasurer_id, family.family_head_id))

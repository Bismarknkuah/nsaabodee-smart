from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import Role

# "Apart from collectors/frontdesk officer no officer should record
# payment... unless they are paying for themselves." Narrowed from
# Community Admin/Treasurer/Financial Secretary also being able to
# record a payment on someone ELSE's behalf — that authority now
# belongs only to whoever is actually staffing collections: a
# Collector by role, or anyone else specifically assigned to a
# funeral's desk (see is_desk_worker_for, checked separately in the
# view). Recording your OWN contribution — as any role, since every
# user type is also a community member with their own obligations — is
# handled as its own, separate exception in the view, not through this set.
PAYMENT_COLLECTING_ROLES = {
    Role.COLLECTOR,
}

FUNERAL_OPENING_APPROVAL_ROLES = {Role.COMMUNITY_ADMIN, Role.SECRETARY, Role.CHAIRMAN}


class CanRequestFuneralOpening(BasePermission):
    """A Family Head can request for his own family (scoped inside the serializer); Community Admin+ can request for anyone."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.can_manage_families() or request.user.role == Role.FAMILY_HEAD


class CanApproveFuneralOpening(BasePermission):
    """'The community secretary, chairman, or admin — two of them.' Family Head is deliberately not in this pool — he requests, he doesn't also approve his own request."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.role in FUNERAL_OPENING_APPROVAL_ROLES


class IsSameCommunity(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return str(obj.community_id) == str(getattr(request.user, "community_id", None))


class CanManageFunerals(BasePermission):
    """Only Community Administrators (and above) create/close funerals; anyone in the community can view."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.can_manage_families()  # same tier: community_admin+


class CanRecordPayments(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.role in PAYMENT_COLLECTING_ROLES


def is_desk_worker_for(user, funeral, capability: str) -> bool:
    """
    Capability-based, not role-based — this is what makes a
    FuneralDeskAssignment actually DO something: an ordinary Community
    Member, or a brand-new account with no Member profile at all, gains
    real permission to record payments/gifts for exactly one funeral the
    moment they're assigned to a desk whose PURPOSE grants that
    capability, regardless of what their platform-wide role otherwise is
    (or isn't). `capability` is "contributions" or "gifts" — see
    FuneralDeskAssignment.CONTRIBUTION_DESK_TYPES / GIFT_DESK_TYPES for
    which of the four desk purposes (Community/Elders/Guest/Family)
    grants which.
    """
    if not (user and user.is_authenticated):
        return False
    from .models import FuneralDeskAssignment

    granting_types = (
        FuneralDeskAssignment.CONTRIBUTION_DESK_TYPES if capability == "contributions"
        else FuneralDeskAssignment.GIFT_DESK_TYPES
    )
    return FuneralDeskAssignment.objects.filter(
        funeral_event=funeral, user=user, desk_type__in=granting_types, is_active=True
    ).exists()


def is_committee_member_for(user, funeral) -> bool:
    """
    'Committee members should only access information related to the
    funeral event they are assigned to.' Capability-based, exactly
    like is_desk_worker_for above, but for committee membership rather
    than desk assignment — an ordinary Community Member (holding no
    executive role at all) gains real, read-scoped access to exactly
    one funeral's operational detail the moment they're appointed to
    its committee, regardless of what their platform-wide role
    otherwise is. FuneralCommitteePosition links a Member, not a User
    directly, so this goes through the user's own linked member profile.
    """
    if not (user and user.is_authenticated):
        return False
    own_member = getattr(user, "member_profile", None)
    if own_member is None:
        return False
    from .models import FuneralCommitteePosition

    return FuneralCommitteePosition.objects.filter(funeral_event=funeral, member=own_member).exists()


class CanRecordPaymentsOrIsDeskWorker(BasePermission):
    """
    Same as CanRecordPayments, but ALSO lets through anyone assigned to
    this specific funeral's contributions desk — see is_desk_worker_for.
    Deliberately a permissive class-level `has_permission` (desk status
    can't be checked without knowing WHICH funeral, which isn't known
    yet at that point) with the real desk check done inside the view
    once the funeral object is available.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

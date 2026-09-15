from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsSameCommunity(BasePermission):
    """Blocks any cross-tenant access outright, regardless of role."""

    def has_object_permission(self, request, view, obj):
        user_community_id = getattr(request.user, "community_id", None)
        if request.user.is_superuser:
            return True
        return str(obj.community_id) == str(user_community_id)


class CanManageFamilies(BasePermission):
    """
    Read access: any authenticated member of the community (Family Heads,
    Community Members, Guests included) can view the family list/dashboard.

    Write access (create/rename/merge/deactivate/reactivate/delete/transfer/
    assign-head): only Community Administrator and above, per the spec:
    "Community Administrator must be able to: Add Family, Edit Family,
    Delete Family, Merge Families, Deactivate Family, Transfer Members,
    Assign Family Head."
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.can_manage_families()


class CanTransferMembers(BasePermission):
    """
    Transferring members between families is explicitly opened up to
    Chairman and Secretary too, not just Community Admin+ — "same
    community chair or secretary should be able to add all members and
    assign task and can transfer members." Deliberately its own
    permission rather than broadening CanManageFamilies wholesale: a
    Chairman/Secretary doesn't automatically also get family deletion,
    merging, or rate approval just because they can move members around.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        from accounts.models import Role
        return request.user.can_manage_families() or request.user.role in {Role.CHAIRMAN, Role.SECRETARY}


class CanAssignFamilyOfficer(BasePermission):
    """
    Assigning a Family Secretary/Treasurer is the family head's own
    prerogative — "abusuapanin can assign any of his members" — not
    something that should require going through Community Admin the way
    assigning the Family Head itself does. Community Admin+ can still do
    it too, for the same oversight reasons as everywhere else.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.can_manage_families():
            return True
        member = getattr(request.user, "member_profile", None)
        return bool(member and obj.family_head_id == member.id)


class CanRecommendFamilyRate(BasePermission):
    """
    A Family Head may recommend a rate for their own family; Community
    Administrators (and above) may recommend on behalf of any family too.
    Approval is a separate, stricter permission (CanManageFamilies) since
    only management roles may approve/reject.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        from accounts.models import Role
        return request.user.can_manage_families() or request.user.role == Role.FAMILY_HEAD

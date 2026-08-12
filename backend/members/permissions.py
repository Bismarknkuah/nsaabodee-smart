from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import Role

MEMBER_REGISTRATION_ROLES = {
    Role.COMMUNITY_ADMIN,
    Role.CHAIRMAN, Role.SECRETARY, Role.COLLECTOR, Role.FAMILY_HEAD, Role.FAMILY_SECRETARY,
}

# Roles that can register/edit/transfer members across ANY family in the
# community. Family Head and Family Secretary are deliberately excluded
# here — see IsSameFamilyOrCommunityWide below, which restricts both of
# them to acting only on members of the one family they actually belong
# to ("each family head and secretary should be able to create accounts
# for the family members" — THEIR family's members, not the whole
# community's).
COMMUNITY_WIDE_MEMBER_ROLES = {
    Role.COMMUNITY_ADMIN, Role.CHAIRMAN, Role.SECRETARY,
}


class IsSameCommunity(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return str(obj.community_id) == str(getattr(request.user, "community_id", None))


class IsSameFamilyOrCommunityWide(BasePermission):
    """
    Object-level companion to IsSameCommunity: a Family Head or Family
    Secretary editing an existing member, or linking one to a login,
    must be acting on a member of their OWN family — community-wide
    roles (Admin/Chairman/Secretary/Collector) are unrestricted, same as
    always. Read-only requests (viewing) are untouched — every member
    of the community can already see the roster, per CanManageMembers.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if user.is_superuser or user.role in COMMUNITY_WIDE_MEMBER_ROLES:
            return True
        own_member = getattr(user, "member_profile", None)
        return bool(own_member and own_member.family_id and own_member.family_id == obj.family_id)


class CanManageMembers(BasePermission):
    """Anyone in the community can view/search members; registering or editing needs a collecting role."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.role in MEMBER_REGISTRATION_ROLES

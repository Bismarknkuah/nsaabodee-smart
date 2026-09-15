from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import Role

MEMBER_REGISTRATION_ROLES = {
    Role.COMMUNITY_ADMIN,
    Role.CHAIRMAN, Role.SECRETARY, Role.COLLECTOR, Role.FAMILY_HEAD, Role.FAMILY_SECRETARY,
    Role.FAMILY_REGISTRATION_OFFICER, Role.TOWN_REGISTRATION_OFFICER, Role.COMMUNITY_REGISTRATION_DESK,
}

# Roles that can register/edit/transfer members across ANY family in the
# community. Family Head and Family Secretary are deliberately excluded
# here — see IsSameFamilyOrCommunityWide below, which restricts both of
# them to acting only on members of the one family they actually belong
# to ("each family head and secretary should be able to create accounts
# for the family members" — THEIR family's members, not the whole
# community's). Family Registration Officer follows the exact same
# family-scoped restriction (see members.services.register_member) —
# deliberately excluded here too, for the same reason. Town Registration
# Officer is community-wide by jurisdiction (elders aren't tied to one
# family) but restricted to registering ONLY town elders, enforced in
# register_member itself rather than by narrowing this set.
COMMUNITY_WIDE_MEMBER_ROLES = {
    Role.COMMUNITY_ADMIN, Role.CHAIRMAN, Role.SECRETARY, Role.COMMUNITY_REGISTRATION_DESK, Role.TOWN_REGISTRATION_OFFICER,
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

    Traditional Leader gets its own, narrower case rather than being
    added to COMMUNITY_WIDE_MEMBER_ROLES outright: that set is shared
    by every action this permission class gates, and a Traditional
    Leader's own authority (see members.services.assign_role_to_member)
    only ever extends to the Town Elders group, not the whole
    community's roster the way Admin/Chairman/Secretary/Collector's
    does.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if user.is_superuser or user.role in COMMUNITY_WIDE_MEMBER_ROLES:
            return True
        if user.role == "traditional_leader":
            return bool(obj.is_town_leader and obj.community_id == user.community_id)
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


class CanAssignExecutiveRoles(BasePermission):
    """
    'The community admin should be able to add new executive user
    roles... same as each family head should be able to add new
    family executive role, and the town leader should also have these
    features.' A deliberately separate check from CanManageMembers:
    Traditional Leader belongs here (assigning/suspending Town Elders
    executive roles) but should not automatically gain
    CanManageMembers' own, much broader authority to register or edit
    any community member. The actual, narrower scoping for each of
    these three roles (which specific roles, which specific members)
    still lives in members.services.assign_role_to_member and its
    suspend/reactivate companions, not duplicated here.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.role in ("community_admin", "family_head", "traditional_leader")

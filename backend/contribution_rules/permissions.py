from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import Role

# Who can actually change the community's general (male/female) minimum
# contribution rates, and the tiered family rates — Community Admin+,
# the funeral committee Secretary, AND the Chairman ("the community
# chairman and secretary set an amount each family member should pay").
# Family-level own-family rates stay governed separately
# (families.services.approve_family_rate, still Community Admin+ only)
# — this is specifically the community-wide general and tiered rates.
CONTRIBUTION_RULE_MANAGER_ROLES = {
    Role.COMMUNITY_ADMIN, Role.SECRETARY, Role.CHAIRMAN,
}


class CanManageContributionRules(BasePermission):
    """Anyone in the community can view the rules; Community Admin+ or the Secretary can change them."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.role in CONTRIBUTION_RULE_MANAGER_ROLES

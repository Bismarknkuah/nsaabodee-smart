from rest_framework.permissions import BasePermission

from accounts.models import Role

REPORT_VIEWING_ROLES = {
    Role.COMMUNITY_ADMIN, Role.TRADITIONAL_LEADER,
    Role.CHAIRMAN, Role.SECRETARY, Role.TREASURER, Role.FINANCIAL_SECRETARY, Role.AUDITOR,
}

RECEIPT_VIEWING_ROLES = REPORT_VIEWING_ROLES | {Role.COLLECTOR}


def is_family_head_of(user, family) -> bool:
    """
    The abusuapanin (family head) needs to see his own family's
    statement even though he isn't a Community Admin/Treasurer/etc —
    this checks whether the requesting user's own linked Member profile
    (see members.services.link_member_to_user) IS this specific
    family's registered head, not just "some family head somewhere."
    """
    member = getattr(user, "member_profile", None)
    return bool(member and family.family_head_id and member.id == family.family_head_id)


class CanViewReports(BasePermission):
    """Community-wide reports (collections, statements, outstanding members) are for management roles only."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.role in REPORT_VIEWING_ROLES


class CanViewOwnPerformance(BasePermission):
    """Any authenticated collecting role can view THEIR OWN performance report."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanViewReceipts(BasePermission):
    """Collectors can view receipts (they issued them); so can every management role."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.role in RECEIPT_VIEWING_ROLES

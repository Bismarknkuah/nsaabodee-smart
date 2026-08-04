from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import Role

# "The Super Administrator must not... manage community finances...
# access confidential financial records belonging to a community."
# Role.PLATFORM_ADMIN deliberately removed from this
# and every other COMMUNITY-OPERATIONAL role set touched this batch —
# they were baked in as a "can do everything a Community Admin can"
# convenience throughout this project's earlier build, which is exactly
# the conflation this spec calls out. Platform-level access (the
# Communities console, billing records) is untouched — that's checked
# separately, via is_platform_admin(), not through these sets.
EXPENSE_ROLES = {
    Role.COMMUNITY_ADMIN,
    Role.TREASURER, Role.FINANCIAL_SECRETARY,
}
ATTENDANCE_ROLES = {
    Role.COMMUNITY_ADMIN,
    Role.SECRETARY, Role.COLLECTOR, Role.NOTIFICATION_OFFICER,
}


class CanRecordExpenses(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.role in EXPENSE_ROLES


class CanRecordAttendance(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.role in ATTENDANCE_ROLES

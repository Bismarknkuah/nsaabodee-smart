from rest_framework.permissions import BasePermission

from accounts.models import Role

# Mirrors members.permissions.MEMBER_REGISTRATION_ROLES exactly — the
# same people who can register a member into the community are the
# people who can hand that member a task, which matches how the master
# brief describes the two capabilities as one and the same sentence.
TASK_ASSIGNMENT_ROLES = {
    Role.COMMUNITY_ADMIN,
    Role.CHAIRMAN, Role.SECRETARY, Role.FAMILY_HEAD,
}

COMMUNITY_WIDE_TASK_ROLES = {
    Role.COMMUNITY_ADMIN, Role.CHAIRMAN, Role.SECRETARY,
}


class CanAssignTasks(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ("GET", "PATCH"):
            # GET: everyone can see their own tasks. PATCH: object-level
            # check below decides whether THIS task is theirs to update —
            # marking your own task done is a self-service action, not
            # an assignment action, so it doesn't need an assignment role.
            return True
        return request.user.is_superuser or request.user.role in TASK_ASSIGNMENT_ROLES

    def has_object_permission(self, request, view, obj):
        if request.method != "PATCH":
            return True
        if request.user.is_superuser or request.user.role in TASK_ASSIGNMENT_ROLES:
            return True
        own_member = getattr(request.user, "member_profile", None)
        return bool(own_member and obj.assigned_to_id == own_member.id)

from rest_framework.permissions import SAFE_METHODS, BasePermission


class RequiresExecutiveContext(BasePermission):
    """
    'When using Personal Dashboard: EXECUTIVE ACTIONS ARE FORBIDDEN.'
    Deliberately additive — combined with a view's EXISTING role-check
    permission class (e.g. `[IsAuthenticated, CanRecordExpenses,
    RequiresExecutiveContext]`), never replacing it. This only ever
    adds a second gate: even a genuine Treasurer, with every role
    -based permission they'd normally have, is blocked here the moment
    they've switched to their Personal Dashboard — until they switch
    back, which changes nothing about their stored role, only which
    dashboard and which actions are live right now.

    A superuser and anyone not in EXECUTIVE_ROLES (Community Member,
    Guest, Bereaved Rep — roles with no executive/personal distinction
    to switch between in the first place) are never blocked by this,
    since `active_context` defaults to executive and never changes for
    them.

    Only appropriate for a view that is ENTIRELY one executive action —
    never for a mixed read/write viewset, where this would also block
    the ordinary viewing every community member is entitled to. See
    RequiresExecutiveContextForWrites and
    RequiresExecutiveContextForTaskCreation below for the mixed cases.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.is_in_executive_context()


class RequiresExecutiveContextForWrites(BasePermission):
    """
    For a mixed read/write viewset where EVERY write is an executive
    action but viewing is not (member registration and editing): GET,
    HEAD, and OPTIONS are always allowed regardless of context — every
    community member is already entitled to view/search the roster —
    only an actual write (register, edit) is blocked while someone is
    in their Personal Dashboard.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.is_in_executive_context()


class RequiresExecutiveContextForTaskCreation(BasePermission):
    """
    Tasks need a finer distinction than read-vs-write: ASSIGNING a new
    task, REASSIGNING one, ARCHIVING one, and DECIDING its completion
    are all executive actions, but UPDATING the status of a task
    already assigned to you — including by PATCH, not a safe method —
    is explicitly a personal activity ('everyone can update the status
    of tasks assigned to them') that must stay available in Personal
    Dashboard too. Checking `view.action` rather than `request.method`
    is what makes that distinction possible: DRF sets this to
    "create" only for POST-to-the-list-endpoint, never to
    "partial_update" (PATCH-to-one-task) — the self-service status
    update — so only the genuinely executive actions are gated here.
    """

    _EXECUTIVE_ACTIONS = {"create", "reassign", "archive", "unarchive", "decide_completion"}

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(view, "action", None) not in self._EXECUTIVE_ACTIONS:
            return True
        return request.user.is_superuser or request.user.is_in_executive_context()

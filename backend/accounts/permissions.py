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
    Guest — roles with no executive/personal distinction to switch
    between in the first place) are never blocked by this, since
    `active_context` defaults to executive and never changes for them.
    Bereaved Rep CAN now switch context (see
    User.can_switch_dashboard_context) but is intentionally excluded
    from EXECUTIVE_ROLES itself for an unrelated reason — that set also
    decides donation-recipient eligibility — so in practice they never
    hit this check anyway, since they have no executive-only actions to
    perform in the first place.

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


_COMMUNITY_EXECUTIVE_ROLES = {
    "chairman", "secretary", "treasurer", "financial_secretary", "auditor",
    "collector", "traditional_leader", "notification_officer",
    "family_head", "family_secretary", "family_treasurer",
    "family_registration_officer", "town_registration_officer", "community_registration_desk",
}
_FAMILY_EXECUTIVE_ROLES = {"family_secretary", "family_treasurer", "family_registration_officer"}


def can_restrict_features_for(actor, target) -> bool:
    """
    'The community admin should... manage all the family head,
    community executives, community leader, collectors... select what
    they can do or should see in their dashboard. Same as each family
    head should also... select he want each of the family executives
    to have access to, and also select features he want members to
    have access to.'

    Two distinct tiers of authority, deliberately never overlapping:
    - Community Admin can restrict any executive role WITHIN their own
      community (Family Head included, since a family officer is still
      part of the community the Admin runs) — never another Community
      Admin, never a plain Community Member/Guest (that's not what
      "executive" means here), never themselves.
    - Family Head can restrict their own family's Secretary/Treasurer,
      and any ordinary member of their own family — never anyone
      outside their own family, never themselves.

    Self-restriction is blocked for the same reason it's blocked for
    Platform Admin: an accidental self-restriction of something needed
    to undo a mistake would be a real, hard lockout.
    """
    if actor.id == target.id:
        return False
    if target.is_superuser:
        return False

    if actor.role == "community_admin":
        if target.community_id != actor.community_id:
            return False
        return target.role in _COMMUNITY_EXECUTIVE_ROLES

    if actor.role == "family_head":
        own_member = getattr(actor, "member_profile", None)
        own_family_id = own_member.family_id if own_member else None
        if own_family_id is None:
            return False
        target_member = getattr(target, "member_profile", None)
        if target.role in _FAMILY_EXECUTIVE_ROLES:
            return bool(target_member and target_member.family_id == own_family_id)
        if target.role == "community_member":
            return bool(target_member and target_member.family_id == own_family_id)
        return False

    if actor.role == "traditional_leader":
        # 'The chief should also have user management and system
        # settings features to manage town elders, including adding
        # town elders and the town elders' executive.' Scoped to
        # membership in the Town Elders group itself (Member.is_town_leader),
        # not to any particular User.role — a Town Elder can otherwise
        # hold any ordinary account type, exactly like Community Admin's
        # own scope is "which role", not "which account type".
        if target.community_id != actor.community_id:
            return False
        target_member = getattr(target, "member_profile", None)
        return bool(target_member and target_member.is_town_leader)

    return False

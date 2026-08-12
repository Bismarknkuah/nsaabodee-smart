"""
One recorder, used everywhere a general audit entry is needed, so
every entry has the exact same shape and there's exactly one place
this logic could ever drift. Individual call sites (tenants/services.py,
members/services.py, funerals/services.py, etc.) call `record_event`
with their own category/action/description — the recording itself
never needs to know the specifics of what triggered it.
"""
from .models import AuditLogEntry


def record_event(
    *, category: str, action: str, description: str, actor=None, community=None,
    target_type: str = "", target_id: str = "", target_label: str = "", metadata: dict = None,
) -> AuditLogEntry:
    return AuditLogEntry.objects.create(
        category=category,
        action=action,
        description=description,
        actor=actor,
        actor_username=getattr(actor, "username", ""),
        actor_role=getattr(actor, "role", "") or "",
        community=community,
        target_type=target_type,
        target_id=str(target_id) if target_id else "",
        target_label=target_label,
        metadata=metadata or {},
    )


def list_audit_log(*, actor, community=None, category: str = None, limit: int = 200) -> list:
    """
    Platform Admin (or superuser) sees the whole platform, optionally
    filtered to one community. A Community Admin sees only their own
    community's entries — never another's, never platform-level
    entries (community=None) that aren't theirs to see.
    """
    from django.core.exceptions import ValidationError

    qs = AuditLogEntry.objects.all()

    is_platform_admin = actor.is_superuser or actor.role == "platform_admin"
    if is_platform_admin:
        if community is not None:
            qs = qs.filter(community=community)
    elif actor.role == "community_admin" and actor.community_id:
        if community is not None and str(community.id) != str(actor.community_id):
            raise ValidationError("You can only view your own community's audit log.")
        qs = qs.filter(community_id=actor.community_id)
    else:
        raise ValidationError("Only a Platform Admin or Community Admin can view the audit log.")

    if category:
        qs = qs.filter(category=category)
    return list(qs[:limit])

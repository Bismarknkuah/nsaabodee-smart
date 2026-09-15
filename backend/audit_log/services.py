"""
One recorder, used everywhere a general audit entry is needed, so
every entry has the exact same shape and there's exactly one place
this logic could ever drift. Individual call sites (tenants/services.py,
members/services.py, funerals/services.py, etc.) call `record_event`
with their own category/action/description — the recording itself
never needs to know the specifics of what triggered it.
"""
from django.db import models

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
    'All the community logs should go to the community administrator
    not the platform admin. The platform admin should only see the
    logs of the community admins only, not members.' A Community
    Admin already saw every entry for their own community regardless
    of who the actor was — that part needed no change. Platform
    Admin's own view is now filtered to entries whose actor role is
    community_admin (or system-generated entries with no actor at
    all, e.g. an automated escalation) — never a Family Head,
    Collector, Traditional Leader, or ordinary member's own action,
    no matter which community it happened in. A genuine Django
    superuser bypasses this (the same debugging-account exception
    every business-level restriction on this platform already makes)
    — 'platform_admin' is the business role this rule actually targets.
    """
    from django.core.exceptions import ValidationError

    qs = AuditLogEntry.objects.all()

    is_platform_admin_role = (not actor.is_superuser) and actor.role == "platform_admin"
    if actor.is_superuser:
        if community is not None:
            qs = qs.filter(community=community)
    elif is_platform_admin_role:
        if community is not None:
            qs = qs.filter(community=community)
        qs = qs.filter(models.Q(actor_role__in=["community_admin", "platform_admin"]) | models.Q(actor__isnull=True))
    elif actor.role == "community_admin" and actor.community_id:
        if community is not None and str(community.id) != str(actor.community_id):
            raise ValidationError("You can only view your own community's audit log.")
        qs = qs.filter(community_id=actor.community_id)
    else:
        raise ValidationError("Only a Platform Admin or Community Admin can view the audit log.")

    if category:
        qs = qs.filter(category=category)
    return list(qs[:limit])

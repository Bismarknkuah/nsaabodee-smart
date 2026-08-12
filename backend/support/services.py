from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SupportTicket, SupportTicketMessage


def _is_platform_admin(user) -> bool:
    return bool(user and (user.is_superuser or user.role == "platform_admin"))


def _is_community_admin_ticket(ticket: SupportTicket) -> bool:
    """
    'Only the community and temporary support should be moved or
    reported to the platform admin' — a ticket raised by a Community
    Admin (ordinary or of a temporary/rental community, since both use
    the same role) concerns the community's own standing on the
    platform, which only the Platform Admin can actually act on.
    """
    return ticket.submitted_by.role == "community_admin"


def _is_community_admin_of(user, community) -> bool:
    return bool(
        user and community and not user.is_superuser and user.role == "community_admin" and user.community_id == community.id
    )


def submit_ticket(*, submitted_by, subject: str, description: str, priority: str = SupportTicket.Priority.MEDIUM) -> SupportTicket:
    """Any signed-in user, any role — a Guest with no community is just as entitled to raise a problem as anyone else."""
    if not subject.strip():
        raise ValidationError("A subject is required.")
    if not description.strip():
        raise ValidationError("A description is required.")
    return SupportTicket.objects.create(
        submitted_by=submitted_by, community=submitted_by.community, subject=subject.strip(),
        description=description.strip(), priority=priority,
    )


def list_my_tickets(*, user) -> list:
    return list(SupportTicket.objects.filter(submitted_by=user))


def list_all_tickets(*, actor, status: str = None) -> list:
    """
    'All other members or executives support should be reported to
    their community admin as their community admin should have those
    reports.' Two entirely separate queues, by design: the Platform
    Admin's queue is community/temporary-admin escalations only; a
    Community Admin's own queue is every other role's tickets from
    their own community only — never another community's, and never
    a fellow Community Admin's own escalation, which stays reserved
    for the Platform Admin.
    """
    if _is_platform_admin(actor):
        qs = SupportTicket.objects.filter(submitted_by__role="community_admin")
    elif actor.role == "community_admin":
        qs = SupportTicket.objects.filter(community=actor.community).exclude(submitted_by__role="community_admin")
    else:
        raise ValidationError("Only a Platform Administrator or a Community Administrator can view a support ticket queue.")
    if status:
        qs = qs.filter(status=status)
    return list(qs)


def can_access_ticket(*, user, ticket: SupportTicket) -> bool:
    if ticket.submitted_by_id == user.id:
        return True
    if _is_community_admin_ticket(ticket):
        return _is_platform_admin(user)
    return _is_community_admin_of(user, ticket.community)


def update_ticket_status(*, ticket: SupportTicket, status: str, actor) -> SupportTicket:
    if not can_access_ticket(user=actor, ticket=ticket) or actor.id == ticket.submitted_by_id:
        raise ValidationError("Only the administrator this ticket was routed to can change its status.")
    if status not in SupportTicket.Status.values:
        raise ValidationError(f"'{status}' isn't a real ticket status.")
    ticket.status = status
    if status in (SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED) and not ticket.resolved_at:
        ticket.resolved_at = timezone.now()
    ticket.save(update_fields=["status", "resolved_at", "updated_at"])
    return ticket


def post_ticket_message(*, ticket: SupportTicket, sender, content: str) -> SupportTicketMessage:
    if not can_access_ticket(user=sender, ticket=ticket):
        raise ValidationError("You don't have access to this ticket.")
    if not content.strip():
        raise ValidationError("A message can't be empty.")
    return SupportTicketMessage.objects.create(ticket=ticket, sender=sender, content=content.strip())


def list_ticket_messages(*, ticket: SupportTicket, actor) -> list:
    if not can_access_ticket(user=actor, ticket=ticket):
        raise ValidationError("You don't have access to this ticket.")
    return list(ticket.messages.select_related("sender"))

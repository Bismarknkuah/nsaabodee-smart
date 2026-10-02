"""
Resolves who a Notification (notifications.models.Notification) actually
reaches, and dispatches it across whichever channels have a usable
contact address. This is the piece that makes a role-scoped notification
("the Treasurer") concrete: it's turned into every User in that
community with that role, then — for each — whichever of email/SMS/
WhatsApp that specific person has a real address for.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import DeliveryAttempt
from .providers import ConsoleProvider, EmailProvider, ProviderNotConfiguredError, SmsProvider, WhatsAppProvider

_PROVIDERS = {
    DeliveryAttempt.Channel.CONSOLE: ConsoleProvider(),
    DeliveryAttempt.Channel.EMAIL: EmailProvider(),
    DeliveryAttempt.Channel.SMS: SmsProvider(),
    DeliveryAttempt.Channel.WHATSAPP: WhatsAppProvider(),
}

DEFAULT_CHANNELS = [DeliveryAttempt.Channel.CONSOLE, DeliveryAttempt.Channel.EMAIL, DeliveryAttempt.Channel.SMS]


def resolve_recipients(notification):
    """
    Every User this notification actually reaches. A role-scoped
    notification ("Treasurer") resolves to every User with that role in
    the SAME community — never across communities, same tenant-isolation
    rule as everywhere else in this platform.
    """
    User = get_user_model()
    if notification.recipient_user_id:
        return [notification.recipient_user]
    if notification.recipient_role:
        return list(User.objects.filter(community=notification.community, role=notification.recipient_role))
    return []


def _contact_address(user, channel) -> str:
    if channel == DeliveryAttempt.Channel.EMAIL:
        return user.email or ""
    if channel in (DeliveryAttempt.Channel.SMS, DeliveryAttempt.Channel.WHATSAPP):
        member = getattr(user, "member_profile", None)
        return member.phone if member else ""
    return ""


def deliver_notification(notification, channels=None):
    """
    Attempts delivery of one Notification across `channels` (defaults to
    console + email + SMS — WhatsApp is opt-in given its stricter
    template/window rules, see WhatsAppProvider's doc comment) for every
    resolved recipient. Every attempt is recorded via DeliveryAttempt
    regardless of outcome — including a channel that isn't configured at
    all, so "we never even tried" and "we tried and it failed" are always
    distinguishable in the audit trail.
    """
    channels = channels or DEFAULT_CHANNELS
    recipients = resolve_recipients(notification)
    attempts = []

    for user in recipients:
        for channel in channels:
            provider = _PROVIDERS[channel]
            address = _contact_address(user, channel) if channel != DeliveryAttempt.Channel.CONSOLE else user.username

            if channel != DeliveryAttempt.Channel.CONSOLE and not address:
                attempts.append(DeliveryAttempt.objects.create(
                    notification=notification, channel=channel, recipient_address="",
                    status=DeliveryAttempt.Status.SKIPPED_NO_ADDRESS,
                    provider_response="This user has no contact address on file for this channel.",
                ))
                continue
            try:
                result = provider.send(recipient_address=address, subject="Nsaabodeɛ Smart notification", message=notification.message)
                attempts.append(DeliveryAttempt.objects.create(
                    notification=notification, channel=channel, recipient_address=address,
                    status=result.status, provider_response=result.provider_response,
                ))
            except ProviderNotConfiguredError as exc:
                attempts.append(DeliveryAttempt.objects.create(
                    notification=notification, channel=channel, recipient_address=address,
                    status=DeliveryAttempt.Status.SKIPPED_NOT_CONFIGURED, provider_response=str(exc),
                ))
    return attempts


MEETING_SCHEDULING_ROLES = {"community_admin", "chairman", "secretary"}


def _can_schedule_meeting(actor, family=None, funeral=None) -> bool:
    """Community leadership can schedule for anyone; a Family Head can additionally schedule for their own family; a funeral's own committee member can schedule for that funeral."""
    if actor is None:
        return True
    if actor.is_superuser or actor.role in MEETING_SCHEDULING_ROLES:
        return True
    if family is not None and actor.role == "family_head":
        own_member = getattr(actor, "member_profile", None)
        return bool(own_member is not None and own_member.family_id == family.id)
    if funeral is not None:
        from funerals.permissions import is_committee_member_for
        return is_committee_member_for(actor, funeral)
    return False


def schedule_meeting(*, community, title, scheduled_for, description="", location="", family=None, funeral=None, actor=None):
    """
    'View meeting schedules' (community-wide) / 'Schedule family
    meetings' (Family Head) / 'Schedule meetings' (Funeral Committee) —
    the same underlying model, scoped by whichever of family/funeral is
    given (mutually exclusive; a meeting belongs to at most one of
    them, or neither for a community-wide one). A Family Head can only
    schedule for their own family; a funeral's committee member can
    only schedule for that funeral; community leadership can schedule
    any kind.
    """
    from django.core.exceptions import ValidationError
    from .models import CommunityMeeting

    if family is not None and funeral is not None:
        raise ValidationError("A meeting belongs to a family, a funeral, or the whole community — never more than one of those at once.")

    if not _can_schedule_meeting(actor, family=family, funeral=funeral):
        if family is not None:
            raise ValidationError("Only your own family's Family Head, or community leadership, can schedule a meeting for this family.")
        if funeral is not None:
            raise ValidationError("Only this funeral's own committee members, or community leadership, can schedule a meeting for it.")
        raise ValidationError("Only Community Admin, Chairman, or Secretary can schedule a community-wide meeting.")

    meeting = CommunityMeeting.objects.create(
        community=community, family=family, funeral_event=funeral, title=title.strip(), description=description.strip(),
        scheduled_for=scheduled_for, location=location.strip(), created_by=actor,
    )
    from audit_log.services import record_event
    scope_note = f", for {family.name} only." if family else (f", for {funeral.deceased_name}'s committee only." if funeral else ".")
    record_event(
        category="community", action="meeting_scheduled", actor=actor, community=community,
        target_type="CommunityMeeting", target_id=meeting.id, target_label=meeting.title,
        description=f"'{meeting.title}' scheduled for {scheduled_for.date().isoformat()}" + scope_note,
    )
    return meeting


def cancel_meeting(*, meeting, actor=None):
    from django.core.exceptions import ValidationError

    if not _can_schedule_meeting(actor, family=meeting.family, funeral=meeting.funeral_event):
        raise ValidationError("You don't have authority to cancel this meeting.")
    meeting.is_cancelled = True
    meeting.save(update_fields=["is_cancelled"])
    return meeting


def list_upcoming_meetings(community, family=None, funeral=None):
    """
    Community-wide meetings are visible to everyone in the community.
    A family's own meetings are visible only alongside that specific
    family's own view; a funeral's committee meetings only alongside
    that funeral's own committee view — this function itself doesn't
    enforce that visibility restriction, its caller does, matching how
    every other scoped read in this platform works.
    """
    from django.utils import timezone
    from .models import CommunityMeeting

    qs = CommunityMeeting.objects.filter(community=community, is_cancelled=False, scheduled_for__gte=timezone.now())
    if family is not None:
        qs = qs.filter(Q(family__isnull=True) | Q(family=family))
    elif funeral is not None:
        qs = qs.filter(Q(family__isnull=True, funeral_event__isnull=True) | Q(funeral_event=funeral))
    else:
        qs = qs.filter(family__isnull=True, funeral_event__isnull=True)
    return qs.order_by("scheduled_for")

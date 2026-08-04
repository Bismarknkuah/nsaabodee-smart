import uuid

from django.conf import settings
from django.db import models


class CommunityMeeting(models.Model):
    """
    'View meeting schedules.' A scheduled community meeting, announced
    by community leadership and visible to everyone in the community —
    the Traditional Leader included, on their own oversight dashboard —
    not a private calendar entry belonging to any one person.

    'Schedule family meetings' (Family Head) reuses this exact model
    rather than a parallel one: family is null for a community-wide
    meeting, set for a family-only one. Same underlying concept
    (a scheduled gathering with a time and place), just a narrower
    audience — no reason to duplicate the whole feature for a
    different scope.

    'Schedule meetings' (Funeral Committee) extends the same pattern a
    third way: funeral_event set means this meeting belongs to one
    funeral's own committee, visible only to that funeral's committee
    members plus community leadership — never to the wider community
    or another funeral's committee.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="meetings")
    family = models.ForeignKey(
        "families.Family", null=True, blank=True, on_delete=models.CASCADE, related_name="meetings",
        help_text="Null for a community-wide meeting; set for a single family's own meeting.",
    )
    funeral_event = models.ForeignKey(
        "funerals.FuneralEvent", null=True, blank=True, on_delete=models.CASCADE, related_name="meetings",
        help_text="Set for a single funeral's own committee meeting.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    scheduled_for = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    is_cancelled = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_for"]

    def __str__(self):
        return f"{self.title} — {self.scheduled_for.date().isoformat()}"


class DeliveryAttempt(models.Model):
    """
    An audit trail row for every attempt to actually deliver a
    Notification (see notifications.models.Notification) over a real
    channel — email, SMS, WhatsApp. This exists independently of whether
    the attempt succeeded: a community with no Twilio account configured
    yet should still see "we tried to SMS the Treasurer, but SMS isn't
    configured" rather than the attempt vanishing silently, the same way
    the rest of this platform prefers an honest recorded state over a
    silent no-op.
    """

    class Channel(models.TextChoices):
        CONSOLE = "console", "Console (development log)"
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        SKIPPED_NOT_CONFIGURED = "skipped_not_configured", "Skipped — Channel Not Configured"
        SKIPPED_NO_ADDRESS = "skipped_no_address", "Skipped — No Contact Address"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        "notifications.Notification", on_delete=models.CASCADE, related_name="delivery_attempts"
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    recipient_address = models.CharField(max_length=255, blank=True, help_text="Email address or phone number attempted, if any.")
    status = models.CharField(max_length=30, choices=Status.choices)
    provider_response = models.TextField(blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attempted_at"]

    def __str__(self):
        return f"{self.channel} -> {self.recipient_address or '(none)'}: {self.status}"

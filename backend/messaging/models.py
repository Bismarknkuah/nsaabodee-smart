"""
'Add message channel to all user types and should be a channel from
top to down.' Three channel types, matching the actual organizational
hierarchy this platform already has — not real-time WebSocket delivery
(the one existing WS consumer in realtime/ has a flagged, unresolved
auth gap; building more on top of that would compound a real problem
rather than solve one), but the same REST + refetch pattern already
proven for notifications and the chatbot.

- Platform channel: one for the whole platform. Platform Admin posts;
  every Community Admin, across every community, can read and reply —
  the top of the hierarchy reaching every community's own leadership.
- Community channel: one per community. Every member of that
  community can read and post — Community Admin, Chairman, and
  Secretary are simply members of it too, not exclusive gatekeepers,
  since a community-wide channel needs everyone in it to be useful.
- Family channel: one per family. Every member of that family can
  read and post, the same way.

Channels are never created by hand — one gets created automatically
the moment it's first needed (a community is created, a family is
created), the same "the thing that should always exist just always
does" pattern as ContributionObligation.
"""
import uuid

from django.conf import settings
from django.db import models


class Channel(models.Model):
    class ChannelType(models.TextChoices):
        PLATFORM = "platform", "Platform"
        COMMUNITY = "community", "Community"
        FAMILY = "family", "Family"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices)
    community = models.ForeignKey("tenants.Community", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    family = models.ForeignKey("families.Family", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["channel_type", "community", "family"], name="one_channel_per_scope"),
        ]

    def __str__(self):
        return self.name


class ChannelMessage(models.Model):
    """A real, permanent record — 'make sure proper records are being taken and kept safe' applies here exactly as it does everywhere else messages or decisions get made in this platform."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender_id} in {self.channel.name}"

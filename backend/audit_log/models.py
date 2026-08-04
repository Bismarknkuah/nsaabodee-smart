"""
'View audit logs' — one of the Platform Admin capabilities from the
spec that genuinely didn't exist anywhere in this codebase. This is
NOT a replacement for the scoped logs already built for specific
high-stakes workflows — FamilyAuditLog (family structural changes),
AnnouncementReviewLog (submission/approval/rejection), and
PaymentReversal's own built-in trail all stay exactly as they are and
keep their own detailed, workflow-specific records. This is the
general layer that covers everything else worth a permanent record:
community lifecycle (created, deactivated, reactivated, access
extended), role grants, funeral-opening decisions, payment-reversal
decisions, platform billing actions, and homepage-feature grants.

Deliberately simple and append-only, the same principle every audit
trail in this platform already follows: no update, no delete, ever.
"""
import uuid

from django.conf import settings
from django.db import models


class AuditLogEntry(models.Model):
    class Category(models.TextChoices):
        COMMUNITY = "community", "Community Lifecycle"
        ROLE = "role", "Role Assignment"
        FUNERAL_OPENING = "funeral_opening", "Funeral Opening Decision"
        PAYMENT_REVERSAL = "payment_reversal", "Payment Reversal Decision"
        BILLING = "billing", "Platform Billing"
        ANNOUNCEMENT = "announcement", "Announcement / Homepage Feature"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=30, choices=Category.choices)
    action = models.CharField(max_length=100)

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    # Snapshots, not just the FK — a person's username/role can change
    # (or their account can be deleted) without the historical record
    # of what they did at the time becoming meaningless or vanishing.
    actor_username = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=30, blank=True)

    community = models.ForeignKey("tenants.Community", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    # A simple, generic reference — not a GenericForeignKey — since an
    # audit log is written once and read many times; it never needs to
    # resolve back into a live queryset the way a real relation would.
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    target_label = models.CharField(max_length=255, blank=True)

    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["community", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.category}] {self.action} by {self.actor_username or 'system'}"

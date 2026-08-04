import uuid

from django.db import models


class MeetingSummary(models.Model):
    """
    Stores the input transcript alongside whatever
    llm_provider.MeetingSummaryProvider returned, so a Secretary can
    always go back and check the summary against what was actually said
    — an LLM summary is a draft to review, not a record to trust blindly.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    transcript = models.TextField()
    summary = models.TextField(blank=True)
    decisions = models.JSONField(default=list, blank=True)
    action_items = models.JSONField(default=list, blank=True)
    generated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SuspiciousTransactionFlag(models.Model):
    """
    A recorded flag from the rule-based anomaly checks in services.py —
    kept as a real row (not just a log line) so a Treasurer or Auditor
    has an actual dashboard to review and dismiss/confirm flags from,
    the same "record what was decided, don't just react silently"
    pattern the rest of this platform follows for audit trails.
    """

    class Reason(models.TextChoices):
        AMOUNT_OUTLIER = "amount_outlier", "Unusual amount for this collector"
        RAPID_SUCCESSION = "rapid_succession", "Many payments in rapid succession"

    class ReviewStatus(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed"
        CONFIRMED = "confirmed", "Confirmed genuine concern"
        DISMISSED = "dismissed", "Dismissed — false positive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    payment = models.ForeignKey("funerals.ContributionPayment", on_delete=models.CASCADE, related_name="suspicion_flags")
    reason = models.CharField(max_length=30, choices=Reason.choices)
    detail = models.TextField(blank=True)
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.UNREVIEWED)
    flagged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-flagged_at"]
        constraints = [
            models.UniqueConstraint(fields=["payment", "reason"], name="one_flag_per_payment_per_reason")
        ]


class ChatbotMessage(models.Model):
    """
    'Add chatbot to all user types... make sure proper records are
    being taken and kept safe.' Every exchange is a real, persisted
    row — not an ephemeral browser-only chat that vanishes on refresh
    — visible only to the person who sent it; nothing here is
    queryable across users or communities. The same "record what
    happened, don't just react silently" pattern this platform already
    follows for meeting summaries and suspicious-transaction flags.
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="chatbot_messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

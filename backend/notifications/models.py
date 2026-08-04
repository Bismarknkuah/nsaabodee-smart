import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    A minimal in-app notification record. This module intentionally does
    NOT implement the SMS/WhatsApp/push/email delivery channels described
    in the master brief's Communication Module — that's a separate module
    with its own provider integrations. What lives here is the trigger and
    the record: "the system decided X person/role needed to know Y", so
    that module has something concrete to send from once it's built.
    """

    class Category(models.TextChoices):
        DEFAULTER_ESCALATION = "defaulter_escalation", "Defaulter Escalation"
        FAMILY_EXPENSE_APPROVAL = "family_expense_approval", "Family Expense Approval"
        OLD_DEBT = "old_debt", "Old Debt Alert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=40, choices=Category.choices)
    message = models.TextField()

    # Either a specific user, or a role-scope (e.g. every Treasurer in the
    # community) — at least one of these is always set.
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications"
    )
    recipient_role = models.CharField(max_length=32, blank=True)

    related_member = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

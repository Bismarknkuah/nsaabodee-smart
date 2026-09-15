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
        BIRTHDAY = "birthday", "Birthday"
        # 'When Family A launches a campaign: notifications go to
        # eligible Family A members. Do NOT notify all community
        # members unless the campaign scope says COMMUNITY.' One
        # category covering both scopes — the recipient list itself
        # (built from the same eligibility this campaign already uses
        # to generate obligations) is what actually enforces the scope,
        # not a separate category per scope.
        WELFARE_CAMPAIGN_LAUNCHED = "welfare_campaign_launched", "Welfare Campaign Launched"
        # 'The platform admin should have a way to remind communities
        # to pay their subscription fees.' Goes to every Community
        # Admin in the community, not just one — the same reasoning as
        # every other community-wide notification on this platform.
        SUBSCRIPTION_REMINDER = "subscription_reminder", "Subscription Reminder"
        # 'Members notification should have features where they can see
        # what has been posted on the notice board.' Sent the moment an
        # announcement is actually approved — a pending or rejected one
        # was never genuinely "posted," so members are never notified
        # about either.
        NOTICE_BOARD_POST = "notice_board_post", "Notice Board Post"

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

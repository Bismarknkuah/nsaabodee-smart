import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    PLATFORM_ADMIN = "platform_admin", "Platform Administrator"
    COMMUNITY_ADMIN = "community_admin", "Community Administrator"
    TRADITIONAL_LEADER = "traditional_leader", "Traditional Leader (Chief)"
    CHAIRMAN = "chairman", "Chairman"
    SECRETARY = "secretary", "Secretary"
    TREASURER = "treasurer", "Treasurer"
    FINANCIAL_SECRETARY = "financial_secretary", "Financial Secretary"
    AUDITOR = "auditor", "Auditor"
    COLLECTOR = "collector", "Collector"
    FAMILY_HEAD = "family_head", "Family Head"
    FAMILY_SECRETARY = "family_secretary", "Family Secretary"
    FAMILY_TREASURER = "family_treasurer", "Family Treasurer"
    COMMUNITY_MEMBER = "community_member", "Community Member"
    GUEST = "guest", "Guest"
    BEREAVED_REP = "bereaved_rep", "Bereaved Family Representative"
    NOTIFICATION_OFFICER = "notification_officer", "Notification Officer"


# Roles allowed to perform destructive / structural family-management actions
# at the community level (add, rename, merge, deactivate, delete).
FAMILY_MANAGEMENT_ROLES = {
    Role.COMMUNITY_ADMIN,
}

# "Every community executive MUST have two separate identities" — the
# roles genuinely eligible to switch into a Personal Dashboard.
# Community Member, Guest, and Bereaved Rep are excluded deliberately:
# they have no executive powers to begin with, so there's no "personal
# vs official" distinction for them to switch between. Platform Admin
# is excluded too — a cross-community role with no single community
# membership of their own to have a personal profile in.
EXECUTIVE_ROLES = {
    Role.COMMUNITY_ADMIN, Role.TRADITIONAL_LEADER, Role.CHAIRMAN, Role.SECRETARY,
    Role.TREASURER, Role.FINANCIAL_SECRETARY, Role.AUDITOR, Role.COLLECTOR,
    Role.FAMILY_HEAD, Role.FAMILY_SECRETARY, Role.FAMILY_TREASURER, Role.NOTIFICATION_OFFICER,
}


class DashboardContext(models.TextChoices):
    EXECUTIVE = "executive", "Executive"
    PERSONAL = "personal", "Personal"


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(
        "tenants.Community",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
        help_text="Null only for Super/Platform Administrators who span communities.",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.GUEST)
    profile_photo = models.ImageField(upload_to="profile_photos/", null=True, blank=True)
    # Optional — set by the person themselves (Profile page) or an
    # admin, enabling phone+OTP login for this account ALONGSIDE the
    # existing username/password login, not instead of it. Deliberately
    # additive: replacing username/password entirely would put every
    # existing test, every demo account, and everything already built
    # on top of it at real risk for no real gain.
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    # "Switch to Personal Dashboard... does not require logout, does not
    # create another account, only changes permission context." This is
    # the whole mechanism — one extra field, checked by
    # RequiresExecutiveContext (accounts/permissions.py) on every
    # view that gates an official executive action, and by the
    # dashboard dispatcher to decide which dashboard to actually show.
    active_context = models.CharField(max_length=20, choices=DashboardContext.choices, default=DashboardContext.EXECUTIVE)

    def can_manage_families(self) -> bool:
        return self.is_superuser or self.role in FAMILY_MANAGEMENT_ROLES

    def can_switch_dashboard_context(self) -> bool:
        """Only an actual executive, with a personal profile to switch TO, has anything to switch between."""
        return self.role in EXECUTIVE_ROLES and bool(getattr(self, "member_profile", None))

    def is_in_executive_context(self) -> bool:
        return self.active_context == DashboardContext.EXECUTIVE


class PhoneOTP(models.Model):
    """
    A one-time login code sent by SMS. Deliberately its own small,
    short-lived record rather than routed through the Notification/
    DeliveryAttempt system — that machinery exists to give a permanent,
    auditable trail of community-facing messages; a security code is
    the opposite of something that should leave a durable, readable
    record lying around once it's served its purpose.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.phone_number}"

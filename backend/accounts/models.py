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
    # 'We have to get registration officer, for each ledger... each
    # family will have their registration officer, who will register
    # for only his family members... registration officer who will
    # register the town elders... registration officer desks who
    # will register the whole community and assign them to a family
    # and a ledger.' Dedicated roles whose only real job is
    # registration — distinct from Family Head/Secretary (who already
    # have family-scoped registration authority alongside their many
    # other duties) so a family can delegate registration specifically
    # without handing over everything else a Family Head can do.
    FAMILY_REGISTRATION_OFFICER = "family_registration_officer", "Family Registration Officer"
    TOWN_REGISTRATION_OFFICER = "town_registration_officer", "Town Elders Registration Officer"
    COMMUNITY_REGISTRATION_DESK = "community_registration_desk", "Community Registration Desk"


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
#
# Deliberately does NOT include Bereaved Rep, even though they now get
# dashboard-context-switching too (see can_switch_dashboard_context
# below) — this exact set is also what gifts.services uses to decide
# who can never be registered as a donation recipient, and a Deceased
# Rep's whole purpose is representing their bereaved family, which
# very much includes being able to receive condolence gifts on their
# behalf. Reusing this set for both purposes would have silently
# broken that existing, deliberate, documented behavior.
# 'System settings should provide more option that will restrict or
# give access to the platform admin based on what they can do.' The
# full, recognized set of capabilities a Platform Admin's own account
# can be individually restricted from — checked via
# User.has_platform_admin_capability() and enforced in tenants/views.py.
# Every key here maps to a genuinely distinct, already-existing
# Platform-Admin-only action in this platform, not an invented one.
PLATFORM_ADMIN_CAPABILITIES = {
    "manage_communities": "Create, edit, deactivate, reactivate, or permanently retain a community",
    "manage_access_periods": "Extend or terminate a community's access period",
    "manage_community_admins": "View or add a community's own Community Admin accounts",
    "manage_platform_admins": "View or add other Platform Admin accounts",
    "manage_feature_flags": "Toggle platform-wide feature flags",
}


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

    # 'The system settings should provide more option that will
    # restrict or give access to the platform admin based on what they
    # can do... they manage only the platform admin, not community
    # member.' Only meaningful for role=platform_admin; ignored for
    # every other role. A key absent from this dict means "allowed" —
    # the default is permissive, not restrictive, specifically so an
    # existing Platform Admin never silently loses access the moment
    # this field starts existing on their account. Only an EXPLICIT
    # `False` restricts anything. See accounts.models.PLATFORM_ADMIN_CAPABILITIES
    # for the recognized keys and tenants.services.has_platform_admin_capability
    # for how this is actually checked.
    platform_admin_capabilities = models.JSONField(default=dict, blank=True)

    def has_platform_admin_capability(self, capability: str) -> bool:
        if self.is_superuser:
            return True
        if self.role != Role.PLATFORM_ADMIN:
            return False
        return self.platform_admin_capabilities.get(capability, True)

    # 'The community admin should also have user management and system
    # settings where he can manage all the family head, community
    # executives, community leader, collectors... and have more system
    # options to select what they can do or should see in their
    # dashboard. Same as each family head should also... select he
    # want each of the family executives to have access to, and also
    # select features he want members to have access to.'
    #
    # Deliberately a single, generic list of nav feature keys (the
    # Sidebar's own `href` values) this ACCOUNT is denied, layered on
    # TOP of whatever their role would otherwise grant — not a
    # per-role capability dict like platform_admin_capabilities above,
    # since the same mechanism has to serve a Community Admin
    # restricting any executive role in their community AND a Family
    # Head restricting their family's own officers or members. An
    # empty list (the default) means no restriction at all — every
    # feature their role already grants stays fully available; this
    # can only ever take features AWAY, never grant ones a role
    # doesn't already have. See accounts.permissions.can_restrict_features_for
    # for who is allowed to set this on whom.
    disabled_features = models.JSONField(default=list, blank=True)

    def has_feature(self, href: str) -> bool:
        if self.is_superuser:
            return True
        return href not in (self.disabled_features or [])

    def can_manage_families(self) -> bool:
        return self.is_superuser or self.role in FAMILY_MANAGEMENT_ROLES

    def can_switch_dashboard_context(self) -> bool:
        """
        Only an actual executive, with a personal profile to switch TO,
        has anything to switch between. Bereaved Rep is checked
        separately from EXECUTIVE_ROLES on purpose — that set is also
        what decides who can never receive a donation, and a Deceased
        Rep's whole role is representing their bereaved family, which
        includes being able to receive condolence gifts on their behalf.
        """
        return (self.role in EXECUTIVE_ROLES or self.role == Role.BEREAVED_REP) and bool(getattr(self, "member_profile", None))

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

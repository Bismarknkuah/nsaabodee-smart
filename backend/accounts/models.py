from django.conf import settings
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
    # 'We will have two type of collectors, one collect on going
    # funerals and the other one is arrears collector who collect
    # arrears payment.' A distinct role, not a flag on Collector —
    # community leadership assigns someone specifically to this desk,
    # the same way Family Registration Officer is a distinct role from
    # Family Head rather than a checkbox on it. Shares the exact same
    # community-wide (not desk-scoped) payment authority Collector
    # already has, see funerals.permissions.PAYMENT_COLLECTING_ROLES,
    # since collecting a payment against ANY member's obligation on
    # ANY funeral, closed ones included, is exactly the authority an
    # arrears collector needs and Collector already happened to have.
    # Confirmed by the person: "the arrears collector for the
    # community and the community arrears officer are the same
    # role." The stored value stays arrears_collector, unchanged,
    # since that is already deployed and already has real data and
    # tests depending on it; only the human-readable label changes,
    # to read consistently alongside Family Arrears Officer and Town
    # Elders Arrears Officer below.
    ARREARS_COLLECTOR = "arrears_collector", "Community Arrears Officer"
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
    # 'Each family should also have family arrears officer, and the
    # town elders should also have arrears.' The same "a dedicated
    # role for one specific job" pattern as the Registration Officer
    # trio just above, scoped the same way: a family's own arrears
    # officer only ever collects arrears from members of their OWN
    # family, and a Town Elders arrears officer only ever collects
    # from the Town Elders group, the same scoping already used for
    # Family Registration Officer and Town Registration Officer.
    FAMILY_ARREARS_OFFICER = "family_arrears_officer", "Family Arrears Officer"
    TOWN_ELDERS_ARREARS_OFFICER = "town_elders_arrears_officer", "Town Elders Arrears Officer"
    # 'For visitors level, there should be a collector for collecting guest
    # contribution.' The cashier at the gifts desk — guests' and sympathisers'
    # donations — community-wide. A family's own donation collector is a
    # Collector with an approved "donation" nomination scoped to that family.
    GIFT_COLLECTOR = "gift_collector", "Guest Contribution Collector"
    # 'Add a community welfare manager purposely for the community; each
    # family should have a family welfare manager who works with his family
    # only.' Both run welfare — campaigns and requests — and never touch
    # money (payments are taken by collectors).
    WELFARE_MANAGER = "welfare_manager", "Community Welfare Manager"
    FAMILY_WELFARE_MANAGER = "family_welfare_manager", "Family Welfare Manager"


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


# Every role that is an office rather than membership. Defined by EXCLUSION on purpose: the earlier
# hand-written list quietly omitted every role added after it (the registrars, the welfare managers, the
# guest-contribution collector), which left those executives with no way to switch to their member account.
# Deceased Rep is handled separately (see can_switch_dashboard_context); it is not a donation-ineligible executive.
_NOT_EXECUTIVE = {Role.PLATFORM_ADMIN, Role.COMMUNITY_MEMBER, Role.GUEST, Role.BEREAVED_REP}
EXECUTIVE_ROLES = {r for r in Role if r not in _NOT_EXECUTIVE}


class DashboardContext(models.TextChoices):
    EXECUTIVE = "executive", "Executive"
    PERSONAL = "personal", "Personal"


# ---------------------------------------------------------------------------
# Role consolidation — "merge some of the user role types so each community
# and each family doesn't have so many... the collectors at all levels should
# play the same role as arrears collector... each community 5–6 role types,
# the town elders 3, each family 5."
#
# The legacy values stay in the enum so old records and code paths never
# break; the data migration moves every existing account to its canonical
# role (creating the collector nomination that carries a family or
# Town-Elders scope), and only the canonical set is ever offered anywhere.
# ---------------------------------------------------------------------------
ROLE_CONSOLIDATION = {
    # "Remove the guest user role." A guest login becomes an ordinary community member.
    "guest": ("community_member", None),
    # "No family will have their personal welfare managers" — welfare is created by the Community Welfare Manager only.
    "family_welfare_manager": ("community_member", None),
    # collectors at every level take contributions AND arrears — one role, scoped by nomination
    "arrears_collector": ("collector", None),
    "family_arrears_officer": ("collector", "family"),
    "town_elders_arrears_officer": ("collector", "town_elder"),
    # the community secretary keeps the register and sends the notices
    "notification_officer": ("secretary", None),
    "community_registration_desk": ("secretary", None),
    # one finance officer for the community
    "treasurer": ("financial_secretary", None),
}
# NOT merged: "each ledger should have a registration officer — each family
# will have a family registration officer." The Family Registration Officer
# stays a distinct family role.
LEGACY_ROLES = set(ROLE_CONSOLIDATION)

# The canonical set, by level. Collectors are one role everywhere; a
# collector's LEVEL is the nomination they hold (community, family, or
# Town Elders), shown in their label ("Asona Collector").
# "Each ledger should have a registration officer": the Town Registration
# Officer is the COMMUNITY's registrar (the whole town, town elders included —
# "town elders should not have an elders registration officer because they are
# not many; the community admin and the town registration officer register
# them"), and each family has its own Family Registration Officer.
COMMUNITY_ROLE_TYPES = ["community_admin", "chairman", "secretary", "financial_secretary", "town_registration_officer", "welfare_manager", "collector", "gift_collector"]
# An Auditor only READS the community's finances. It is deliberately not merged into the
# Financial Secretary: that role records expenses and decides their status, so folding an
# auditor into it would silently grant powers the auditor was never meant to have. A seat a
# community may fill, outside the core roster counted above.
OPTIONAL_OVERSIGHT_ROLE_TYPES = ["auditor"]
TOWN_ELDERS_ROLE_TYPES = ["traditional_leader", "town_registration_officer", "collector"]  # the registrar serves the elders level as well as the whole community
FAMILY_ROLE_TYPES = ["family_head", "family_secretary", "family_treasurer", "family_registration_officer", "collector", "bereaved_rep"]
# The Guest role is retired: a person is either a community member or holds an executive role.
# 'Each family executive's role should be isolated, so they can't access or see other families' members.' Every
# role whose reach is one family — used wherever member-level data is listed.
FAMILY_LEVEL_ROLES = {"family_head", "family_secretary", "family_treasurer", "family_registration_officer", "family_arrears_officer", "family_welfare_manager"}

MEMBER_ROLE_TYPES = ["community_member"]
VISIBLE_ROLES = [r for r in Role.values if r not in LEGACY_ROLES]


def canonical_role(role: str) -> str:
    """The role a legacy value now means."""
    return ROLE_CONSOLIDATION.get(role, (role, None))[0]


def member_q(**lookups):
    """
    Query a User by its member, whichever login it is: member_q(family_id=x) == Q(member login's member family) | Q(executive
    login's member family). `member_profile__...` cannot be used in a filter any more because member_profile is a property.
    """
    from django.db.models import Q
    q = Q()
    for accessor in ("_member_login_profile", "_executive_login_profile"):
        q |= Q(**{f"{accessor}__{k}": v for k, v in lookups.items()})
    return q


MEMBER_SELECT_RELATED = ("_member_login_profile__family", "_executive_login_profile__family")


class CustomRole(models.Model):
    """
    'The family secretary can create a new role for his family, same as
    the community admin can create roles for the community.' A custom
    role is a NAME a community or family gives to a job, built on one of
    the canonical roles whose permissions it inherits — "Welfare Officer"
    built on secretary, "Youth Collector" built on collector. Permissions
    always come from the base role; the custom role is what people see.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="custom_roles")
    family = models.ForeignKey("families.Family", null=True, blank=True, on_delete=models.CASCADE, related_name="custom_roles", help_text="Null = a community-level role.")
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    base_role = models.CharField(max_length=40, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["family__name", "name"]
        constraints = [models.UniqueConstraint(fields=["community", "family", "name"], name="uniq_custom_role_name_per_scope")]

    def __str__(self):
        return self.name


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
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.COMMUNITY_MEMBER)
    # A custom-named variant of `role` ("Welfare Officer" built on secretary). Permissions always come from `role`.
    custom_role = models.ForeignKey("accounts.CustomRole", null=True, blank=True, on_delete=models.SET_NULL, related_name="holders")
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

    @property
    def member_profile(self):
        """The Member this login belongs to — the member login (linked_user) or the executive login — else None."""
        for accessor in ("_member_login_profile", "_executive_login_profile"):
            try:
                return getattr(self, accessor)
            except Exception:   # RelatedObjectDoesNotExist
                continue
        return None

    @property
    def real_role(self) -> str:
        """
        The role this ACCOUNT holds. Inside a request made from the community-member account, `role` reads
        as community_member (that is what the request is authorised as); this always reads the account's own.
        """
        return getattr(self, "_real_role", None) or self.role

    def can_switch_dashboard_context(self) -> bool:
        """
        Only an actual executive, with a personal profile to switch TO,
        has anything to switch between. Bereaved Rep is checked
        separately from EXECUTIVE_ROLES on purpose — that set is also
        what decides who can never receive a donation, and a Deceased
        Rep's whole role is representing their bereaved family, which
        includes being able to receive condolence gifts on their behalf.
        """
        # Retired: each person has a separate member login now (Member.linked_user), so there is nothing to switch to.
        return False

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

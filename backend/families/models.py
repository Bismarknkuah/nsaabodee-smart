import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Family(models.Model):
    """
    A family within one Community (tenant).

    A Family is *scoped to its Community* — the same family name
    ("Asona", "Bretuo", ...) can exist independently in many communities
    without collision, and no query ever crosses the community boundary
    because every lookup is filtered by `community` (enforced in the
    ViewSet, not just here).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEACTIVATED = "deactivated", "Deactivated"
        MERGED = "merged", "Merged into another family"
        DELETED = "deleted", "Soft-deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(
        "tenants.Community", on_delete=models.CASCADE, related_name="families"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    family_head = models.ForeignKey(
        "members.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="heads_of_family",
    )

    # Delegated by the family head (or Community Admin) — see
    # families/services.py's assign_family_officer(). Purely a
    # within-family designation used to gate access to this family's own
    # Family Fund (family_funds app); it does NOT change anyone's
    # platform-wide accounts.Role. "Abusuapanin can assign any of his
    # members to use like secretary and finance dashboards" — the
    # assigned member sees the extra dashboard section (see
    # dashboard/services.py) the moment this FK points at them, with no
    # separate login-role change required.
    family_secretary = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="secretary_of_family",
    )
    family_treasurer = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="treasurer_of_family",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    # If this family was merged away, point at the surviving family.
    merged_into = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absorbed_families",
    )

    # --- Own-family contribution rate -----------------------------------
    # This is the amount a member of THIS family pays when a funeral is held
    # for a deceased member of THIS family (as opposed to the community's
    # general rate everyone else pays). The Family Head recommends it; a
    # Community Administrator must approve it before it takes effect on any
    # new funeral. Until approved, `standing_family_rate` stays null and a
    # funeral for this family cannot be created without an explicit
    # one-off amount supplied at creation time (see funerals.services).
    recommended_family_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Proposed by the Family Head; not yet in effect until approved.",
    )
    standing_family_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="The approved, currently-effective own-family contribution amount.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # A given community cannot have two ACTIVE families sharing a name.
            # (Deactivated/merged/deleted duplicates are allowed, e.g. history.)
            models.UniqueConstraint(
                fields=["community", "name"],
                condition=models.Q(status="active"),
                name="unique_active_family_name_per_community",
            )
        ]
        indexes = [
            models.Index(fields=["community", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.community.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def member_count(self):
        return self.members.filter(status="active").count()


class FamilyAuditLog(models.Model):
    """
    Immutable audit trail for every structural change made to a family:
    create, rename, merge, deactivate, reactivate, delete, member transfer,
    family-head assignment. Required by the platform's audit-log requirement
    and essential for undoing/explaining merges later.
    """

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        RENAMED = "renamed", "Renamed"
        MERGED = "merged", "Merged"
        DEACTIVATED = "deactivated", "Deactivated"
        REACTIVATED = "reactivated", "Reactivated"
        DELETED = "deleted", "Deleted"
        HEAD_ASSIGNED = "head_assigned", "Family Head Assigned"
        OFFICER_ASSIGNED = "officer_assigned", "Family Officer (Secretary/Treasurer) Assigned"
        OFFICER_POSITION_APPOINTED = "officer_position_appointed", "Family Executive Position Appointed"
        OFFICER_POSITION_REMOVED = "officer_position_removed", "Family Executive Position Removed"
        MEMBER_TRANSFERRED_IN = "member_transferred_in", "Member Transferred In"
        MEMBER_TRANSFERRED_OUT = "member_transferred_out", "Member Transferred Out"
        RATE_RECOMMENDED = "rate_recommended", "Own-Family Rate Recommended"
        RATE_APPROVED = "rate_approved", "Own-Family Rate Approved"
        RATE_REJECTED = "rate_rejected", "Own-Family Rate Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    family = models.ForeignKey(
        Family, on_delete=models.CASCADE, related_name="audit_logs", null=True
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.family_id} @ {self.created_at:%Y-%m-%d %H:%M}"


# The eight positions the spec names explicitly, offered as suggestions
# in the frontend — "Custom positions allowed" means this is a starting
# point, not an exhaustive enum. The model field itself is free text
# (see FamilyOfficerPosition.title below), the same choice already made
# deliberately for family_secretary/family_treasurer's real-world
# titles rather than forcing every community's own terminology into a
# fixed set that might not fit.
SUGGESTED_FAMILY_OFFICER_TITLES = [
    "Assistant Family Head",
    "Financial Secretary",
    "Organizer",
    "Welfare Officer",
    "Youth Leader",
    "Women's Leader",
    "Communication Officer",
    "Auditor",
]


class FamilyOfficerPosition(models.Model):
    """
    'Family Head can create: Assistant Family Head, Secretary,
    Treasurer, Financial Secretary, Organizer, Welfare Officer, Youth
    Leader, Women's Leader, Communication Officer, Auditor... Custom
    positions allowed.' Secretary and Treasurer already exist as their
    own dedicated fields above (family_secretary, family_treasurer) —
    they carry real functional weight (family fund access) that
    predates this model. Everything else is a genuinely organizational
    appointment: recorded and displayed for real family governance and
    transparency, exactly like Secretary/Treasurer already are, but
    deliberately NOT a new platform-wide accounts.Role or a new
    permission of its own — a Youth Leader gets recognized here, not a
    new login capability. Multiple people can hold the same title
    (co-organizers, for instance) — nothing here assumes exactly one
    holder per title the way the Head/Secretary/Treasurer FKs do.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="officer_positions")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="family_officer_positions")
    title = models.CharField(max_length=100)
    appointed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    appointed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "appointed_at"]

    def __str__(self):
        return f"{self.title} — {self.member.full_name}"

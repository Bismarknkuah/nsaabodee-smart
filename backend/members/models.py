import uuid

from django.conf import settings
from django.db import models


class Member(models.Model):
    """
    A registered resident of a community — the full model, not the stub
    the Family and Funeral modules were originally built against. Every
    member belongs to exactly one family (or none, only ever transiently:
    right after a forced family deletion, pending reassignment by an
    administrator — see families.services.delete_family).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DECEASED = "deceased", "Deceased"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class DefaulterTier(models.TextChoices):
        NONE = "none", "In Good Standing"
        WARNING = "warning", "Warning"
        HIGH_WARNING = "high_warning", "High Warning"
        FLAGGED = "flagged", "Flagged"

    class FamilySeniority(models.TextChoices):
        # Which own-family contribution tier a male member pays when
        # their own family holds a funeral — there's no generation/
        # birth-order data anywhere in this system to derive "uncle" vs
        # "nephew" automatically, so whoever registers this member (their
        # Family Head or Family Secretary) sets it directly. The family
        # head himself is never driven by this field at all — his rate
        # is resolved separately, from Family.family_head, regardless of
        # whatever seniority value happens to be stored here for him.
        SENIOR = "senior", "Senior (uncle-tier)"
        JUNIOR = "junior", "Junior (nephew-tier)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="members")
    family = models.ForeignKey(
        "families.Family", on_delete=models.PROTECT, related_name="members", null=True, blank=True,
        help_text="Every member belongs to at most one family. Null only transiently after a forced family deletion.",
    )

    # A Member (a resident profile) and a User (a login) are different
    # things throughout this platform — most members never need an app
    # account at all. This link is optional and is what makes a personal
    # "My Receipts" dashboard possible for the members who DO have one:
    # without it, a receipt can only be looked up by a collector or
    # administrator, never by the member themselves.
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="member_profile",
    )

    # A short, human-friendly identifier printed on the digital membership
    # card and receipts — NOT the database primary key, which stays a UUID
    # internally. Generated once at registration, never reused.
    membership_number = models.CharField(max_length=32, blank=True)

    full_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    ghana_card_number = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(upload_to="member_photos/", null=True, blank=True)

    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    # --- Defaulter tracking -----------------------------------------------
    # Cached, recomputed whenever a funeral closes (see
    # members.services.evaluate_defaulters_for_closed_funeral). Kept as a
    # stored field rather than calculated on every read because the
    # Defaulters Dashboard needs to filter/sort on it cheaply across an
    # entire community.
    missed_contributions_count = models.PositiveIntegerField(default=0)
    defaulter_tier = models.CharField(max_length=20, choices=DefaulterTier.choices, default=DefaulterTier.NONE)

    family_seniority = models.CharField(
        max_length=10, choices=FamilySeniority.choices, default=FamilySeniority.JUNIOR,
        help_text="Which own-family contribution tier this member pays (male members only; women pay the family's woman rate regardless). Ignored for the family head, whose rate is always the head rate.",
    )
    is_town_leader = models.BooleanField(
        default=False,
        help_text="Chief or elder — pays the community's flat town-leader contribution rate instead of the usual family/general rate, regardless of which family they belong to.",
    )
    defaulter_evaluated_at = models.DateTimeField(null=True, blank=True)

    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(fields=["community", "membership_number"], name="unique_membership_number_per_community"),
            models.UniqueConstraint(
                fields=["community", "ghana_card_number"],
                condition=models.Q(ghana_card_number__isnull=False),
                name="unique_ghana_card_per_community",
            ),
        ]
        indexes = [
            models.Index(fields=["community", "status"]),
            models.Index(fields=["community", "defaulter_tier"]),
            models.Index(fields=["community", "full_name"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.membership_number})"

    def save(self, *args, **kwargs):
        if not self.membership_number:
            self.membership_number = self._generate_membership_number()
        super().save(*args, **kwargs)

    def _generate_membership_number(self) -> str:
        import secrets
        prefix = self.community.slug.upper()[:8]
        for _ in range(5):
            candidate = f"{prefix}-{secrets.randbelow(999999):06d}"
            if not Member.objects.filter(community=self.community, membership_number=candidate).exists():
                return candidate
        raise RuntimeError("Could not generate a unique membership number; please retry.")

    @property
    def qr_payload(self) -> str:
        """
        What the printed QR code on the membership card / receipt
        encodes. A real, scannable URL — not a custom app-only URI
        scheme, which no ordinary phone camera can actually open.
        Lands on this member's profile page; since that page requires
        login, scanning it is genuinely useful for a Collector doing a
        quick lookup at the front desk, not a random passerby.
        """
        from django.conf import settings
        return f"{settings.FRONTEND_BASE_URL}/members/{self.id}"

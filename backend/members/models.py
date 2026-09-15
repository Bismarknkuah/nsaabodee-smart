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

    class FamilyPosition(models.TextChoices):
        """
        The richer family contribution-tier taxonomy this platform's
        own funeral contribution rules now specify — an ADDITIVE
        replacement for the coarser FamilySeniority above, never a
        breaking one: this field is optional, and rate_for() (see
        funerals/models.py) only ever consults it when it's actually
        set, falling back to the original gender/FamilySeniority logic
        otherwise. FAMILY_HEAD is included here for completeness even
        though it's never actually read for rate purposes — Family.family_head
        alone still decides who pays the Head's own rate, exactly as
        before.
        """
        FAMILY_HEAD = "family_head", "Family Head"
        SENIOR_FAMILY_MEMBER = "senior_family_member", "Senior Family Member"
        PARENT_GENERATION = "parent_generation", "Parent Generation"
        UNCLE = "uncle", "Uncle"
        AUNT = "aunt", "Aunt"
        SON = "son", "Son"
        DAUGHTER = "daughter", "Daughter"
        NEPHEW = "nephew", "Nephew"
        NIECE = "niece", "Niece"
        SPOUSE = "spouse", "Spouse"
        IN_LAW = "in_law", "In-Law"
        DEPENDANT = "dependant", "Dependant"
        OTHER = "other", "Other"

    class BiologicalRelationship(models.TextChoices):
        """
        Purely descriptive — the member's actual biological/legal
        relationship within their own family, recorded for clarity and
        to help whoever assigns FamilyPosition above do so accurately
        (a Father or Brother clearly belongs in PARENT_GENERATION or
        SENIOR_FAMILY_MEMBER; a Nephew clearly belongs in NEPHEW) —
        never itself read by rate_for(), which only ever looks at
        FamilyPosition. Keeping the two separate rather than inferring
        one from the other automatically is deliberate: 'if the
        existing system does not have sufficient information to
        determine the category reliably, provide an authorized
        classification/verification mechanism rather than silently
        guessing' — a person's real relationship and which
        CONTRIBUTION TIER it maps to are still two different human
        judgment calls, not one the software should collapse silently.
        """
        FATHER = "father", "Father"
        MOTHER = "mother", "Mother"
        SON = "son", "Son"
        DAUGHTER = "daughter", "Daughter"
        BROTHER = "brother", "Brother"
        SISTER = "sister", "Sister"
        GRANDFATHER = "grandfather", "Grandfather"
        GRANDMOTHER = "grandmother", "Grandmother"
        UNCLE = "uncle", "Uncle"
        AUNT = "aunt", "Aunt"
        NEPHEW = "nephew", "Nephew"
        NIECE = "niece", "Niece"
        COUSIN = "cousin", "Cousin"
        SPOUSE = "spouse", "Spouse"
        PARENT_IN_LAW = "parent_in_law", "Parent-in-law"
        SIBLING_IN_LAW = "sibling_in_law", "Sibling-in-law"
        OTHER = "other", "Other"

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
    # 'Once a community member gets to 20 years and he's not schooling
    # or an apprentice he has to mandatory pay for contribution...
    # note that even if the person is a student or an apprentice and
    # more than 25 years should still have to pay.' A structured,
    # explicit flag rather than parsing the free-text `occupation`
    # field above — matching this platform's own "don't silently
    # guess" principle. See
    # contribution_rules.services.is_contribution_eligible_by_age for
    # exactly how this and date_of_birth combine into the actual rule.
    occupation_status = models.CharField(
        max_length=20,
        choices=[("none", "None"), ("student", "Student"), ("apprentice", "Apprentice")],
        default="none",
    )
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    ghana_card_number = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(upload_to="member_photos/", null=True, blank=True)

    # 'The registration form should be redesigned to ask more
    # information about the person, mother, father, background.'
    # Free text throughout — a mother or father's name here is
    # background information for the record, not a lookup against
    # another Member (they're very often not registered in this
    # system themselves), and hometown is the person's own ancestral
    # origin, distinct from `address` above (their current residence).
    mother_name = models.CharField(max_length=255, blank=True)
    father_name = models.CharField(max_length=255, blank=True)
    hometown = models.CharField(max_length=255, blank=True)

    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "Single"
        MARRIED = "married", "Married"
        DIVORCED = "divorced", "Divorced"
        WIDOWED = "widowed", "Widowed"

    marital_status = models.CharField(max_length=20, choices=MaritalStatus.choices, blank=True)
    # Free text, same reasoning as mother_name/father_name above — a
    # spouse is very often not a registered Member themselves, and
    # even when they are, this platform's own In-Law Contribution
    # workflow (funerals.services.request_in_law_contribution) already
    # works at the FAMILY level, not by resolving this name to a
    # specific Member record.
    spouse_name = models.CharField(max_length=255, blank=True)

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
    # Optional and additive — when set, takes priority over the
    # gender/family_seniority logic above in rate_for(); when left
    # unset (the default for every existing member), behavior is
    # completely unchanged. See FamilyPosition's own docstring.
    family_position = models.CharField(max_length=30, choices=FamilyPosition.choices, null=True, blank=True)
    # Purely descriptive — never read by rate_for() at all. See
    # BiologicalRelationship's own docstring for why this is kept
    # separate from family_position rather than driving it automatically.
    biological_relationship = models.CharField(max_length=30, choices=BiologicalRelationship.choices, blank=True)
    is_town_leader = models.BooleanField(
        default=False,
        help_text="Chief or elder — pays the community's flat town-leader contribution rate instead of the usual family/general rate, regardless of which family they belong to.",
    )

    class TownElderTitle(models.TextChoices):
        CHIEF = "chief", "Chief"
        QUEEN_MOTHER = "queen_mother", "Queen Mother"
        LINGUIST = "linguist", "Linguist"
        OTHER = "other", "Other Town Executive"

    # 'They should also be registered as town elders which consist of
    # the chief, queen mother, linguist, and other town executive.'
    # Only meaningful when is_town_leader is True — the boolean itself
    # still governs which contribution rate applies (rate_for() in
    # funerals/models.py), unchanged; this just records WHICH kind of
    # elder they are.
    town_elder_title = models.CharField(max_length=20, choices=TownElderTitle.choices, null=True, blank=True)
    # 'Town elder contribution can also be individual... Elder A -> GHS
    # X, Elder B -> GHS Y. This is important because traditional elders
    # may not all contribute the same amount even when they have
    # similar positions.' Takes absolute priority over both the
    # per-title and flat rates when set — see FuneralEvent.rate_for.
    # A standing, community-wide figure for this specific person
    # (not scoped to one funeral) since an individual elder's own
    # contribution level doesn't reset between funerals the way a
    # family member's role within a family might.
    town_elder_individual_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

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


class MemberWallet(models.Model):
    """
    'If he doesn't get change, money balance should be credited to the
    member's wallet.' A real, reusable credit balance — separate from
    ContributionObligation.overpaid_amount (which only ever describes
    one specific obligation's own excess) precisely because a wallet
    credit needs to survive past that one obligation and be usable
    against a genuinely different, future one. One row per member,
    created on first use rather than for every member up front.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.member.full_name}'s wallet — {self.balance}"


class WalletTransaction(models.Model):
    """
    A full, auditable ledger of every deposit (an overpayment with no
    change given) and withdrawal (applied toward a real obligation) —
    'balance' alone is never enough of a record for real money moving
    in and out of an account, the same reasoning behind every other
    ledger on this platform.
    """
    class Kind(models.TextChoices):
        CREDIT = "credit", "Credit (overpayment, no change given)"
        DEBIT = "debit", "Debit (applied to an obligation)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(MemberWallet, on_delete=models.CASCADE, related_name="transactions")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount} — {self.wallet.member.full_name}"


class CollectorNomination(models.Model):
    """
    'The collectors should be in 4 categories... for transparency, when
    one creates an account he needs other executives to approve it
    before that account can start collecting money.'

    A nomination is pending, not yet a real Collector, until enough of
    the RIGHT people (which varies by category — see
    members.services.COLLECTOR_APPROVAL_RULES) have confirmed it. The
    member's own role only actually becomes "collector" (see
    members.services.approve_collector_nomination) once approved — an
    account with a pending nomination can never collect a single cedi
    in the meantime.
    """

    class CollectorType(models.TextChoices):
        GENERAL = "general", "General Collector (community ledger)"
        FAMILY = "family", "Family Collector (family ledger)"
        DONATION = "donation", "Donation Collector (gift ledger)"
        TOWN_ELDER = "town_elder", "Town Elders Collector"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="collector_nominations")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="collector_nominations")
    collector_type = models.CharField(max_length=20, choices=CollectorType.choices)

    # Only ever set for FAMILY and DONATION nominations — a General or
    # Town Elder collector isn't scoped to any one family at all.
    scoped_family = models.ForeignKey("families.Family", null=True, blank=True, on_delete=models.CASCADE, related_name="+")

    nominated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_collector_type_display()} nomination for {self.member.full_name} ({self.status})"


class CollectorApproval(models.Model):
    """One executive's own confirmation (or rejection) of a single CollectorNomination — the record of WHO actually signed off, not just a count."""

    class Decision(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nomination = models.ForeignKey(CollectorNomination, on_delete=models.CASCADE, related_name="approvals")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    decision = models.CharField(max_length=10, choices=Decision.choices)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["decided_at"]
        constraints = [
            models.UniqueConstraint(fields=["nomination", "decided_by"], name="one_decision_per_approver_per_nomination"),
        ]

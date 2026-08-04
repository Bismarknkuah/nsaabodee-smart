import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class FuneralEvent(models.Model):
    """
    A single funeral. The platform supports many of these open for the
    same community at the same time — there is deliberately no uniqueness
    constraint limiting a community to one active funeral. A busy season
    can have four, five, or more running concurrently, each with its own
    independent contribution ledger.
    """

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="funerals")

    deceased_name = models.CharField(max_length=255)
    deceased_gender = models.CharField(max_length=10, choices=Gender.choices)
    deceased_family = models.ForeignKey(
        "families.Family", on_delete=models.PROTECT, related_name="funerals",
        help_text="Members of this family pay the own-family rate; everyone else pays the general rate.",
    )

    date_of_death = models.DateField()
    deceased_date_of_birth = models.DateField(
        null=True, blank=True,
        help_text="The deceased's own date of birth — shown on receipts instead of date of death.",
    )
    burial_date = models.DateField(null=True, blank=True)
    funeral_date = models.DateField(null=True, blank=True)
    collection_start_date = models.DateField()
    collection_end_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    # Rates are SNAPSHOTTED onto the funeral at creation time. If a family's
    # standing_family_rate or the community's default general rates change
    # later, past and currently-open funerals are completely unaffected —
    # only a new funeral created afterwards will pick up the new numbers.
    own_family_amount = models.DecimalField(max_digits=10, decimal_places=2)
    general_male_amount = models.DecimalField(max_digits=10, decimal_places=2)
    general_female_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # The tiered rates within the deceased's OWN family — "family heads
    # pay 200, uncle pays 100, nephew pays 50, women pay 40" — plus the
    # flat town-leader rate, which cuts across the family/community
    # split entirely. own_family_amount above is kept for backward
    # compatibility (existing receipts/reports/PDFs read it as general
    # context on "this family's standing rate") but no longer drives
    # what an individual family member actually owes — these five fields
    # do that now, resolved per-member by rate_for() below.
    family_head_amount = models.DecimalField(max_digits=10, decimal_places=2, default=200)
    family_senior_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    family_junior_amount = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    family_woman_amount = models.DecimalField(max_digits=10, decimal_places=2, default=40)
    town_leader_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_of_death"]
        indexes = [models.Index(fields=["community", "status"])]

    def __str__(self):
        return f"Funeral of {self.deceased_name} ({self.community.name})"

    def rate_for(self, member) -> tuple[str, "models.DecimalField"]:
        """
        Returns (rate_type, amount) for the given member under this
        funeral — resolved in priority order:

          1. Town leader (chief/elder) — their own flat rate, regardless
             of which family they belong to. Still counted as "general"
             for ledger-reporting purposes (it's still money the wider
             community contributes, just at a different amount), never
             "own_family" — a town leader isn't paying a family levy.
          2. The deceased's own family head — the head's own rate.
          3. Any other member of the deceased's own family — tiered by
             gender and seniority: women pay the family's woman rate;
             men pay the senior ("uncle") or junior ("nephew") rate
             depending on their own recorded seniority.
          4. Everyone else — the ordinary general rate, by gender,
             exactly as before.
        """
        if member.is_town_leader:
            return "general", self.town_leader_amount

        if member.family_id == self.deceased_family_id:
            if self.deceased_family.family_head_id == member.id:
                return "own_family", self.family_head_amount
            if member.gender == self.Gender.FEMALE:
                return "own_family", self.family_woman_amount
            if member.family_seniority == member.FamilySeniority.SENIOR:
                return "own_family", self.family_senior_amount
            return "own_family", self.family_junior_amount

        if member.gender == self.Gender.MALE:
            return "general", self.general_male_amount
        return "general", self.general_female_amount

    @property
    def qr_payload(self) -> str:
        """
        'The community admin should be able to generate a barcode so
        that it can be printed and pasted for guests to use to donate
        their gift or contribute... once you scan it should take you
        to what the barcode was meant for.' A real, scannable URL —
        the same public Memorial Page that already needs no login,
        which shows the community's payout account details and a
        tribute form. Any ordinary phone camera can open this directly.
        """
        from django.conf import settings
        return f"{settings.FRONTEND_BASE_URL}/memorial/{self.id}"


class FuneralApproval(models.Model):
    """
    'Is the family head who will open the ledger when there's a
    funeral... once ledger is opened the community secretary, chairman,
    or admin — two of them — have to approve the request before every
    member is billed.' One row per person who has signed off on a
    funeral still in PENDING_APPROVAL — the unique constraint means the
    same person approving twice is a no-op, not a double-count, so "two"
    genuinely means two DISTINCT people, never one person clicking twice.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funeral_event = models.ForeignKey(FuneralEvent, on_delete=models.CASCADE, related_name="approvals")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["funeral_event", "approved_by"], name="one_approval_per_person_per_funeral")]
        ordering = ["approved_at"]

    def __str__(self):
        return f"{self.approved_by} approved {self.funeral_event}"


class MemorialPage(models.Model):
    """
    'A dignified public page for the funeral, event details, donor
    tributes, and a lasting place to remember your loved one.' The one
    genuinely PUBLIC page in this whole platform — no login required to
    view it, specifically so friends and family who aren't registered
    members can still see it and leave a tribute. Deliberately never
    shows individual donor names/amounts or any ledger breakdown, even
    if `show_contribution_total` is on — that's an aggregate figure the
    family opts into sharing, not a window into the private ledgers
    every other part of this platform already protects carefully.

    Explicitly opt-in per funeral (not auto-created for every one) —
    not every family wants a public page, so this only exists once the
    family or a community admin actually creates it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funeral_event = models.OneToOneField(FuneralEvent, on_delete=models.CASCADE, related_name="memorial_page")
    tribute_message = models.TextField(blank=True)
    photo = models.ImageField(upload_to="memorial_photos/", null=True, blank=True)
    show_contribution_total = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Memorial page for {self.funeral_event.deceased_name}"


class MemorialTribute(models.Model):
    """
    A message left by anyone — no login required to submit one, the
    same as viewing the page itself. Moderated before it shows publicly
    (`is_approved`, defaulting False): a fully open, unmoderated public
    text box tied to a real person's memory is exactly the kind of
    surface that needs a real safeguard against spam or something
    inappropriate landing on a grieving family's page, not an honor
    -system assumption that nobody ever will.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    memorial_page = models.ForeignKey(MemorialPage, on_delete=models.CASCADE, related_name="tributes")
    author_name = models.CharField(max_length=255)
    message = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Tribute from {self.author_name} on {self.memorial_page}"


class PaymentReversal(models.Model):
    """
    'If a payment is mistakenly recorded against the wrong member, wrong
    funeral event, wrong family, or incorrect amount, an authorized
    administrator should be able to initiate a reversal or correction...
    Every reversal must be logged with the reason, the user who
    performed it, the original transaction reference, the date, and the
    approval history.'

    Deliberately follows the SAME two-person safeguard this platform
    already uses before a funeral even opens for billing (request, then
    a DIFFERENT authorized person approves) — reversing a real payment
    is exactly the kind of action that shouldn't rest on one person's
    say-so. The original ContributionPayment row is never deleted or
    mutated by this — the audit trail stays whole; only the
    obligation's running total is corrected once a reversal is
    genuinely approved, and only then.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey("ContributionPayment", on_delete=models.PROTECT, related_name="reversal_requests")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True)
    decision_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Reversal request for {self.payment.receipt_number} ({self.status})"


class FuneralDeskAssignment(models.Model):
    """
    'Head of the family should be able to add one or more users and
    assign them, some who could be a member or not, to be on the
    funeral desk... some for [contributions], some for funeral gifts...
    the community chairman or secretary should be able to assign some
    people on the funeral desk [too].' Capability-based, not role-based
    on purpose: the whole reason this exists is to hand real, working
    desk access to someone whose PLATFORM role is otherwise nothing
    special (an ordinary Community Member, or someone with no Member
    profile at all) — for exactly one funeral, and only for the
    ledger(s) they were actually assigned to. See
    funerals.permissions.is_desk_worker_for, which every payment- and
    gift-recording endpoint checks alongside its normal role gates.
    """

    class DeskType(models.TextChoices):
        # 'The community chairman or secretary can open two or more
        # community ledger payment desks... a separate desk for the
        # community elders... one or more guest payment desks... the
        # abusuapanin/head and secretary of the deceased family can also
        # create family desks.' Multiple desks of the SAME purpose are
        # already supported naturally — this is just a label per
        # assignment, and any number of different people can each hold
        # the same one for a single funeral.
        COMMUNITY = "community", "Community Ledger Desk"
        ELDERS = "elders", "Town Elders Desk"
        GUEST = "guest", "Guest Desk"
        FAMILY = "family", "Family Desk"

    # What each desk purpose actually grants — see
    # funerals.permissions.is_desk_worker_for, which every payment- and
    # gift-recording endpoint checks. A desk's PURPOSE label is mostly
    # organizational clarity (who's meant to queue at which table); what
    # actually gates real permission is whether that purpose grants
    # contribution-recording, gift-recording, or (for the Elders desk,
    # since an elder might pay their own flat mandatory rate AND give an
    # extra voluntary gift at the same table) both.
    CONTRIBUTION_DESK_TYPES = {"community", "elders", "family"}
    # "Can assign someone to receive family contribution and donating
    # of gifts to deceased family members" — a Family desk covers BOTH,
    # since gifts given to a bereaved family are specifically theirs to
    # receive, the same way an Elder's own flat rate and a voluntary
    # gift both land at the Elders desk.
    GIFT_DESK_TYPES = {"elders", "guest", "family"}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funeral_event = models.ForeignKey(FuneralEvent, on_delete=models.CASCADE, related_name="desk_assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    desk_type = models.CharField(max_length=20, choices=DeskType.choices)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    # 'Only the abusuapanin of each family can assign someone as a
    # front desk officer or collector and it has to be approved by the
    # community admin or temporary admin.' Community/Elders/Guest desks
    # (opened by community-wide leadership itself) are real the moment
    # they're created — that authority already IS the approval. A
    # Family desk assignment is different: the Family Head who opens
    # it is a different person from the Community Admin who must
    # approve it, so it starts inactive — a real pending request, not
    # yet real desk access — until approved (see
    # funerals.services.approve_desk_assignment).
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["funeral_event", "user"], name="one_desk_assignment_per_user_per_funeral")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.desk_type} desk for {self.funeral_event}"


class FuneralMemberRateOverride(models.Model):
    """
    'The family head and secretary of the deceased family can set an
    amount for each member [of their own family] have to pay.' The
    community's tiered rates (head/uncle/nephew/woman) are a sensible
    DEFAULT — this is how the deceased's own family leadership overrides
    it per person, for THIS funeral only, without touching the
    community-wide defaults everyone else's funerals still use.

    Deliberately its own table rather than a field bolted onto
    ContributionObligation: overrides only ever apply while a funeral is
    still PENDING_APPROVAL (see generate_obligations, which is the only
    place these get read) — obligations themselves don't exist yet at
    that point, so there's nothing on ContributionObligation to attach
    an override to until the funeral actually activates.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funeral_event = models.ForeignKey(FuneralEvent, on_delete=models.CASCADE, related_name="member_rate_overrides")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="+")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["funeral_event", "member"], name="one_rate_override_per_member_per_funeral")]

    def __str__(self):
        return f"{self.member.full_name} pays {self.amount} for {self.funeral_event}"


class ContributionObligation(models.Model):
    """
    Ledger 1 — Mandatory Nsaabodeɛ Contributions.

    One row per (member, funeral). Every active member of the community is
    automatically enrolled here the moment a funeral is created — nobody
    signs up, nobody can be left out by accident. `expected_amount` is a
    snapshot, not a live computation, so a later change to a family's rate
    never silently rewrites what someone already owed on a funeral that's
    already open.
    """

    class RateType(models.TextChoices):
        OWN_FAMILY = "own_family", "Own Family Rate"
        GENERAL = "general", "General Rate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    funeral_event = models.ForeignKey(FuneralEvent, on_delete=models.CASCADE, related_name="obligations")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="contribution_obligations")

    rate_type = models.CharField(max_length=20, choices=RateType.choices)
    expected_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["funeral_event", "member"], name="one_obligation_per_member_per_funeral")
        ]
        indexes = [
            models.Index(fields=["community", "funeral_event", "rate_type"]),
            models.Index(fields=["member"]),
        ]

    def __str__(self):
        return f"{self.member.full_name} owes {self.expected_amount} for {self.funeral_event.deceased_name}"

    @property
    def balance(self):
        """
        Never negative: `expected_amount` is a required minimum now, not
        a ceiling (see funerals.services.record_payment), so someone
        paying more than required shows a balance of zero owed, not a
        confusing negative number — the excess is reported separately
        via `overpaid_amount`.
        """
        return max(self.expected_amount - self.amount_paid, Decimal("0"))

    @property
    def overpaid_amount(self):
        return max(self.amount_paid - self.expected_amount, Decimal("0"))

    @property
    def payment_status(self):
        if self.amount_paid <= 0:
            return "unpaid"
        if self.amount_paid < self.expected_amount:
            return "partial"
        return "paid"


class ContributionPayment(models.Model):
    """
    An individual payment against one ContributionObligation. A member can
    pay in more than one instalment if partial payments are enabled for the
    community — each instalment is its own row here so receipts and the
    audit trail are never lossy, while `ContributionObligation.amount_paid`
    stays a fast running total for dashboards and defaulter checks.
    """

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK = "bank", "Bank"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obligation = models.ForeignKey(ContributionObligation, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices)
    receipt_number = models.CharField(max_length=50, unique=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Idempotency key from the collecting device, so a payment recorded
    # offline and retried after a dropped sync can never be double-counted.
    client_op_id = models.UUIDField(unique=True, null=True, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    # Set the moment a physical thermal-printer receipt actually finishes
    # printing (see reports.services.mark_contribution_receipt_printed).
    # Every cash payment gets a receipt_number the instant it's recorded —
    # that's the electronic receipt, and it's guaranteed already. This
    # field is what closes the loop on the PHYSICAL half: "did the payer
    # actually walk away with a printed slip," which a jammed printer or
    # a dead phone battery can otherwise leave silently unresolved. See
    # reports.services.unprinted_receipts for the dashboard this powers.
    printed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-paid_at"]
        indexes = [models.Index(fields=["paid_at"])]

    def __str__(self):
        return f"{self.amount} via {self.method} — receipt {self.receipt_number}"


# The twelve positions the spec names explicitly, offered as
# suggestions in the frontend — "custom positions allowed" here too,
# the same choice already made for FamilyOfficerPosition rather than
# forcing every community's own funeral-organizing terminology into a
# fixed set that might not fit.
SUGGESTED_FUNERAL_COMMITTEE_TITLES = [
    "Chairman", "Vice Chairman", "Secretary", "Treasurer", "Financial Secretary",
    "Welfare Officer", "Logistics Coordinator", "Public Relations Officer",
    "Protocol Officer", "Security Coordinator",
]


class FuneralCommitteePosition(models.Model):
    """
    'Every funeral creates a committee workspace... Chairman, Vice
    Chairman, Secretary, Treasurer, Welfare Officer, Logistics
    Officer, Food Coordinator, Transport Coordinator, Accommodation
    Coordinator, Protocol Officer, Security Officer, PR Officer.'

    Deliberately separate from FuneralDeskAssignment above, which
    grants real, working payment/gift-recording AUTHORITY for a
    specific desk. This is pure organizational record-keeping — the
    same "recognized, not granted a new login capability" principle
    already used for FamilyOfficerPosition: a funeral's Logistics
    Officer is recorded and displayed here, but if they also need to
    actually collect money, that's still its own, separate desk
    assignment. Free-text `title`, not a rigid enum, for the same
    reason — "custom positions allowed" needs to mean something real.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funeral_event = models.ForeignKey(FuneralEvent, on_delete=models.CASCADE, related_name="committee_positions")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="funeral_committee_positions")
    title = models.CharField(max_length=100)
    appointed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    appointed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "appointed_at"]

    def __str__(self):
        return f"{self.title} — {self.member.full_name} ({self.funeral_event.deceased_name}'s funeral)"

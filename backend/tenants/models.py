import uuid

from django.conf import settings
from django.db import models


class Community(models.Model):
    """
    A tenant. Every piece of data in the platform (families, members,
    funerals, contributions, ...) is scoped to exactly one Community.
    This is the root of data isolation between communities.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    region = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # "Configure branding (logo, colors, community information)" — a
    # Community Admin's own workspace, without needing the Platform
    # Admin for a routine, cosmetic change. Purely presentational:
    # never used by any permission check, and the hex colors are
    # validated as genuine hex codes so a typo here can't break the
    # frontend's own styling.
    logo = models.ImageField(upload_to="community_logos/", null=True, blank=True)
    primary_color = models.CharField(max_length=7, blank=True, help_text="Hex color, e.g. #2F5233")
    secondary_color = models.CharField(max_length=7, blank=True, help_text="Hex color, e.g. #B8860B")
    tagline = models.CharField(max_length=255, blank=True)

    # "Configure approval workflows" — how many distinct community
    # leaders must approve before a requested funeral opening actually
    # goes live. Was a hardcoded constant (always 2); now each
    # community's own Admin decides this for their own workspace.
    required_funeral_approvals = models.PositiveSmallIntegerField(default=2)

    class AccessPlan(models.TextChoices):
        ONGOING = "ongoing", "Ongoing (permanent)"
        SINGLE_FUNERAL = "single_funeral", "Single Funeral (temporary)"
        TIME_LIMITED = "time_limited", "Time-Limited (temporary)"

    # "Some people can also decide to rent or use the service
    # temporarily." Null means permanent, ongoing access — the default,
    # and the ONLY behavior every community created before this existed
    # ever had, so nothing already running is affected by adding this.
    # A real value here is a real, enforced deadline: checked on every
    # authenticated request (see accounts.authentication), not just at
    # login — an already-issued token doesn't get a free pass past
    # expiration just because it was issued before the clock ran out.
    access_plan = models.CharField(max_length=20, choices=AccessPlan.choices, default=AccessPlan.ONGOING)
    access_expires_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_access_expired(self) -> bool:
        if self.access_expires_at is None:
            return False
        from django.utils import timezone
        return timezone.now() >= self.access_expires_at

    @property
    def access_days_remaining(self):
        if self.access_expires_at is None:
            return None
        from django.utils import timezone
        delta = self.access_expires_at - timezone.now()
        return max(0, delta.days)

    @property
    def is_temporary_event(self) -> bool:
        """
        'Individuals or organizations renting the platform for temporary
        use' — a Single Funeral or Time-Limited community, as opposed to
        an ordinary, ongoing one. This is the boundary the gift-donor
        privacy rule keys off: a temporary renter's own Community Admin
        doesn't get the same standing default access to donor PII that
        an established, permanent community's own admin has.
        """
        return self.access_plan != Community.AccessPlan.ONGOING

    # --- General (non-own-family) contribution defaults ------------------
    # Whenever a funeral is held, every member NOT in the deceased's family
    # pays this "general" amount, based on gender, unless the funeral
    # explicitly overrides it. This is the community-wide default; each
    # funeral event snapshots its own copy so changing these later never
    # rewrites the amount someone already owed on a past funeral.
    default_general_male_amount = models.DecimalField(max_digits=10, decimal_places=2, default=5)
    default_general_female_amount = models.DecimalField(max_digits=10, decimal_places=2, default=3)

    # "Family heads pay 200, uncle pays 100, nephew pays 50, women pay
    # 40... town leaders pay about 100 cedis each" — every one of these
    # is a real, per-community-configurable default (the Secretary can
    # adjust them the same way the general rates above are already
    # adjustable), applied ONLY to the deceased's OWN family (everyone
    # else still pays the general rate above) except for town leaders,
    # who pay their own flat rate regardless of which family they're in.
    default_family_head_amount = models.DecimalField(max_digits=10, decimal_places=2, default=200)
    default_family_senior_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)  # "uncle" tier
    default_family_junior_amount = models.DecimalField(max_digits=10, decimal_places=2, default=50)  # "nephew" tier
    default_family_woman_amount = models.DecimalField(max_digits=10, decimal_places=2, default=40)
    default_town_leader_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CommunityPayoutAccount(models.Model):
    """
    'Each registered community should have its own dedicated payment
    account(s)... configured by the Community Administrator... The
    platform must never mix funds between different communities.'

    HONEST SCOPE, stated plainly rather than glossed over: this is the
    real, correct RECORD of where a community's funds should be
    directed — it is NOT an automated fund-disbursement system.
    Actually moving real money into this account programmatically
    would require a genuine disbursement partnership with MTN MoMo or a
    bank (a different, much bigger relationship than the Collections
    API this platform already uses to receive a member's payment) —
    that doesn't exist here, and building code that pretends to move
    real money without one would be actively dishonest, not just
    incomplete. What this model DOES do, correctly: designate the
    destination, and let every report and every payment record
    correctly attribute funds to the right community's own account,
    never a shared or mixed pool.
    """

    class AccountType(models.TextChoices):
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK = "bank", "Bank Account"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="payout_accounts")
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    provider_name = models.CharField(max_length=100, help_text="e.g. MTN Mobile Money, Vodafone Cash, or the bank's name")
    account_number = models.CharField(max_length=50)
    account_holder_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self):
        return f"{self.get_account_type_display()} ({self.account_number}) for {self.community.name}"


class PlatformBillingRecord(models.Model):
    """
    'The system must clearly separate platform service fees from
    community funds. Subscription payments belong to the platform,
    while funeral contributions and donations always belong to the
    respective community or bereaved family. Under no circumstances
    should the platform mix or hold community funds.'

    This model exists ONLY to track what a community owes Nsaabodeɛ
    Smart itself for using the platform — a rental fee for temporary
    access, a subscription installment, a setup fee. It is completely
    separate from, and never aggregated with, that same community's own
    ContributionPayment/GiftDonation records, which stay entirely the
    community's own money and are never touched by anything here.

    Same honest boundary already drawn for CommunityPayoutAccount: no
    automated payment processing happens through this model. A platform
    admin marks a record paid once payment has genuinely been received
    through some real channel — a bank transfer, MoMo to the
    PLATFORM'S OWN account (never a community's), or cash. This is a
    record of a real-world financial fact the platform operator
    confirms, not a payment gateway pretending to move money it never
    actually touched.
    """

    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="platform_billing_records")
    description = models.CharField(max_length=255, help_text="e.g. '5-day Single Funeral access' or 'Monthly subscription — July 2026'")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    marked_paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    marked_paid_at = models.DateTimeField(null=True)
    payment_reference = models.CharField(max_length=255, blank=True, help_text="A bank transfer reference, MoMo transaction ID, or similar — for the platform's own records only.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.description} — GHS {self.amount} ({self.status}) for {self.community.name}"


class HomepageImage(models.Model):
    """
    'The homepage live pictures which will be changing should be
    uploaded by the super admin.' Platform-level content — not tied to
    any single community — shown on the public homepage's hero, which
    previously depended on an external stock-photo hotlink that broke
    in real use. This replaces that with real, admin-controlled images
    stored on the platform's own server.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ImageField(upload_to="homepage_images/")
    caption = models.CharField(max_length=100, blank=True, help_text="e.g. 'Supporting Families'")
    subcaption = models.CharField(max_length=150, blank=True, help_text="e.g. 'Cash · MoMo · Bank · Instant Record'")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "-created_at"]

    def __str__(self):
        return self.caption or f"Homepage image {self.id}"


class PlanInterestSubmission(models.Model):
    """
    'Make sure all coming soon are completely designed' — the pricing
    plans (Single Funeral, Community, Multi-Community) aren't real,
    payable products yet, so a disabled button was honest but a dead
    end. This turns "Coming soon" into a genuine, actionable thing:
    real lead capture the platform admin can actually follow up on,
    not a decoration pretending a checkout exists that doesn't.
    """

    class PlanType(models.TextChoices):
        SINGLE_FUNERAL = "single_funeral", "Single Funeral"
        COMMUNITY = "community", "Community"
        MULTI_COMMUNITY = "multi_community", "Multi-Community"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_type = models.CharField(max_length=20, choices=PlanType.choices)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    contacted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.get_plan_type_display()}"


class Announcement(models.Model):
    """
    'Any community who wants to post announcement on the notice board...
    has to be submitted by the community admin and the super admin has
    to approve it before... and the super admin can edit the content or
    reject it with reasons for the community admin to edit and resend
    again.' A shared, platform-wide notice board — Super Admin curates
    what's visible across every community, which is why this is a
    platform-level approval, not something a community's own leadership
    decides for itself.

    HONEST SCOPE on 'pictures or videos can be attached': a real image
    upload is genuinely supported. A real, hosted VIDEO FILE upload
    (storage, encoding, streaming) is a materially different and much
    larger undertaking than an image — what's supported instead is a
    video LINK (YouTube, Vimeo, or similar), which is the same practical
    outcome (a video attached to the announcement) without pretending
    to have built video hosting infrastructure that doesn't exist here.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=255)
    content = models.TextField()
    image = models.ImageField(upload_to="announcement_images/", null=True, blank=True)
    video_url = models.URLField(blank=True, help_text="A link to a hosted video (YouTube, Vimeo, or similar) — not a raw file upload.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True)
    rejection_reason = models.TextField(blank=True)
    was_edited_by_reviewer = models.BooleanField(default=False)

    # "When it needs it on the homepage he has to send a request to the
    # platform admin." Separate from ordinary Notice Board approval — a
    # Community Admin can ask for wider, PUBLIC placement, but a
    # Platform Admin decides whether to actually grant it, independent
    # of whether the announcement itself gets approved for the (already
    # authenticated-only) Notice Board.
    homepage_feature_requested = models.BooleanField(default=False)
    featured_on_homepage = models.BooleanField(default=False)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.title} ({self.status}) — {self.community.name}"


class AnnouncementReviewLog(models.Model):
    """
    'A complete audit trail' for the same reason every other approval
    workflow in this platform keeps one — who submitted, who reviewed,
    what was decided, and why, permanently, even across multiple
    reject-edit-resubmit cycles the Announcement record itself only
    ever shows the CURRENT state of.
    """

    class Action(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        EDITED_AND_APPROVED = "edited_and_approved", "Edited and Approved"
        REJECTED = "rejected", "Rejected"
        RESUBMITTED = "resubmitted", "Resubmitted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="review_log")
    action = models.CharField(max_length=30, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.announcement.title}"


class FeatureFlag(models.Model):
    """
    'Manage feature flags' — a genuine kill-switch a Platform Admin can
    flip without a deploy, not an unused toy: `key` is checked by the
    real features it names (see chatbot's AskChatbotView and
    messaging's channel views) before doing anything, so disabling a
    flag here actually disables that feature platform-wide, immediately.
    """
    key = models.SlugField(unique=True, max_length=100)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.name} ({'on' if self.is_enabled else 'off'})"

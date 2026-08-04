"""
Self-service tenant onboarding — "the system should be scalable to be
able to simply add a new or more communities." Everything else in this
platform already assumes a Community exists (every model carries a
community FK); the one genuine gap was that creating the FIRST one for
a brand-new community had no path except direct database/admin access.
This closes that gap: one call creates a new, fully isolated Community
plus its first Community Admin login, ready to use immediately.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from .models import Announcement, AnnouncementReviewLog, Community, CommunityPayoutAccount, FeatureFlag, HomepageImage, PlanInterestSubmission, PlatformBillingRecord


@transaction.atomic
def onboard_new_community(
    *, community_name: str, admin_username: str, admin_password: str, admin_email: str = "",
    region: str = "", default_general_male_amount: Decimal = Decimal("5"),
    default_general_female_amount: Decimal = Decimal("3"), actor=None,
) -> tuple[Community, "get_user_model"]:
    """
    Creates a brand-new, fully isolated Community and its first
    Community Admin account atomically — either both are created, or
    neither is (a community with no way to log into it, or a stray
    orphaned admin account with no community, would both be broken
    half-states this platform should never produce).
    """
    from accounts.models import Role

    community_name = community_name.strip()
    if not community_name:
        raise ValidationError("Community name is required.")

    User = get_user_model()
    if User.objects.filter(username=admin_username).exists():
        raise ValidationError(f"The username '{admin_username}' is already taken.")

    base_slug = slugify(community_name) or "community"
    slug = base_slug
    suffix = 1
    # Two communities can legitimately share a name in different
    # regions ("Bodi" is common) — auto-disambiguating the slug rather
    # than rejecting the signup outright is the difference between a
    # real onboarding flow and one that breaks the moment two towns
    # share a name.
    while Community.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    try:
        community = Community.objects.create(
            name=community_name, slug=slug, region=region.strip(),
            default_general_male_amount=default_general_male_amount,
            default_general_female_amount=default_general_female_amount,
        )
    except IntegrityError:
        raise ValidationError("Could not create this community — please try again.")

    admin_user = User.objects.create_user(
        username=admin_username, password=admin_password, email=admin_email,
        community=community, role=Role.COMMUNITY_ADMIN,
    )

    from audit_log.services import record_event
    record_event(
        category="community", action="community_created", actor=actor, community=community,
        target_type="Community", target_id=community.id, target_label=community.name,
        description=f"Community '{community.name}' onboarded, with '{admin_username}' as its first Community Admin.",
    )

    return community, admin_user


def is_platform_admin(user) -> bool:
    """
    "I think it's the super admin who should add, edit, or remove a
    community." Deliberately narrower than can_manage_families(): a
    Community Admin runs their OWN community's day-to-day affairs
    (families, contribution rates, members — all of that stays exactly
    as it was), but creating, editing, deactivating, or deleting the
    COMMUNITY ITSELF is a platform-level decision, not a single
    community's own admin's call to make about themselves.
    """
    from accounts.models import Role
    return user.is_superuser or user.role == Role.PLATFORM_ADMIN


def list_communities():
    return Community.objects.all().order_by("name")


@transaction.atomic
def update_community(community: Community, **fields) -> Community:
    allowed = {"name", "region", "default_general_male_amount", "default_general_female_amount"}
    for key, value in fields.items():
        if key not in allowed:
            raise ValidationError(f"'{key}' cannot be changed through this action.")
        setattr(community, key, value)
    community.full_clean()
    community.save()
    return community


_HEX_COLOR_RE = None


def _is_valid_hex_color(value: str) -> bool:
    global _HEX_COLOR_RE
    if _HEX_COLOR_RE is None:
        import re
        _HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
    return bool(_HEX_COLOR_RE.match(value))


def update_own_community_branding(*, actor, tagline: str = None, primary_color: str = None, secondary_color: str = None) -> Community:
    """
    'Configure branding (logo, colors, community information)' — a
    Community Admin's own workspace, self-service, without needing the
    Platform Admin for a purely cosmetic change. Deliberately separate
    from update_community above, which stays Platform-Admin-only for
    the fields that actually matter operationally (name, region,
    default rates) — branding never touches any permission check or
    financial calculation, so there's no reason it should need
    platform-level sign-off.
    """
    if actor.role != "community_admin" or actor.community_id is None:
        raise ValidationError("Only a Community Admin can configure their own community's branding.")
    community = actor.community

    if primary_color is not None:
        if primary_color and not _is_valid_hex_color(primary_color):
            raise ValidationError("Primary color must be a real hex code, like #2F5233.")
        community.primary_color = primary_color
    if secondary_color is not None:
        if secondary_color and not _is_valid_hex_color(secondary_color):
            raise ValidationError("Secondary color must be a real hex code, like #B8860B.")
        community.secondary_color = secondary_color
    if tagline is not None:
        community.tagline = tagline

    community.full_clean()
    community.save()
    return community


def upload_own_community_logo(*, actor, logo) -> Community:
    if actor.role != "community_admin" or actor.community_id is None:
        raise ValidationError("Only a Community Admin can configure their own community's branding.")
    community = actor.community
    community.logo = logo
    community.save(update_fields=["logo"])
    return community


def update_required_funeral_approvals(*, actor, required_approvals: int) -> Community:
    """'Configure approval workflows' — self-service, Community Admin only, own community only."""
    if actor.role != "community_admin" or actor.community_id is None:
        raise ValidationError("Only a Community Admin can configure their own community's approval workflow.")
    if required_approvals < 1 or required_approvals > 10:
        raise ValidationError("The number of required approvals must be between 1 and 10.")
    community = actor.community
    community.required_funeral_approvals = required_approvals
    community.save(update_fields=["required_funeral_approvals"])
    return community


def deactivate_community(community: Community, actor=None) -> Community:
    """
    "Remove" a community, the safe/reversible way: is_active=False hides
    it from platform-overview listings without touching a single row of
    its actual data. A community's families, members, and — critically —
    its financial history are never something an admin action should
    casually destroy.
    """
    community.is_active = False
    community.save(update_fields=["is_active"])
    from audit_log.services import record_event
    record_event(
        category="community", action="community_deactivated", actor=actor, community=community,
        target_type="Community", target_id=community.id, target_label=community.name,
        description=f"Community '{community.name}' deactivated — hidden from platform listings, no data touched.",
    )
    return community


def reactivate_community(community: Community, actor=None) -> Community:
    community.is_active = True
    community.save(update_fields=["is_active"])
    from audit_log.services import record_event
    record_event(
        category="community", action="community_reactivated", actor=actor, community=community,
        target_type="Community", target_id=community.id, target_label=community.name,
        description=f"Community '{community.name}' reactivated.",
    )
    return community


def set_community_access_expiration(*, community: Community, days_from_now: int, plan: str = None) -> Community:
    """
    'Some people can also decide to rent or use the service
    temporarily.' Sets (or resets) a real, enforced deadline —
    CommunityAwareJWTAuthentication and the login serializer both check
    this on every request, not just when it's first set.
    """
    from django.utils import timezone

    if days_from_now <= 0:
        raise ValidationError("The access period must be at least 1 day.")
    community.access_expires_at = timezone.now() + timedelta(days=days_from_now)
    community.access_plan = plan or (
        community.access_plan if community.access_plan != Community.AccessPlan.ONGOING else Community.AccessPlan.TIME_LIMITED
    )
    community.save(update_fields=["access_expires_at", "access_plan"])
    return community


def extend_community_access(*, community: Community, additional_days: int, actor=None) -> Community:
    """
    Renewing an already-temporary community, or a lapsed one — extends
    from NOW if access already expired (or was never set), or adds onto
    the existing deadline if it's still running, so renewing early
    never shortens what was already paid for.
    """
    from django.utils import timezone

    if additional_days <= 0:
        raise ValidationError("The extension must be at least 1 day.")
    base = community.access_expires_at if (community.access_expires_at and not community.is_access_expired) else timezone.now()
    community.access_expires_at = base + timedelta(days=additional_days)
    community.save(update_fields=["access_expires_at"])
    from audit_log.services import record_event
    record_event(
        category="community", action="community_access_extended", actor=actor, community=community,
        target_type="Community", target_id=community.id, target_label=community.name,
        description=f"Access for '{community.name}' extended by {additional_days} day(s), new expiry {community.access_expires_at.date().isoformat()}.",
    )
    return community


def reset_administrator_password(*, actor, username: str, new_password: str) -> "User":
    """
    'Reset administrator accounts when requested' — a real, occasional
    support action (a locked-out Community Admin has nowhere else to
    turn) distinct from the ongoing internal management the Platform
    Admin must otherwise stay out of. Deliberately scoped to
    Community Admin and Platform Admin accounts only — not a general
    "reset anyone's password" tool, which would cut against "must not
    interfere with the internal management of a community... unless
    granted explicit support access."
    """
    from accounts.models import User

    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can reset an administrator account's password.")
    if len(new_password) < 8:
        raise ValidationError("The new password must be at least 8 characters.")

    try:
        target = User.objects.get(username=username)
    except User.DoesNotExist:
        raise ValidationError(f"No user named '{username}' exists.")
    if target.role not in ("community_admin", "platform_admin"):
        raise ValidationError("Only a Community Admin or Platform Admin account's password can be reset this way.")

    target.set_password(new_password)
    target.save(update_fields=["password"])

    from audit_log.services import record_event
    record_event(
        category="role", action="administrator_password_reset", actor=actor, community=target.community,
        target_type="User", target_id=target.id, target_label=target.username,
        description=f"'{target.username}''s password was reset by platform administrator '{actor.username}'.",
    )
    return target


def terminate_community_access(community: Community, actor=None) -> Community:
    """
    'Extend or terminate licenses' — the direct counterpart to
    extend_community_access above. Distinct from deactivate_community:
    deactivating hides a community from platform listings but leaves
    its own access clock (if any) running underneath; terminating cuts
    a temporary/rental period short right now, immediately, regardless
    of how much time was left on it. Never touches an already-ongoing
    (permanent) community's access — there's no license there to
    terminate in the first place.
    """
    from django.utils import timezone

    if community.access_plan == Community.AccessPlan.ONGOING:
        raise ValidationError(f"'{community.name}' has ongoing, permanent access — there's no temporary license here to terminate.")
    community.access_expires_at = timezone.now()
    community.save(update_fields=["access_expires_at"])
    from audit_log.services import record_event
    record_event(
        category="community", action="community_license_terminated", actor=actor, community=community,
        target_type="Community", target_id=community.id, target_label=community.name,
        description=f"'{community.name}'s temporary access license was terminated immediately by {getattr(actor, 'username', 'the platform')}.",
    )
    return community


def make_community_permanent(community: Community) -> Community:
    """Upgrades a temporary/rental community to ongoing, permanent access — clears the deadline entirely."""
    community.access_expires_at = None
    community.access_plan = Community.AccessPlan.ONGOING
    community.save(update_fields=["access_expires_at", "access_plan"])
    return community


def can_manage_payout_accounts_for(user, community: Community) -> bool:
    """
    'Configured by the Community Administrator.' Deliberately narrower
    than contribution-rule management (which Chairman/Secretary also
    hold) — this is literally 'where does the community's money go,'
    and stays with the Community Admin of THIS community (or a
    platform admin) specifically, not the wider committee.
    """
    if user.is_superuser or is_platform_admin(user):
        return True
    return user.role == "community_admin" and user.community_id == community.id


def add_payout_account(*, community: Community, actor, account_type: str, provider_name: str, account_number: str, account_holder_name: str) -> CommunityPayoutAccount:
    if not can_manage_payout_accounts_for(actor, community):
        raise ValidationError("Only this community's own Community Admin (or a platform administrator) can configure its payout accounts.")
    if not account_number.strip() or not account_holder_name.strip() or not provider_name.strip():
        raise ValidationError("Provider, account number, and account holder name are all required.")
    return CommunityPayoutAccount.objects.create(
        community=community, account_type=account_type, provider_name=provider_name.strip(),
        account_number=account_number.strip(), account_holder_name=account_holder_name.strip(),
    )


def deactivate_payout_account(*, account: CommunityPayoutAccount, actor) -> CommunityPayoutAccount:
    if not can_manage_payout_accounts_for(actor, account.community):
        raise ValidationError("Only this community's own Community Admin (or a platform administrator) can change its payout accounts.")
    account.is_active = False
    account.save(update_fields=["is_active"])
    return account


def list_payout_accounts(community: Community) -> list:
    return list(community.payout_accounts.all())


def create_billing_record(*, community: Community, description: str, amount, actor) -> PlatformBillingRecord:
    """
    'Subscription payments belong to the platform.' Platform-admin
    only, deliberately — even that community's own Community Admin
    doesn't create or confirm their own platform billing, the same way
    a customer doesn't write their own invoice. They can still VIEW
    their community's records (see list_billing_records_for_viewing),
    just never create or mark one paid.
    """
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can create a platform billing record.")
    if not description.strip():
        raise ValidationError("A description is required.")
    if amount is None or amount <= 0:
        raise ValidationError("The amount must be greater than zero.")
    return PlatformBillingRecord.objects.create(community=community, description=description.strip(), amount=amount, created_by=actor)


def mark_billing_record_paid(*, record: PlatformBillingRecord, actor, payment_reference: str = "") -> PlatformBillingRecord:
    """
    Confirms a real-world fact (payment genuinely received through some
    real channel — bank transfer, MoMo to the PLATFORM's own account,
    cash) — this is NOT a payment gateway and never touches or moves
    any actual money itself.
    """
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can mark a platform billing record as paid.")
    if record.status != PlatformBillingRecord.Status.UNPAID:
        raise ValidationError("This record has already been decided.")
    record.status = PlatformBillingRecord.Status.PAID
    record.marked_paid_by = actor
    record.marked_paid_at = timezone.now()
    record.payment_reference = payment_reference
    record.save()
    from audit_log.services import record_event
    record_event(
        category="billing", action="billing_record_marked_paid", actor=actor, community=record.community,
        target_type="PlatformBillingRecord", target_id=record.id, target_label=record.description,
        description=f"Billing record '{record.description}' ({record.amount}) for '{record.community.name}' marked paid.",
        metadata={"amount": str(record.amount), "payment_reference": payment_reference},
    )
    return record


def waive_billing_record(*, record: PlatformBillingRecord, actor) -> PlatformBillingRecord:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can waive a platform billing record.")
    if record.status != PlatformBillingRecord.Status.UNPAID:
        raise ValidationError("This record has already been decided.")
    record.status = PlatformBillingRecord.Status.WAIVED
    record.marked_paid_by = actor
    record.marked_paid_at = timezone.now()
    record.save()
    from audit_log.services import record_event
    record_event(
        category="billing", action="billing_record_waived", actor=actor, community=record.community,
        target_type="PlatformBillingRecord", target_id=record.id, target_label=record.description,
        description=f"Billing record '{record.description}' ({record.amount}) for '{record.community.name}' waived.",
        metadata={"amount": str(record.amount)},
    )
    return record


def list_billing_records_for_viewing(*, community: Community, actor) -> list:
    """
    Platform admins see any community's billing history; a community's
    OWN Community Admin can see their own community's records (so they
    know what they owe) — but never another community's, and never
    anything beyond viewing.
    """
    if is_platform_admin(actor):
        return list(community.platform_billing_records.all())
    if actor.role == "community_admin" and actor.community_id == community.id:
        return list(community.platform_billing_records.all())
    raise ValidationError("You don't have permission to view this community's platform billing records.")


def platform_revenue_report(*, actor, start_date=None, end_date=None) -> dict:
    """
    'View revenue reports' — Platform Admin only, aggregating across
    every community's PlatformBillingRecord. Still the platform's OWN
    fee income exclusively — this never touches, sums with, or even
    queries a single community's actual contribution/gift ledgers,
    the same hard boundary PlatformBillingRecord itself was built to
    enforce.
    """
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can view the platform revenue report.")

    qs = PlatformBillingRecord.objects.all()
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    paid = qs.filter(status=PlatformBillingRecord.Status.PAID)
    unpaid = qs.filter(status=PlatformBillingRecord.Status.UNPAID)
    waived = qs.filter(status=PlatformBillingRecord.Status.WAIVED)

    by_community = list(
        paid.values("community__name").annotate(total=Sum("amount")).order_by("-total")
    )

    return {
        "total_paid": str(paid.aggregate(total=Sum("amount"))["total"] or Decimal("0")),
        "total_outstanding": str(unpaid.aggregate(total=Sum("amount"))["total"] or Decimal("0")),
        "total_waived": str(waived.aggregate(total=Sum("amount"))["total"] or Decimal("0")),
        "paid_count": paid.count(),
        "unpaid_count": unpaid.count(),
        "waived_count": waived.count(),
        "by_community": [{"community_name": r["community__name"], "total": str(r["total"])} for r in by_community],
    }


def delete_empty_community(community: Community):
    """
    Genuine, permanent deletion — but ONLY for a community that was
    created by mistake and has no real data in it yet. The moment a
    community has a single family or member, this refuses: permanently
    destroying real financial/membership history is not something this
    action will ever do, no matter who asks. Deactivation above is the
    real "remove" for anything that's actually been used.
    """
    from families.models import Family
    from members.models import Member

    if Family.objects.filter(community=community).exists() or Member.objects.filter(community=community).exists():
        raise ValidationError(
            "This community already has real data in it (families or members) — it can only be "
            "deactivated, not permanently deleted. Deactivating hides it without destroying any history."
        )
    community.delete()


@transaction.atomic
def add_community_admin(*, community: Community, username: str, password: str, email: str = ""):
    """
    "Each community should have [its own] admin to manage their system"
    — the platform-admin-side counterpart: once a community exists, its
    very first (or an additional) Community Admin login is created here,
    scoped to exactly that one community, with full day-to-day authority
    over it and nowhere else.
    """
    from accounts.models import Role, User

    if User.objects.filter(username=username).exists():
        raise ValidationError(f"The username '{username}' is already taken.")
    return User.objects.create_user(username=username, password=password, email=email, community=community, role=Role.COMMUNITY_ADMIN)


def list_community_admins(community: Community):
    from accounts.models import Role, User
    return User.objects.filter(community=community, role=Role.COMMUNITY_ADMIN).order_by("username")


def list_platform_admins(*, actor) -> list:
    """'Managing platform administrators' — Platform Admin only, cross-community by nature so no community filter applies."""
    from accounts.models import Role, User

    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can view the list of platform administrators.")
    return list(User.objects.filter(role=Role.PLATFORM_ADMIN).order_by("username"))


def add_platform_admin(*, username: str, password: str, email: str = "", actor) -> "User":
    """
    Deliberately create_user, never create_superuser — Platform Admin's
    authority comes entirely from role=platform_admin, exactly like
    every other role in this system. is_superuser would bypass every
    operational boundary Platform Admin is supposed to respect (it
    must not add/edit members, manage a community's finances, create
    funeral events, and so on) — the same reasoning behind
    accounts.management.commands.create_platform_admin.
    """
    from accounts.models import Role, User

    if not is_platform_admin(actor):
        raise ValidationError("Only an existing platform administrator can create another one.")
    if User.objects.filter(username=username).exists():
        raise ValidationError(f"The username '{username}' is already taken.")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.")

    new_admin = User.objects.create_user(username=username, password=password, email=email, role=Role.PLATFORM_ADMIN)

    from audit_log.services import record_event
    record_event(
        category="role", action="platform_admin_created", actor=actor,
        target_type="User", target_id=new_admin.id, target_label=username,
        description=f"'{username}' granted Platform Admin access by '{actor.username}'.",
    )
    return new_admin


def upload_homepage_image(*, image, actor, caption="", subcaption="", display_order=0) -> HomepageImage:
    """'The homepage live pictures... should be uploaded by the super admin.' Platform-admin only — this is the public homepage's own content, not any single community's."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    return HomepageImage.objects.create(image=image, caption=caption, subcaption=subcaption, display_order=display_order, uploaded_by=actor)


def deactivate_homepage_image(*, homepage_image: HomepageImage, actor) -> HomepageImage:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    homepage_image.is_active = False
    homepage_image.save(update_fields=["is_active"])
    return homepage_image


def list_all_homepage_images(*, actor) -> list:
    """The management view — active and inactive alike, so there's something to actually manage."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    return list(HomepageImage.objects.all())


def list_public_homepage_images() -> list:
    """The one genuinely public read here — no login, matching the homepage itself. Only ever active images, in display order."""
    return list(HomepageImage.objects.filter(is_active=True))


def submit_plan_interest(*, plan_type: str, name: str, email: str = "", phone: str = "", message: str = "") -> PlanInterestSubmission:
    """Public — anyone visiting the homepage can register interest in a not-yet-available plan, no login needed."""
    if not name.strip():
        raise ValidationError("Please include your name.")
    if not email.strip() and not phone.strip():
        raise ValidationError("Please include an email or phone number so we can reach you.")
    return PlanInterestSubmission.objects.create(
        plan_type=plan_type, name=name.strip(), email=email.strip(), phone=phone.strip(), message=message.strip(),
    )


def list_plan_interest_submissions(*, actor) -> list:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can view plan interest submissions.")
    return list(PlanInterestSubmission.objects.all())


def mark_plan_interest_contacted(*, submission: PlanInterestSubmission, actor) -> PlanInterestSubmission:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can update plan interest submissions.")
    submission.contacted = True
    submission.save(update_fields=["contacted"])
    return submission


def _is_own_communitys_admin(user, community: Community) -> bool:
    return user.role == "community_admin" and user.community_id == community.id


def submit_announcement(*, community: Community, title: str, content: str, actor, image=None, video_url: str = "", homepage_feature_requested: bool = False) -> Announcement:
    """'Has to be submitted by the community admin' — for their OWN community only, matching every other community-scoped authority in this platform. 'When it needs it on the homepage he has to send a request to the platform admin' — homepage_feature_requested is that request, decided at approval time, not automatic."""
    if not _is_own_communitys_admin(actor, community):
        raise ValidationError("Only this community's own Community Admin can submit an announcement for it.")
    if not title.strip() or not content.strip():
        raise ValidationError("An announcement needs both a title and content.")
    announcement = Announcement.objects.create(
        community=community, title=title.strip(), content=content.strip(), image=image, video_url=video_url,
        submitted_by=actor, homepage_feature_requested=homepage_feature_requested,
    )
    AnnouncementReviewLog.objects.create(announcement=announcement, action=AnnouncementReviewLog.Action.SUBMITTED, actor=actor)
    return announcement


def approve_announcement(*, announcement: Announcement, actor, edited_title: str = None, edited_content: str = None, feature_on_homepage: bool = None) -> Announcement:
    """'The super admin has to approve it... and the super admin can edit the content.' Editing and approving happen together — there's no separate 'just edit, don't decide yet' state. feature_on_homepage is the Platform Admin's own decision on the Community Admin's homepage request — defaults to whatever was requested if not explicitly overridden."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can approve an announcement.")
    if announcement.status != Announcement.Status.PENDING:
        raise ValidationError("This announcement has already been decided.")

    was_edited = False
    if edited_title is not None and edited_title.strip() and edited_title.strip() != announcement.title:
        announcement.title = edited_title.strip()
        was_edited = True
    if edited_content is not None and edited_content.strip() and edited_content.strip() != announcement.content:
        announcement.content = edited_content.strip()
        was_edited = True

    announcement.status = Announcement.Status.APPROVED
    announcement.reviewed_by = actor
    announcement.reviewed_at = timezone.now()
    announcement.was_edited_by_reviewer = was_edited
    announcement.featured_on_homepage = announcement.homepage_feature_requested if feature_on_homepage is None else feature_on_homepage
    announcement.save()
    AnnouncementReviewLog.objects.create(
        announcement=announcement,
        action=AnnouncementReviewLog.Action.EDITED_AND_APPROVED if was_edited else AnnouncementReviewLog.Action.APPROVED,
        actor=actor,
        notes="Featured on homepage" if announcement.featured_on_homepage else "",
    )
    if announcement.featured_on_homepage:
        # Ordinary approval is already thoroughly covered by
        # AnnouncementReviewLog; the general audit log's value-add here
        # is specifically the platform-level decision to put something
        # in front of the public, not the routine Notice Board approval.
        from audit_log.services import record_event
        record_event(
            category="announcement", action="homepage_feature_granted", actor=actor, community=announcement.community,
            target_type="Announcement", target_id=announcement.id, target_label=announcement.title,
            description=f"'{announcement.title}' from '{announcement.community.name}' granted public homepage placement.",
        )
    return announcement


def list_homepage_featured_announcements() -> list:
    """The one genuinely public read here — no login, matching the homepage itself. Only ever announcements BOTH approved for the Notice Board AND separately granted homepage placement by a Platform Admin."""
    return list(Announcement.objects.filter(status=Announcement.Status.APPROVED, featured_on_homepage=True).select_related("community"))


def reject_announcement(*, announcement: Announcement, actor, reason: str) -> Announcement:
    """'Reject it with reasons for the community admin to edit and resend again' — the reason is required, not optional; it's the whole point of what makes a resubmission possible."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can reject an announcement.")
    if announcement.status != Announcement.Status.PENDING:
        raise ValidationError("This announcement has already been decided.")
    if not reason.strip():
        raise ValidationError("A reason is required — the community admin needs to know what to fix.")

    announcement.status = Announcement.Status.REJECTED
    announcement.reviewed_by = actor
    announcement.reviewed_at = timezone.now()
    announcement.rejection_reason = reason.strip()
    announcement.save()
    AnnouncementReviewLog.objects.create(announcement=announcement, action=AnnouncementReviewLog.Action.REJECTED, actor=actor, notes=reason.strip())
    return announcement


def resubmit_announcement(*, announcement: Announcement, actor, title: str = None, content: str = None, image=None, video_url: str = None) -> Announcement:
    """'For the community admin to edit and resend again' — only the ORIGINAL community's own admin, and only something that's actually been rejected, not a pending or already-approved one."""
    if not _is_own_communitys_admin(actor, announcement.community):
        raise ValidationError("Only this community's own Community Admin can resubmit this announcement.")
    if announcement.status != Announcement.Status.REJECTED:
        raise ValidationError("Only a rejected announcement can be resubmitted.")

    if title is not None and title.strip():
        announcement.title = title.strip()
    if content is not None and content.strip():
        announcement.content = content.strip()
    if image is not None:
        announcement.image = image
    if video_url is not None:
        announcement.video_url = video_url

    announcement.status = Announcement.Status.PENDING
    announcement.reviewed_by = None
    announcement.reviewed_at = None
    announcement.rejection_reason = ""
    announcement.was_edited_by_reviewer = False
    announcement.save()
    AnnouncementReviewLog.objects.create(announcement=announcement, action=AnnouncementReviewLog.Action.RESUBMITTED, actor=actor)
    return announcement


def list_pending_announcements_for_review(*, actor) -> list:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can review announcements.")
    return list(Announcement.objects.filter(status=Announcement.Status.PENDING).select_related("community", "submitted_by"))


def list_announcements_for_own_community(*, community: Community, actor) -> list:
    """A Community Admin's own view of everything THEY'VE submitted — pending, approved, and rejected alike, so there's something to track and resubmit from."""
    if not _is_own_communitys_admin(actor, community):
        raise ValidationError("Only this community's own Community Admin can view its announcement submissions.")
    return list(Announcement.objects.filter(community=community))


def list_public_notice_board() -> list:
    """The actual notice board — every community's approved announcements, platform-wide, most recent first. Requires being logged in (checked at the view layer) — this is internal community content, not public marketing."""
    return list(Announcement.objects.filter(status=Announcement.Status.APPROVED).select_related("community"))

# The real, platform-wide features a flag can actually gate — checked
# by AskChatbotView and messaging's channel views before doing
# anything, not just a management-page toy. New entries here are only
# meaningful once the corresponding feature actually checks the flag.
DEFAULT_FEATURE_FLAGS = [
    ("chatbot", "Help Chatbot", "The floating help assistant available to every signed-in user."),
    ("messaging", "Community Messaging", "Platform, Community, and Family channels."),
]


def ensure_default_feature_flags() -> None:
    for key, name, description in DEFAULT_FEATURE_FLAGS:
        FeatureFlag.objects.get_or_create(key=key, defaults={"name": name, "description": description})


def list_feature_flags(*, actor) -> list:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can view feature flags.")
    ensure_default_feature_flags()
    return list(FeatureFlag.objects.all())


def set_feature_flag_enabled(*, key: str, is_enabled: bool, actor) -> FeatureFlag:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can change a feature flag.")
    ensure_default_feature_flags()
    try:
        flag = FeatureFlag.objects.get(key=key)
    except FeatureFlag.DoesNotExist:
        raise ValidationError(f"No feature flag named '{key}' exists.")
    flag.is_enabled = is_enabled
    flag.updated_by = actor
    flag.save(update_fields=["is_enabled", "updated_by", "updated_at"])

    from audit_log.services import record_event
    record_event(
        category="community", action="feature_flag_toggled", actor=actor,
        target_type="FeatureFlag", target_id=flag.key, target_label=flag.name,
        description=f"Feature flag '{flag.name}' turned {'on' if is_enabled else 'off'}.",
    )
    return flag


def is_feature_enabled(key: str) -> bool:
    """
    A deliberately unrestricted read — every signed-in user's chatbot
    widget and messaging nav link need to know this, not just a
    Platform Admin. Fails OPEN (returns True) if the flag has never
    been created at all, so a brand-new deployment behaves exactly as
    it always has rather than silently disabling something nobody
    configured yet.
    """
    flag = FeatureFlag.objects.filter(key=key).first()
    return flag.is_enabled if flag else True

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
from django.db import IntegrityError, models, transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from .models import Announcement, AnnouncementReviewLog, Community, CommunityBackupRecord, CommunityPayoutAccount, FeatureFlag, HomepageImage, PlanInterestSubmission, PlatformBillingRecord


@transaction.atomic
def onboard_new_community(
    *, community_name: str, admin_username: str, admin_password: str, admin_email: str = "",
    region: str = "", default_general_male_amount: Decimal = Decimal("5"),
    default_general_female_amount: Decimal = Decimal("3"), actor=None,
    district: str = "", traditional_authority_name: str = "", contact_phone: str = "",
    contact_email: str = "", address: str = "", estimated_population: int = None, registration_notes: str = "",
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
            district=district.strip(), traditional_authority_name=traditional_authority_name.strip(),
            contact_phone=contact_phone.strip(), contact_email=contact_email.strip(),
            address=address.strip(), estimated_population=estimated_population,
            registration_notes=registration_notes.strip(),
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
    allowed = {
        "name", "region", "default_general_male_amount", "default_general_female_amount",
        "district", "traditional_authority_name", "contact_phone", "contact_email",
        "address", "estimated_population", "registration_notes",
    }
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


def send_subscription_reminder(*, community: Community, actor, message: str = "") -> int:
    """
    'The platform admin should have a way to remind communities to pay
    their subscription fees.' Notifies every Community Admin in this
    community — not just one, since a community's leadership can
    genuinely have more than one Admin account — and records who sent
    it and when directly on the Community itself, so the Platform
    Admin can see reminder history at a glance rather than digging
    through the notification log.

    The default message names the community's actual outstanding
    PlatformBillingRecord(s) — real amounts and descriptions, the same
    ledger a Platform Admin already uses to mark payments received —
    rather than a generic "please pay" with no concrete figure behind
    it.
    """
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can send a subscription reminder.")

    from decimal import Decimal

    from accounts.models import Role, User
    from notifications.models import Notification
    from notifications.services import _deliver

    unpaid = PlatformBillingRecord.objects.filter(community=community, status=PlatformBillingRecord.Status.UNPAID)
    total_unpaid = sum((r.amount for r in unpaid), Decimal("0"))

    if message.strip():
        real_message = message.strip()
    elif unpaid.exists():
        items = "; ".join(f"{r.description} (GHS {r.amount})" for r in unpaid)
        real_message = f"A reminder that {community.name} has outstanding platform fees totalling GHS {total_unpaid}: {items}. Please arrange payment to keep the community's access uninterrupted."
    elif community.access_expires_at:
        when = "expired on" if community.is_access_expired else "is due to expire on"
        real_message = f"A reminder that {community.name}'s subscription {when} {community.access_expires_at:%d %b %Y}. Please arrange payment to keep the community's access uninterrupted."
    else:
        real_message = f"A reminder from the platform team regarding {community.name}'s subscription — please get in touch."

    admins = User.objects.filter(community=community, role=Role.COMMUNITY_ADMIN)
    sent = 0
    for admin_user in admins:
        notification = Notification.objects.create(
            community=community, category=Notification.Category.SUBSCRIPTION_REMINDER,
            message=real_message, recipient_user=admin_user,
        )
        _deliver(notification)
        sent += 1

    community.last_subscription_reminder_at = timezone.now()
    community.last_subscription_reminder_by = actor
    community.save(update_fields=["last_subscription_reminder_at", "last_subscription_reminder_by"])

    from audit_log.services import record_event
    record_event(
        category="community", action="subscription_reminder_sent", actor=actor, community=community,
        target_type="Community", target_id=community.id, target_label=community.name,
        description=f"Subscription reminder sent to {sent} admin(s) of '{community.name}'.",
    )
    return sent


def communities_needing_subscription_attention():
    """
    'The platform admin should have a way to remind communities to pay
    their subscription fees' — the actual worklist: every community
    with at least one unpaid PlatformBillingRecord, OR a temporary/
    rental access period that has already expired or expires within
    the next 14 days. An ongoing/permanent community with nothing
    unpaid never appears here — there's genuinely nothing to remind
    them about.
    """
    from datetime import timedelta

    soon = timezone.now() + timedelta(days=14)
    return Community.objects.filter(
        models.Q(platform_billing_records__status=PlatformBillingRecord.Status.UNPAID)
        | models.Q(access_expires_at__isnull=False, access_expires_at__lte=soon)
    ).distinct().order_by("access_expires_at")


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


def list_all_community_admins(*, actor) -> list:
    """
    'That they can manage the platform admins on the community admins'
    — the existing list_community_admins is per-community, requiring
    one call per community to build a unified view; this is the
    one-query version a genuine "User Management" page across the
    whole platform actually needs.
    """
    from accounts.models import Role, User

    if not (actor.is_superuser or actor.has_platform_admin_capability("manage_community_admins")):
        raise ValidationError("Only a platform administrator with the 'manage_community_admins' capability can view this.")
    return list(
        User.objects.filter(role=Role.COMMUNITY_ADMIN)
        .select_related("community")
        .order_by("community__name", "username")
    )


def list_platform_admins(*, actor) -> list:
    """'Managing platform administrators' — Platform Admin only, cross-community by nature so no community filter applies."""
    from accounts.models import Role, User

    if not (actor.is_superuser or actor.has_platform_admin_capability("manage_platform_admins")):
        raise ValidationError("Only a platform administrator with the 'manage_platform_admins' capability can view the list of platform administrators.")
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

    if not (actor.is_superuser or actor.has_platform_admin_capability("manage_platform_admins")):
        raise ValidationError("Only a platform administrator with the 'manage_platform_admins' capability can create another one.")
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


def update_platform_admin_capabilities(*, target: "User", capabilities: dict, actor) -> "User":
    """
    'System settings should provide more option that will restrict or
    give access to the platform admin based on what they can do... they
    manage only the platform admin, not community member.'

    A Platform Admin can NEVER modify their own capabilities — only
    another Platform Admin's. Without this, restricting one's own
    'manage_platform_admins' capability by mistake would be a genuine,
    hard lockout: nobody (including that same account) could ever use
    this endpoint again to undo it, unless a completely different
    Platform Admin still happened to retain the capability.
    """
    from accounts.models import PLATFORM_ADMIN_CAPABILITIES, Role

    if not (actor.is_superuser or actor.has_platform_admin_capability("manage_platform_admins")):
        raise ValidationError("Only a platform administrator with the 'manage_platform_admins' capability can change another Platform Admin's capabilities.")
    if target.id == actor.id:
        raise ValidationError("A Platform Admin can't change their own capabilities — ask a different Platform Admin to do it.")
    if target.role != Role.PLATFORM_ADMIN:
        raise ValidationError("Capabilities only apply to Platform Admin accounts.")

    unknown_keys = set(capabilities.keys()) - set(PLATFORM_ADMIN_CAPABILITIES.keys())
    if unknown_keys:
        raise ValidationError(f"Unrecognized capability key(s): {', '.join(sorted(unknown_keys))}.")

    target.platform_admin_capabilities = {**target.platform_admin_capabilities, **capabilities}
    target.save(update_fields=["platform_admin_capabilities"])

    from audit_log.services import record_event
    record_event(
        category="role", action="platform_admin_capabilities_updated", actor=actor,
        target_type="User", target_id=target.id, target_label=target.username,
        description=f"'{actor.username}' updated '{target.username}''s Platform Admin capabilities: {capabilities}.",
    )
    return target


def upload_homepage_image(*, image=None, video=None, actor, caption="", subcaption="", display_order=0) -> HomepageImage:
    """'The homepage live pictures... should be uploaded by the super admin... should be able to upload videos as well.' Platform-admin only — this is the public homepage's own content, not any single community's."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    homepage_image = HomepageImage(image=image, video=video, caption=caption, subcaption=subcaption, display_order=display_order, uploaded_by=actor)
    homepage_image.full_clean()
    homepage_image.save()
    return homepage_image


def deactivate_homepage_image(*, homepage_image: HomepageImage, actor) -> HomepageImage:
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    homepage_image.is_active = False
    homepage_image.save(update_fields=["is_active"])
    return homepage_image


def reactivate_homepage_image(*, homepage_image: HomepageImage, actor) -> HomepageImage:
    """The other half of deactivate — 'the platform admin should have option to edit, add, upload, or delete' implies bringing one back too, not just permanent removal as the only way forward."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    homepage_image.is_active = True
    homepage_image.save(update_fields=["is_active"])
    return homepage_image


def update_homepage_image(*, homepage_image: HomepageImage, actor, caption: str = None, subcaption: str = None, display_order: int = None) -> HomepageImage:
    """'The platform admin should have option to edit... some of the photos.' Caption/subcaption/ordering only — replacing the actual image file is a new upload (delete the old, add the new), not an edit of this one."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    fields = []
    if caption is not None:
        homepage_image.caption = caption.strip()
        fields.append("caption")
    if subcaption is not None:
        homepage_image.subcaption = subcaption.strip()
        fields.append("subcaption")
    if display_order is not None:
        homepage_image.display_order = display_order
        fields.append("display_order")
    if fields:
        homepage_image.save(update_fields=fields)
    return homepage_image


def delete_homepage_image(*, homepage_image: HomepageImage, actor) -> None:
    """A genuine, permanent removal — distinct from deactivate, which only hides an image while keeping it around to reactivate later."""
    if not is_platform_admin(actor):
        raise ValidationError("Only a platform administrator can manage the homepage's images.")
    homepage_image.delete()


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


def submit_announcement(
    *, community: Community, title: str, content: str, actor, image=None, video=None, video_url: str = "",
    funeral_event=None, homepage_feature_requested: bool = False,
) -> Announcement:
    """'Has to be submitted by the community admin' — for their OWN community only, matching every other community-scoped authority in this platform. 'When it needs it on the homepage he has to send a request to the platform admin' — homepage_feature_requested is that request, decided at approval time, not automatic."""
    if not _is_own_communitys_admin(actor, community):
        raise ValidationError("Only this community's own Community Admin can submit an announcement for it.")
    if not title.strip() or not content.strip():
        raise ValidationError("An announcement needs both a title and content.")
    if funeral_event is not None and funeral_event.community_id != community.id:
        raise ValidationError("That funeral doesn't belong to this community.")
    announcement = Announcement.objects.create(
        community=community, title=title.strip(), content=content.strip(), image=image, video=video, video_url=video_url,
        funeral_event=funeral_event, submitted_by=actor, homepage_feature_requested=homepage_feature_requested,
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

    from notifications.services import notify_community_of_new_announcement
    notify_community_of_new_announcement(community=announcement.community, announcement_title=announcement.title)

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
    if not (actor.is_superuser or actor.has_platform_admin_capability("manage_feature_flags")):
        raise ValidationError("Only a platform administrator with the 'manage_feature_flags' capability can change a feature flag.")
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


# ============================================================
# COMMUNITY DATA BACKUP — 'import a Google Drive link... to back
# up their system data, and should also have options to retrieve
# them back.' See tenants.models.CommunityBackupRecord for why this
# reads a shared link rather than authenticating to Google Drive's
# own API — no OAuth, no stored Drive credentials, just fetching a
# file the person already made link-shareable, the same way anyone's
# browser would.
# ============================================================

import re


def _extract_google_drive_file_id(drive_link: str) -> str:
    """
    Handles the handful of URL shapes an actual Google Drive 'Share'
    button produces: '/file/d/<id>/view', '?id=<id>', and a bare id
    typed in directly. Raises rather than guessing when none of these
    match — a wrong file id silently fetching nothing (or someone
    else's file) is worse than a clear "this doesn't look like a
    Drive link" error.
    """
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]{20,})",
        r"[?&]id=([a-zA-Z0-9_-]{20,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, drive_link)
        if match:
            return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", drive_link.strip()):
        return drive_link.strip()
    raise ValidationError(
        "That doesn't look like a Google Drive file link. Open the file in Drive, "
        "choose Share → 'Anyone with the link', copy that link, and paste it here."
    )


def export_community_backup(*, community: Community, actor) -> dict:
    """
    'Each community admin... can back up their system data.' A JSON
    snapshot of this community's own member and family roster —
    deliberately NOT funerals, payments, or any other financial
    ledger: those already have their own audit trail, reversal
    workflow, and business-rule validation (minimum-not-cap, no
    double-payment, and so on) that a blind restore would bypass
    entirely. Member/family data is comparatively safe to snapshot and
    later restore wholesale, since restoring it goes through the exact
    same create-or-update path (register_member/update_member) as any
    other write, not a direct database overwrite.
    """
    if not _is_own_communitys_admin(actor, community):
        raise ValidationError("Only this community's own Community Admin can back up its data.")

    from families.models import Family
    from members.models import Member

    families = list(Family.objects.filter(community=community).values("name", "description", "status"))
    members = []
    for m in Member.objects.filter(community=community).select_related("family"):
        members.append({
            "membership_number": m.membership_number, "full_name": m.full_name, "family_name": m.family.name if m.family else "",
            "gender": m.gender, "status": m.status, "phone": m.phone, "email": m.email,
            "date_of_birth": m.date_of_birth.isoformat() if m.date_of_birth else "",
            "occupation": m.occupation, "address": m.address, "ghana_card_number": m.ghana_card_number or "",
            "mother_name": m.mother_name, "father_name": m.father_name, "hometown": m.hometown,
            "marital_status": m.marital_status, "spouse_name": m.spouse_name,
            "emergency_contact_name": m.emergency_contact_name, "emergency_contact_phone": m.emergency_contact_phone,
        })

    CommunityBackupRecord.objects.create(
        community=community, kind=CommunityBackupRecord.Kind.EXPORT,
        member_count=len(members), family_count=len(families), performed_by=actor,
    )
    return {
        "community_name": community.name, "exported_at": timezone.now().isoformat(),
        "families": families, "members": members,
    }


def restore_community_backup_from_drive_link(*, community: Community, drive_link: str, actor) -> dict:
    """
    'Should also have options to retrieve them back.' Fetches a
    previously-exported backup file from a Google Drive share link and
    restores its families and members — every write goes through the
    exact same create_family/register_member/update_member every other
    write on this platform already goes through (matched by name for
    families, by membership_number for members), so this can never
    bypass duplicate detection, family-scoping, or any other existing
    business rule. Nothing is deleted; a restore only ever creates
    families/members that don't already exist and updates ones that do.
    """
    if not _is_own_communitys_admin(actor, community):
        raise ValidationError("Only this community's own Community Admin can restore its data.")

    import json

    import requests as http_requests

    file_id = _extract_google_drive_file_id(drive_link.strip())
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = http_requests.get(download_url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except http_requests.RequestException as exc:
        raise ValidationError(f"Could not fetch that file from Google Drive: {exc}")
    except (json.JSONDecodeError, ValueError):
        raise ValidationError(
            "That Drive file isn't a valid backup — make sure it's the exact file this platform exported, "
            "and that it's shared as 'Anyone with the link'."
        )

    return _restore_community_backup_from_data(community=community, data=data, actor=actor, drive_link=drive_link.strip())


def restore_community_backup_from_uploaded_file(*, community: Community, uploaded_file, actor) -> dict:
    """
    'Should also be able to upload from my computer to synchronize.'
    The same restore, for a backup file the Community Admin already
    has sitting on their own device — no Drive link, no fetch, just
    the file's own content read directly. Goes through the exact same
    families/members restore path as the Drive-link version, so
    there's only one place that logic (and its own duplicate-safety
    checks) actually lives.
    """
    if not _is_own_communitys_admin(actor, community):
        raise ValidationError("Only this community's own Community Admin can restore its data.")

    import json

    try:
        data = json.loads(uploaded_file.read())
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        raise ValidationError(
            "That file isn't a valid backup — make sure it's the exact file this platform exported, unmodified."
        )

    return _restore_community_backup_from_data(community=community, data=data, actor=actor, drive_link="")


def _restore_community_backup_from_data(*, community: Community, data: dict, actor, drive_link: str = "") -> dict:
    """Shared by both restore paths above — every write goes through the exact same create_family/register_member/update_member every other write on this platform already goes through."""
    from families import services as family_services
    from families.models import Family
    from members import services as member_services
    from members.models import Member

    if not isinstance(data, dict):
        raise ValidationError("That file isn't a valid backup — its contents aren't in the expected format.")

    families_restored = 0
    for family_row in data.get("families", []):
        name = (family_row.get("name") or "").strip()
        if not name:
            continue
        if not Family.objects.filter(community=community, name__iexact=name).exists():
            family_services.create_family(community=community, name=name, description=family_row.get("description", ""), actor=actor)
            families_restored += 1

    # 'Should also have options to retrieve them back' has to mean
    # restoring the SAME backup twice is safe — a Community Admin
    # accidentally clicking restore again, or re-running an old backup
    # after already having restored it once, must never duplicate
    # anyone. bulk_register_members' own duplicate detection matches
    # by membership_number, and (by design, to catch a genuine CSV
    # typo rather than silently registering a stranger) treats a
    # membership_number that doesn't match any existing member as an
    # ERROR row, not a new registration — exactly right for an
    # ordinary CSV upload, but wrong here: a real export's
    # membership_number came from the ORIGINAL community it was
    # exported from, and won't exist yet in a different (or a fresh,
    # empty) community being restored into. So membership_number is
    # only ever kept if a member with that exact number already
    # exists in THIS community; otherwise it's stripped and the row
    # falls back to the same by-name check as a number-less row,
    # rather than bulk_register_members rejecting it outright.
    rows = data.get("members", [])
    filtered_rows = []
    for row in rows:
        row = dict(row)
        membership_number = row.get("membership_number")
        if membership_number and Member.objects.filter(community=community, membership_number=membership_number).exists():
            filtered_rows.append(row)
            continue
        row.pop("membership_number", None)
        full_name = (row.get("full_name") or "").strip()
        family_name = (row.get("family_name") or "").strip()
        already_exists = Member.objects.filter(community=community, full_name__iexact=full_name, family__name__iexact=family_name).exists() if full_name else False
        if not already_exists:
            filtered_rows.append(row)

    result = member_services.bulk_register_members(community=community, rows=filtered_rows, actor=actor)

    CommunityBackupRecord.objects.create(
        community=community, kind=CommunityBackupRecord.Kind.RESTORE, drive_link=drive_link,
        member_count=result["created_count"] + result["updated_count"], family_count=families_restored, performed_by=actor,
    )
    return {
        "families_restored": families_restored,
        "members_created": result["created_count"], "members_updated": result["updated_count"], "member_errors": result["errors"],
    }


def list_backup_records(*, community: Community, actor) -> list:
    if not _is_own_communitys_admin(actor, community):
        raise ValidationError("Only this community's own Community Admin can view its backup history.")
    return list(CommunityBackupRecord.objects.filter(community=community).select_related("performed_by"))

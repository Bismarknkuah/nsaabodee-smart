import random
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from communication.providers import ProviderNotConfiguredError, SmsProvider
from .models import PhoneOTP, User

OTP_VALID_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


def request_otp(phone_number: str) -> str | None:
    """
    Sends a one-time login code by SMS. Deliberately returns nothing
    meaningful either way — whether or not a User account actually uses
    this phone number is never revealed here (that's decided at verify
    time instead), so this endpoint can't be used to enumerate which
    phone numbers have real accounts.

    Returns the code itself ONLY when DEMO_MODE_ENABLED is explicitly
    on AND no real SMS provider is configured — a way to actually test
    and demo phone+OTP sign-in without a paid Twilio account, the same
    spirit as the existing demo-login feature. In a real deployment
    with DEMO_MODE_ENABLED off (the only safe way to run this for real
    users), an unconfigured SMS provider still raises a genuine error
    here instead — never silently hands back a working login code.
    """
    if not phone_number or not phone_number.strip():
        raise ValidationError("Please enter a phone number.")
    phone_number = phone_number.strip()

    recent = PhoneOTP.objects.filter(
        phone_number=phone_number, created_at__gte=timezone.now() - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS),
    ).exists()
    if recent:
        raise ValidationError(f"Please wait a moment before requesting another code.")

    code = f"{random.randint(0, 999999):06d}"
    PhoneOTP.objects.create(phone_number=phone_number, code=code, expires_at=timezone.now() + timedelta(minutes=OTP_VALID_MINUTES))

    try:
        SmsProvider().send(
            recipient_address=phone_number, subject="",
            message=f"Your Nsaabodeɛ Smart sign-in code is {code}. It expires in {OTP_VALID_MINUTES} minutes.",
        )
    except ProviderNotConfiguredError as exc:
        if getattr(settings, "DEMO_MODE_ENABLED", False):
            return code
        raise ValidationError(f"Couldn't send the code: {exc}")
    return None


def _consume_valid_otp(phone_number: str, code: str) -> User:
    """
    Shared by both sign-in (verify_otp) and 'forgot password' — the
    exact same generic-error, attempt-limited, single-use validation
    either way, so there is only one place this security-sensitive
    logic can drift or be gotten wrong, not two copies of it.
    """
    generic_error = "That code is invalid or has expired. Request a new one."
    if not phone_number or not code:
        raise ValidationError(generic_error)
    phone_number = phone_number.strip()

    otp = PhoneOTP.objects.filter(phone_number=phone_number, is_used=False).order_by("-created_at").first()
    if otp is None:
        raise ValidationError(generic_error)

    if otp.attempts >= OTP_MAX_ATTEMPTS:
        raise ValidationError(generic_error)
    otp.attempts += 1
    otp.save(update_fields=["attempts"])

    if timezone.now() >= otp.expires_at:
        raise ValidationError(generic_error)
    if otp.code != code.strip():
        raise ValidationError(generic_error)

    user = User.objects.filter(phone_number=phone_number).first()
    if user is None:
        raise ValidationError(generic_error)

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    return user


def verify_otp(phone_number: str, code: str) -> User:
    """
    Returns the User for this phone number if the code is genuinely
    valid. Every failure path — wrong code, expired, already used, too
    many attempts, or simply no account with this phone number at all —
    raises the exact same generic message, deliberately: distinguishing
    them would tell an attacker which phone numbers are worth attacking
    further.
    """
    return _consume_valid_otp(phone_number, code)


def reset_password_with_otp(phone_number: str, code: str, new_password: str) -> User:
    """
    'Forgot password' — reuses the exact same phone verification
    already trusted for OTP sign-in (request_otp sends the same SMS
    code), rather than a separate email-reset flow this platform has
    no real infrastructure to send. Verifying the code proves it's
    genuinely this person's phone; only then is a new password set.
    """
    if not new_password or len(new_password) < 8:
        raise ValidationError("Please choose a password of at least 8 characters.")
    user = _consume_valid_otp(phone_number, code)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


def switch_dashboard_context(*, user: User, context: str) -> User:
    """
    'Switch to Personal Dashboard... does not require logout, does not
    create another account, only changes permission context.' Exactly
    that: one field flips, nothing else about the account changes.
    Only a genuine executive with a linked member profile has anything
    to switch between — a Community Member is already permanently
    'personal', and switching would be a no-op that could confuse
    someone into thinking a real capability exists that doesn't.

    'This switch must... log the switch in the audit log' — every
    context change is a real, individually attributable governance
    event, not a silent UI toggle: who switched, from which context,
    to which, and when.
    """
    from .models import DashboardContext

    if context not in DashboardContext.values:
        raise ValidationError(f"'{context}' isn't a real dashboard context.")
    if not user.can_switch_dashboard_context():
        raise ValidationError("Only an executive role with a linked personal profile can switch dashboard context.")

    previous_context = user.active_context
    user.active_context = context
    user.save(update_fields=["active_context"])

    if previous_context != context:
        from audit_log.services import record_event
        record_event(
            category="role", action="dashboard_context_switched", actor=user, community=user.community,
            target_type="User", target_id=user.id, target_label=user.username,
            description=f"'{user.username}' switched from {previous_context} to {context} context.",
            metadata={"previous_context": previous_context, "new_context": context},
        )
    return user


# 'The recognized feature keys a Community Admin or Family Head can
# actually restrict' — deliberately the Sidebar's own nav hrefs, since
# that's genuinely what "select what they should see in their
# dashboard" means. Kept here as the single source of truth the
# frontend's settings page reads from, rather than hardcoding the
# list separately and risking it drifting out of sync with the real
# nav.
RESTRICTABLE_FEATURES = {
    "/reports": "Reports",
    "/welfare-contributions": "Welfare & Contributions",
    "/payment-reversals": "Payment Reversals",
    "/suspicious-transactions": "Suspicious Transactions",
    "/expenses": "Expenses",
    "/liabilities": "Liabilities",
    "/contribution-rules": "Contribution Rules",
    "/meeting-summary": "Meeting Summary",
    "/community-settings": "Community Settings",
    "/inactive-members": "Inactive Members",
    "/audit-log": "Audit Log",
    "/notifications": "Notifications (admin)",
    "/front-desk": "Front Desk",
    "/pending-sync": "Pending Sync",
    "/my-family-expenses": "Family Expenses",
    "/tasks": "Tasks",
    "/my-receipts": "My Receipts",
    "/my-donations-received": "My Donations Received",
    "/town-elders-ledger": "Town Elders Ledger",
    # Added alongside this platform's own Family Fund, Ledger Wallet,
    # and Registration Officer features — never surfaced as
    # restrictable options before now, purely because nobody had
    # updated this list since those features were built, not because
    # of any deliberate choice to exclude them.
    "/family-fund": "Family Fund",
    "/ledger-wallets": "Ledger Wallets",
}

# 'The abusua can't assign work that was supposed to be assigned by
# the community executive or admin — which means that the abusua in
# his system settings should be restricted to what he can tick or
# not.' A Family Head's own restriction power is deliberately narrower
# than a Community Admin's — genuinely family-relevant, personal
# -dashboard tools only. "/tasks" is excluded on purpose: task
# assignment is community-wide workforce management, the community
# executive/admin's own domain — a Family Head keeps their OWN
# authority to assign tasks WITHIN their family (unchanged, built
# earlier), but restricting who can even see the Tasks feature for
# someone else is a different, broader kind of authority this
# platform doesn't extend to Family Head.
FAMILY_HEAD_RESTRICTABLE_FEATURES = {
    "/my-family-expenses": RESTRICTABLE_FEATURES["/my-family-expenses"],
    "/my-receipts": RESTRICTABLE_FEATURES["/my-receipts"],
    "/my-donations-received": RESTRICTABLE_FEATURES["/my-donations-received"],
    # 'More options in the system settings to set rules of what each
    # family executive can do' — a family's own Welfare campaigns
    # and Family Fund are squarely family-internal financial tools,
    # the same genuinely family-relevant category as the three above.
    "/welfare-contributions": RESTRICTABLE_FEATURES["/welfare-contributions"],
    "/family-fund": RESTRICTABLE_FEATURES["/family-fund"],
}

# The Traditional Leader's own restriction scope is narrower still —
# 'the chief should also have user management... to manage town
# elders' is specifically about that domain, not a grant of broader
# authority over whatever else a Town Elder's account might otherwise
# access (they could hold any ordinary role besides being an elder).
TRADITIONAL_LEADER_RESTRICTABLE_FEATURES = {
    "/town-elders-ledger": RESTRICTABLE_FEATURES["/town-elders-ledger"],
    # 'The town leader should also have more options for the system
    # settings' — Ledger Wallets includes the Town Elders' own wallet
    # scope, the financial tool most directly within this role's
    # actual domain.
    "/ledger-wallets": RESTRICTABLE_FEATURES["/ledger-wallets"],
}


def restrictable_features_for(actor) -> dict:
    if actor is not None and actor.role == "family_head":
        return FAMILY_HEAD_RESTRICTABLE_FEATURES
    if actor is not None and actor.role == "traditional_leader":
        return TRADITIONAL_LEADER_RESTRICTABLE_FEATURES
    return RESTRICTABLE_FEATURES


def list_manageable_users(*, actor):
    """
    'The community admin should have user management... where he can
    manage all the family head, community executives, community
    leader, collectors. Same as each family head... can manage on
    their family.' Returns exactly who can_restrict_features_for(actor,
    X) would say yes to — the manager and the manageable-user list are
    always the same underlying rule, never two rules that could drift
    apart.
    """
    from accounts.permissions import _COMMUNITY_EXECUTIVE_ROLES, _FAMILY_EXECUTIVE_ROLES, can_restrict_features_for

    if actor.role == "community_admin":
        candidates = User.objects.filter(community=actor.community, role__in=_COMMUNITY_EXECUTIVE_ROLES).exclude(id=actor.id)
    elif actor.role == "family_head":
        own_member = getattr(actor, "member_profile", None)
        if own_member is None or own_member.family_id is None:
            return []
        candidates = User.objects.filter(
            member_profile__family_id=own_member.family_id,
            role__in=(*_FAMILY_EXECUTIVE_ROLES, "community_member"),
        ).exclude(id=actor.id)
    elif actor.role == "traditional_leader":
        candidates = User.objects.filter(
            community=actor.community, member_profile__is_town_leader=True,
        ).exclude(id=actor.id)
    else:
        raise ValidationError("Only a Community Admin, Family Head, or the Traditional Leader can manage users this way.")

    return [u for u in candidates.select_related("community") if can_restrict_features_for(actor, u)]


def set_disabled_features(*, target, features: list, actor):
    """The other half — actually applying the restriction, always re-checked against the same authority rule list_manageable_users used to decide who's even shown."""
    from accounts.permissions import can_restrict_features_for

    if not can_restrict_features_for(actor, target):
        raise ValidationError(f"'{actor.username}' isn't authorized to change what '{target.username}' can see.")
    allowed_features = restrictable_features_for(actor)
    unknown = set(features) - set(allowed_features.keys())
    if unknown:
        raise ValidationError(f"'{actor.username}' can't restrict the feature(s): {', '.join(sorted(unknown))}.")

    target.disabled_features = list(features)
    target.save(update_fields=["disabled_features"])

    from audit_log.services import record_event
    record_event(
        category="role", action="user_features_restricted", actor=actor, community=getattr(actor, "community", None),
        target_type="User", target_id=target.id, target_label=target.username,
        description=f"'{actor.username}' set '{target.username}''s disabled features to: {features or 'none'}.",
    )
    return target

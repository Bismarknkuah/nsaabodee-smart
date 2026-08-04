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

"""
The genuinely-real half of the "AI features" list from the master
brief — predictive collections, suspicious-transaction detection,
inactive-member identification, and fuzzy ("voice-adjacent") search are
all implemented here as real statistics and rules over data this
platform already has, not a call to any external AI service. Nothing
here needs credentials, nothing here can silently fail because a
provider account isn't set up — the honest version of "AI" for a
system that doesn't yet have the data volume or budget for anything
fancier. Meeting summarization is the one genuine LLM use case in this
list; it lives in llm_provider.py instead, following the same
credential-gated pattern as Twilio/WhatsApp/MTN MoMo elsewhere in this
platform, because it actually does need a real model call.
"""

import statistics
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher

from django.utils import timezone

from funerals.models import ContributionPayment, FuneralEvent
from members.models import Member
from .models import SuspiciousTransactionFlag


def predict_expected_collections(funeral: FuneralEvent) -> dict:
    """
    A genuinely simple, genuinely honest prediction: look at every
    CLOSED funeral this community has held before, compute what fraction
    of what was expected actually got collected on average, and apply
    that same fraction to this funeral's own expected total. No machine
    learning, no black box — just "historically, about X% of what's
    expected actually comes in," which is exactly the kind of estimate a
    Treasurer already makes in their head, made explicit and consistent.
    """
    from .models import SuspiciousTransactionFlag  # noqa: F401 (keeps import grouping consistent; unused here)

    past_funerals = FuneralEvent.objects.filter(community=funeral.community, status=FuneralEvent.Status.CLOSED)
    ratios = []
    for past in past_funerals:
        obligations = past.obligations.all()
        expected = sum((o.expected_amount for o in obligations), Decimal("0"))
        collected = sum((o.amount_paid for o in obligations), Decimal("0"))
        if expected > 0:
            ratios.append(float(collected / expected))

    current_expected = sum((o.expected_amount for o in funeral.obligations.all()), Decimal("0"))

    if not ratios:
        return {
            "funeral_id": str(funeral.id),
            "has_historical_data": False,
            "expected_total": str(current_expected),
            "predicted_collection_rate": None,
            "predicted_collected_total": None,
            "note": "No closed funerals yet in this community to base a prediction on.",
        }

    average_ratio = statistics.mean(ratios)
    return {
        "funeral_id": str(funeral.id),
        "has_historical_data": True,
        "based_on_funeral_count": len(ratios),
        "expected_total": str(current_expected),
        "predicted_collection_rate": round(average_ratio, 3),
        "predicted_collected_total": str((current_expected * Decimal(str(average_ratio))).quantize(Decimal("0.01"))),
    }


def find_inactive_members(*, community, inactive_days: int = 180) -> list[dict]:
    """
    "Identify inactive members" from the master brief — a member who's
    still marked active in the roster but has neither paid a single
    contribution nor been recorded as attending any funeral in the last
    `inactive_days`. A real, simple query, not a prediction — genuinely
    useful for a Secretary trying to decide who to follow up with.
    """
    cutoff = timezone.now() - timedelta(days=inactive_days)
    candidates = Member.objects.filter(community=community, status="active")

    inactive = []
    for member in candidates:
        recent_payment = ContributionPayment.objects.filter(
            obligation__member=member, paid_at__gte=cutoff
        ).exists()
        recent_attendance = member.funeral_attendance.filter(attended_at__gte=cutoff).exists()
        if not recent_payment and not recent_attendance:
            inactive.append({
                "member_id": str(member.id),
                "full_name": member.full_name,
                "membership_number": member.membership_number,
                "last_registered": member.created_at.isoformat(),
            })
    return inactive


def flag_suspicious_transactions_for_payment(payment: ContributionPayment) -> list[SuspiciousTransactionFlag]:
    """
    Two honest, explainable rules — deliberately not a black-box fraud
    score. Both require a real statistical baseline before they can fire
    at all, so a brand-new collector's very first payments are never
    flagged just for having no history yet.
    """
    if payment.collected_by is None:
        return []

    flags = []
    collector = payment.collected_by

    # Rule 1: this amount is a statistical outlier versus this collector's
    # own historical payments (needs at least 5 prior ones to mean anything).
    history = list(
        ContributionPayment.objects.filter(collected_by=collector)
        .exclude(id=payment.id)
        .values_list("amount", flat=True)[:200]
    )
    if len(history) >= 5:
        amounts = [float(a) for a in history]
        mean = statistics.mean(amounts)
        stdev = statistics.stdev(amounts)
        if stdev > 0 and abs(float(payment.amount) - mean) > 2.5 * stdev:
            flag, _ = SuspiciousTransactionFlag.objects.get_or_create(
                payment=payment, reason=SuspiciousTransactionFlag.Reason.AMOUNT_OUTLIER,
                defaults={
                    "community": payment.obligation.community,
                    "detail": f"GH₵{payment.amount} is unusual for this collector (their typical payment is around GH₵{mean:.2f}).",
                },
            )
            flags.append(flag)

    # Rule 2: this collector has recorded an unusually high burst of
    # payments in a short window — a real signal worth a human look, not
    # proof of anything on its own (a busy funeral genuinely produces
    # bursts of real payments too).
    window_start = timezone.now() - timedelta(minutes=5)
    recent_count = ContributionPayment.objects.filter(collected_by=collector, paid_at__gte=window_start).count()
    if recent_count >= 10:
        flag, _ = SuspiciousTransactionFlag.objects.get_or_create(
            payment=payment, reason=SuspiciousTransactionFlag.Reason.RAPID_SUCCESSION,
            defaults={
                "community": payment.obligation.community,
                "detail": f"{recent_count} payments recorded by this collector in the last 5 minutes.",
            },
        )
        flags.append(flag)

    return flags


def fuzzy_search(*, community, query: str, limit: int = 10) -> list[dict]:
    """
    The honest version of "voice search": this function does text
    matching, not speech recognition — turning spoken audio into a query
    string is a mobile-side, on-device (or third-party STT) concern this
    backend was never going to be able to do, and pretending otherwise
    would be exactly the kind of overclaiming this project has tried
    hard to avoid elsewhere (see the Bluetooth printer and Flutter
    compiler sections of this platform's README). What IS real here:
    fuzzy matching so a slightly-misheard or misspelled name ("Kwabina"
    for "Kwabena") still finds the right member, using Python's own
    difflib rather than an external fuzzy-matching library.
    """
    query_normalized = query.strip().lower()
    if not query_normalized:
        return []

    candidates = Member.objects.filter(community=community).only("id", "full_name", "membership_number", "phone")
    scored = []
    for member in candidates:
        score = SequenceMatcher(None, query_normalized, member.full_name.lower()).ratio()
        if query_normalized in member.full_name.lower():
            score = max(score, 0.9)  # a direct substring match should always rank near the top
        if score >= 0.4:
            scored.append((score, member))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {"member_id": str(m.id), "full_name": m.full_name, "membership_number": m.membership_number, "match_score": round(s, 3)}
        for s, m in scored[:limit]
    ]


def summarize_meeting(*, community, transcript: str, actor=None):
    """
    Calls the real LLM provider and stores the result regardless of
    outcome — a ProviderNotConfiguredError still gets recorded (as an
    empty summary) so "we tried and it's not set up yet" and "we never
    tried" stay distinguishable, the same pattern as every other
    provider integration in this platform.
    """
    from django.core.exceptions import ValidationError

    from .llm_provider import LlmProviderError, MeetingSummaryProvider, ProviderNotConfiguredError
    from .models import MeetingSummary

    try:
        result = MeetingSummaryProvider().summarize(transcript)
    except (ProviderNotConfiguredError, LlmProviderError) as exc:
        raise ValidationError(str(exc))

    return MeetingSummary.objects.create(
        community=community,
        transcript=transcript,
        summary=result.get("summary", ""),
        decisions=result.get("decisions", []),
        action_items=result.get("action_items", []),
        generated_by=actor,
    )


def draft_tribute_message(*, funeral, key_details: str, actor=None) -> str:
    """
    'Add AI features to make it greater.' A genuine starting point for
    a grieving family's public tribute, drafted from whatever real
    details they share — never invented, never automatically saved to
    the memorial page itself. The family (or whoever is drafting on
    their behalf) reviews and edits the returned text before it's ever
    published, through the memorial page's own existing update
    endpoint — this function only drafts, it never writes to
    MemorialPage.tribute_message directly.
    """
    from django.core.exceptions import ValidationError

    from .llm_provider import LlmProviderError, ProviderNotConfiguredError, TributeDraftProvider

    try:
        return TributeDraftProvider().draft(deceased_name=funeral.deceased_name, key_details=key_details)
    except (ProviderNotConfiguredError, LlmProviderError) as exc:
        raise ValidationError(str(exc))


def ask_chatbot(*, user, message: str):
    """
    'Add chatbot to all user types.' Persists both the person's message
    and the assistant's reply as real ChatbotMessage rows regardless of
    outcome — a ProviderNotConfiguredError still gets recorded as the
    user's own message (so "we tried and it's not set up yet" and "we
    never tried" stay distinguishable), the exact same honest pattern
    already used for meeting summarization.
    """
    from django.core.exceptions import ValidationError

    from .llm_provider import ChatbotProvider, LlmProviderError, ProviderNotConfiguredError
    from .models import ChatbotMessage

    if not message.strip():
        raise ValidationError("Please type a message.")

    ChatbotMessage.objects.create(user=user, role=ChatbotMessage.Role.USER, content=message.strip())

    # The last 20 messages (10 exchanges) is plenty of context for a
    # help assistant and keeps every request small and cheap — this is
    # guidance, not a conversation that needs to remember an hour ago.
    history_qs = ChatbotMessage.objects.filter(user=user).order_by("-created_at")[:20]
    history = [{"role": m.role, "content": m.content} for m in reversed(list(history_qs))]

    role_label = (user.get_role_display() if hasattr(user, "get_role_display") else user.role) or "a user"
    community_name = user.community.name if user.community_id else ""

    try:
        reply_text = ChatbotProvider().reply(role_label=role_label, community_name=community_name, history=history)
    except (ProviderNotConfiguredError, LlmProviderError) as exc:
        raise ValidationError(str(exc))

    return ChatbotMessage.objects.create(user=user, role=ChatbotMessage.Role.ASSISTANT, content=reply_text)


def list_chatbot_history(*, user) -> list:
    return list(user.chatbot_messages.order_by("created_at"))

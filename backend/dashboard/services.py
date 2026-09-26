"""
One dashboard endpoint, genuinely different data per role — built by
composing the services every other module already provides (reports,
members, funerals, contribution_rules, communication) rather than
duplicating their logic or faking numbers. Every section here is real
data a real query already proven correct elsewhere in this platform's
test suite; this module's own job is just deciding WHICH sections a
given role sees, and assembling them into one response.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import models as django_models
from django.utils import timezone

from accounts.models import Role
from families.models import Family
from funerals.models import FuneralEvent
from funerals import services as funeral_services
from members.models import Member
from notifications.models import Notification
from reports import services as report_services


def _active_funerals_summary(community, limit=5):
    funerals = FuneralEvent.objects.filter(community=community, status=FuneralEvent.Status.ACTIVE).select_related("deceased_family")[:limit]
    return [
        {
            "id": str(f.id),
            "deceased_name": f.deceased_name,
            "deceased_family_name": f.deceased_family.name,
            "collection_start_date": f.collection_start_date.isoformat(),
        }
        for f in funerals
    ]


def _collections_trend(community, days: int = 7, include_gift_cash: bool = True) -> list:
    """
    A real day-by-day trend for the dashboard's own chart.

    This used to call daily_report once per day (7 separate calls),
    each making its own several queries against ContributionPayment
    and GiftDonation — measured directly (see dashboard/tests/
    test_performance_diagnostic.py) at 56 queries against each table
    just for this one chart, the single largest contributor to a
    Community Admin's dashboard load requiring 119 queries in total.
    Rewritten to a single grouped-by-day query per table instead —
    the real, measured cause of "the system is freezing" for exactly
    the role that hits this dashboard section every day.
    """
    from django.db.models import Sum
    from django.db.models.functions import TruncDate
    from funerals.models import ContributionPayment
    from gifts.models import GiftDonation

    today = date.today()
    start = today - timedelta(days=days - 1)

    contrib_by_day = dict(
        ContributionPayment.objects.filter(obligation__community=community, paid_at__date__gte=start, paid_at__date__lte=today)
        .annotate(day=TruncDate("paid_at")).values("day").annotate(total=Sum("amount")).values_list("day", "total")
    )
    gift_by_day = {}
    if include_gift_cash:
        gift_by_day = dict(
            GiftDonation.objects.filter(community=community, given_at__date__gte=start, given_at__date__lte=today)
            .annotate(day=TruncDate("given_at")).values("day").annotate(total=Sum("amount_cash")).values_list("day", "total")
        )

    trend = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        total = (contrib_by_day.get(day) or Decimal("0")) + (gift_by_day.get(day) or Decimal("0"))
        trend.append({"date": day.isoformat(), "total": str(total)})
    return trend


def _community_overview(community, include_gift_cash: bool = True, include_activity_feed: bool = False):
    today = date.today()
    overview = {
        "active_funerals": FuneralEvent.objects.filter(community=community, status=FuneralEvent.Status.ACTIVE).count(),
        "active_member_count": Member.objects.filter(community=community, status="active").count(),
        "family_count": Family.objects.filter(community=community, status="active").count(),
        "defaulter_count": Member.objects.filter(community=community).exclude(defaulter_tier="none").count(),
        "today_collections": report_services.daily_report(community=community, on_date=today, include_gift_cash=include_gift_cash),
        "outstanding_members": report_services.outstanding_members_report(community=community),
        "recent_active_funerals": _active_funerals_summary(community),
        "collections_trend": _collections_trend(community, include_gift_cash=include_gift_cash),
        # 'The community executive should also have oversight analysis
        # based on their tasks.' Community-wide, matching who's actually
        # allowed to assign here — Community Admin, Chairman, Secretary
        # (COMMUNITY_WIDE_TASK_ROLES), and now Traditional Leader too.
        "task_summary": _community_task_summary(community),
    }
    if include_activity_feed:
        overview["activity_feed"] = _community_activity_feed(community)
    return overview


def _community_task_summary(community) -> dict:
    from tasks.models import MemberTask

    Status = MemberTask.Status
    return MemberTask.objects.filter(community=community).aggregate(
        pending=django_models.Count("id", filter=django_models.Q(status=Status.PENDING)),
        in_progress=django_models.Count("id", filter=django_models.Q(status=Status.IN_PROGRESS)),
        pending_approval=django_models.Count("id", filter=django_models.Q(status=Status.PENDING_APPROVAL)),
        done=django_models.Count("id", filter=django_models.Q(status=Status.DONE)),
        overdue=django_models.Count("id", filter=django_models.Q(due_date__lt=timezone.now().date()) & ~django_models.Q(status=Status.DONE)),
    )


def _community_activity_feed(community, limit: int = 30) -> list:
    """
    'The community chair is to have upper control over the community
    ledger and the system... have all activities analytics view.' The
    same real, chronological "who did what when" already built for
    Family Head (_family_activity_feed), scaled up to the whole
    community rather than one family — member registrations, payments
    collected, community expenses recorded, and completed tasks,
    merged into one time-ordered feed. Read-only, from data these
    roles already write in the ordinary course of their work.
    """
    from funeral_logistics.models import FuneralExpense
    from tasks.models import MemberTask
    from funerals.models import ContributionPayment

    entries = []

    for m in Member.objects.filter(community=community).select_related("registered_by", "family").order_by("-created_at")[:limit]:
        entries.append({
            "type": "member_registered", "at": m.created_at.isoformat(),
            "description": f"{m.full_name} registered" + (f" into {m.family.name}" if m.family_id else "") + (f" by {m.registered_by.username}" if m.registered_by_id else ""),
        })

    for p in (
        ContributionPayment.objects.filter(obligation__community=community)
        .exclude(method=ContributionPayment.Method.WALLET)
        .select_related("obligation__member", "obligation__funeral_event")
        .order_by("-paid_at")[:limit]
    ):
        entries.append({
            "type": "payment_recorded", "at": p.paid_at.isoformat(),
            "description": f"{p.obligation.member.full_name} paid {p.amount} toward {p.obligation.funeral_event.deceased_name}'s funeral" + (f" — collected by {p.collector_name}" if p.collector_name else ""),
        })

    for e in FuneralExpense.objects.filter(community=community).select_related("recorded_by", "funeral_event").order_by("-created_at")[:limit]:
        entries.append({
            "type": f"expense_{e.status}", "at": e.created_at.isoformat(),
            "description": f"{e.description} ({e.amount}) recorded for {e.funeral_event.deceased_name}'s funeral" + (f" by {e.recorded_by.username}" if e.recorded_by_id else "") + f" — {e.get_status_display().lower()}",
        })

    for t in MemberTask.objects.filter(community=community, status=MemberTask.Status.DONE).select_related("assigned_to").order_by("-updated_at")[:limit]:
        entries.append({"type": "task_completed", "at": t.updated_at.isoformat(), "description": f"{t.assigned_to.full_name} completed \"{t.title}\""})

    entries.sort(key=lambda e: e["at"], reverse=True)
    return entries[:limit]


def _traditional_leader_view(community):
    """
    'The Traditional Leader is the highest authority within that
    community... should be able to view the overall health and
    performance of the community... must NOT collect payments, edit
    financial records, modify transactions, manage individual members
    directly, or access sensitive personal financial information
    unless explicitly authorized by community policy.'

    Deliberately reuses the same community-wide data Chairman/Secretary
    see, with the SAME gift/donation exclusion the finance committee
    already has (include_gift_cash=False) — a strategic overview, not
    a window into individual donors' private giving.

    CRITICAL DEVIATION from _community_overview: outstanding_members
    is NEVER passed through as-is here. That report names individual
    members and their personal debt amounts — exactly the "sensitive
    personal financial information" the Traditional Leader must not
    see "unless explicitly authorized by community policy," which
    isn't the default. It's summarized into a count and a total here,
    the same aggregate-only treatment already given to Platform
    Admin's own platform-wide overview.
    """
    from tenants.models import Announcement
    overview = _community_overview(community, include_gift_cash=False)
    outstanding_detail = overview.pop("outstanding_members")
    overview["outstanding_summary"] = {
        "member_count": outstanding_detail["outstanding_member_count"],
        "total_owed": str(sum((Decimal(m["total_owed"]) for m in outstanding_detail["members"]), Decimal("0"))),
    }
    recent_announcements = list(
        Announcement.objects.filter(community=community, status=Announcement.Status.APPROVED)
        .values("id", "title", "submitted_at")[:5]
    )
    return {
        **overview,
        "recent_announcements": recent_announcements,
        "welfare_fund_summary": _community_welfare_fund_summary(community),
        "executive_performance_summary": _executive_performance_summary(community),
        "audit_summary": _community_audit_summary(community),
        "upcoming_meetings": _upcoming_meetings_summary(community),
        "family_compliance_comparison": _family_compliance_comparison(community),
        "growth_trend": _community_growth_trend(community),
        "expenses_month_to_date": report_services.expense_statement(
            community=community, start_date=date.today().replace(day=1), end_date=date.today(),
        ),
    }


def _community_welfare_fund_summary(community) -> dict:
    """'View community welfare fund statistics' — every family's fund, aggregated community-wide. Never a per-family or per-contributor breakdown, matching the same oversight-not-operational-detail principle."""
    from family_funds.models import FamilyFund, FamilyFundContribution

    funds = FamilyFund.objects.filter(family__community=community, is_active=True)
    contributions = FamilyFundContribution.objects.filter(fund__family__community=community)
    # A database SUM() aggregate doesn't preserve the source column's
    # decimal_places the way summing real Decimal objects in Python
    # does — explicitly quantized back to match (matches
    # FamilyFundContribution.amount's own decimal_places=2), so this
    # optimization doesn't silently change what every consumer of this
    # figure sees.
    total = (contributions.aggregate(total=django_models.Sum("amount"))["total"] or Decimal("0")).quantize(Decimal("0.01"))
    return {
        "active_fund_count": funds.count(),
        "total_contributions_ever": str(total),
        "contributing_family_count": funds.filter(contributions__isnull=False).distinct().count(),
    }


def _executive_performance_summary(community) -> dict:
    """'View executive performance summaries' — how active the community's own leadership has been, in aggregate. Never singles out one executive's individual record without their own dashboard context."""
    from datetime import timedelta as _timedelta
    from funerals.models import ContributionPayment
    from gifts.models import GiftDonation

    month_start = date.today().replace(day=1)
    return {
        "payments_recorded_this_month": ContributionPayment.objects.filter(
            obligation__community=community, paid_at__date__gte=month_start,
        ).count(),
        "gifts_recorded_this_month": GiftDonation.objects.filter(
            funeral_event__community=community, given_at__date__gte=month_start,
        ).count(),
        "active_collector_count": Member.objects.filter(
            community=community, linked_user__role="collector",
        ).count(),
    }


def _family_compliance_comparison(community) -> list:
    """
    'The Traditional Leader should have more analytics views, since he
    is the leader.' A genuinely new view, not just a bigger version of
    an existing one, but still aggregate-only, family-by-family, never
    an individual member's own name or specific debt (the same
    restraint applied everywhere else in this view). Only families with
    at least one currently-open obligation are included, so a family
    untouched by any active funeral doesn't show as "0% compliant."

    A single grouped query rather than one .count() plus a full
    row-by-row Python iteration PER family — the original version ran
    roughly 2×N queries and pulled every open obligation into memory
    for a community with N families; this runs one. "Paid" here means
    the same thing ContributionObligation.balance's own property does
    (amount_paid >= expected_amount), expressed as a database
    condition instead of a Python loop, since balance itself is a
    computed property, not a column the database could filter on
    directly.
    """
    from funerals.models import ContributionObligation

    rows = (
        ContributionObligation.objects
        .filter(member__family__community=community, member__family__status="active", funeral_event__status="active")
        .values("member__family__name")
        .annotate(
            member_obligation_count=django_models.Count("id"),
            paid_count=django_models.Count("id", filter=django_models.Q(amount_paid__gte=django_models.F("expected_amount"))),
        )
        .order_by("member__family__name")
    )
    result = [
        {
            "family_name": r["member__family__name"],
            "member_obligation_count": r["member_obligation_count"],
            "paid_count": r["paid_count"],
            "compliance_rate": round((r["paid_count"] / r["member_obligation_count"]) * 100),
        }
        for r in rows
    ]
    result.sort(key=lambda r: r["compliance_rate"])
    return result


def _community_growth_trend(community, months: int = 6) -> list:
    """
    A longer view than the existing 7-day collections trend — how the
    community's own membership has grown, month by month, since a
    "leader" checking in occasionally cares more about the trajectory
    over months than a single week's noise. Uses only the standard
    library for month arithmetic (no python-dateutil dependency).
    """
    today = date.today()
    rows = []
    year, month = today.year, today.month
    for i in range(months - 1, -1, -1):
        target_month = month - i
        target_year = year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        # Last day of target_month/target_year, via the "day 0 of next month" trick.
        if target_month == 12:
            month_end = date(target_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(target_year, target_month + 1, 1) - timedelta(days=1)
        count = Member.objects.filter(community=community, status="active", created_at__date__lte=month_end).count()
        rows.append({"month": f"{target_year:04d}-{target_month:02d}", "active_member_count": count})
    return rows


def _community_audit_summary(community) -> dict:
    """'View audit summaries' — how many governance actions of each kind happened recently, never the raw, detailed audit log itself (that stays Platform Admin / Community Admin only)."""
    from audit_log.models import AuditLogEntry
    from datetime import timedelta as _timedelta

    since = timezone.now() - _timedelta(days=30)
    recent = AuditLogEntry.objects.filter(community=community, created_at__gte=since)
    by_category = {}
    for category, count in recent.values_list("category").annotate(django_models.Count("id")):
        by_category[category] = count
    return {"period_days": 30, "total_events": recent.count(), "by_category": by_category}


def _upcoming_meetings_summary(community) -> list:
    """'View meeting schedules.' Community-wide meetings only — a family's own internal meeting is that family's business, not the Chief's oversight."""
    from communication.services import list_upcoming_meetings

    return list(
        list_upcoming_meetings(community)[:5].values("id", "title", "scheduled_for", "location")
    )


def _money_received_per_funeral(community, limit: int = 20, family=None) -> list:
    """
    One row per funeral — total expected, received, and still
    outstanding across the mandatory contribution ledger — newest
    first. Built on funerals.services.funeral_summary (already
    isolated per funeral, already tested) rather than the heavier
    funeral_closing_report, which also pulls expenses and gifts and
    is meant for one funeral at a time, not a list.

    `family` narrows this to only the funerals where the deceased is
    from that one family — 'the family finance officer only works
    when the funeral is from his family... they have to know
    anything about transactions for a funeral in their family.'
    """
    from funerals.services import funeral_summary

    rows = []
    funerals = FuneralEvent.objects.filter(community=community, status__in=[FuneralEvent.Status.ACTIVE, FuneralEvent.Status.CLOSED])
    if family is not None:
        funerals = funerals.filter(deceased_family=family)
    funerals = funerals.select_related("deceased_family").order_by("-collection_start_date")[:limit]
    for funeral in funerals:
        s = funeral_summary(funeral)
        buckets = (s["own_family"], s["general"], s["town_elder"])
        expected = sum((Decimal(b["expected_total"]) for b in buckets), Decimal("0"))
        received = sum((Decimal(b["collected_total"]) for b in buckets), Decimal("0"))
        rows.append({
            "funeral_id": str(funeral.id),
            "deceased_name": funeral.deceased_name,
            "family_name": funeral.deceased_family.name,
            "status": funeral.status,
            "expected_total": str(expected),
            "received_total": str(received),
            "outstanding_total": str(expected - received),
        })
    return rows


def _financial_officer_view(user, on_date=None):
    """
    'Treasurer sees all the financial aspects, and other executives
    also see what they are capable to.' Treasurer / Financial
    Secretary / Auditor used to get the exact same data — now
    genuinely different, matched to what each role can actually DO,
    the same principle already applied to the family-level financial
    roles above. "The funeral committee should have access to all the
    money paid except the donations": include_gift_cash is always
    False here, no role check needed, since none of the three roles
    that reach this function are the Community-Admin-tier oversight
    role that keeps full visibility.
    """
    from funerals.models import FuneralEvent as _FuneralEvent, PaymentReversal
    community = user.community
    on_date = on_date or date.today()
    month_start = on_date.replace(day=1)
    base = {
        "today": report_services.daily_report(community=community, on_date=on_date, include_gift_cash=False),
        "month_to_date": report_services.collections_report(community=community, start_date=month_start, end_date=on_date, include_gift_cash=False),
        "expenses_month_to_date": report_services.expense_statement(community=community, start_date=month_start, end_date=on_date),
        "outstanding_members": report_services.outstanding_members_report(community=community),
        # 'Make it transparent to the community treasurer to have data
        # of those who have paid.' The other half of outstanding_members
        # above — who HAS settled, not just who still owes. Deliberately
        # a separate key with its own, unchanged shape for
        # outstanding_members — nothing here alters what that key
        # already returns everywhere else it's used.
        "paid_members": report_services.members_payment_status_report(community=community)["paid_members"],
        "collections_trend": _collections_trend(community, include_gift_cash=False),
        "pending_funeral_openings_count": _FuneralEvent.objects.filter(
            community=community, status=_FuneralEvent.Status.PENDING_APPROVAL,
        ).count(),
        "pending_payment_reversals_count": PaymentReversal.objects.filter(
            payment__obligation__funeral_event__community=community, status=PaymentReversal.Status.PENDING,
        ).count(),
        # 'The community finance officer is always involved in any
        # funeral in the community, so they should know all the money
        # they received on each funeral.' Everything else in this view
        # is time-based (today, month-to-date) — this is the one
        # funeral-by-funeral picture, one row per funeral that has
        # actually collected anything (active or closed; pending
        # approval and cancelled funerals never had real obligations
        # to collect against, so they're deliberately left out).
        "money_received_per_funeral": _money_received_per_funeral(community),
    }

    # Treasurer and Financial Secretary can both actually REQUEST a
    # reversal (funerals.services.REVERSAL_REQUEST_ROLES) — the count
    # alone in `base` isn't enough to act on, so both get the real,
    # actionable list too.
    if user.role in ("treasurer", "financial_secretary"):
        base["pending_reversal_requests"] = list(
            PaymentReversal.objects.filter(
                payment__obligation__funeral_event__community=community, status=PaymentReversal.Status.PENDING,
            )
            .select_related("payment", "requested_by")
            .order_by("-requested_at")[:10]
            .values("id", "payment__amount", "reason", "requested_by__username", "requested_at")
        )

    # 'Other executives also see what they are capable to.' An Auditor
    # can never request or approve a reversal (funerals.services'
    # REVERSAL_REQUEST_ROLES and APPROVAL_ROLES both exclude them) and
    # never decides a suspicious-transaction flag either
    # (ai_features.views' partial_update check) — their actual
    # capability is REVIEW, so their dashboard reflects that: flag
    # activity and reversal history to examine, not a to-do list of
    # actions they're not authorized to take.
    if user.role == "auditor":
        from ai_features.models import SuspiciousTransactionFlag
        flags = SuspiciousTransactionFlag.objects.filter(community=community)
        base["suspicious_transaction_summary"] = {
            "unreviewed": flags.filter(review_status=SuspiciousTransactionFlag.ReviewStatus.UNREVIEWED).count(),
            "confirmed": flags.filter(review_status=SuspiciousTransactionFlag.ReviewStatus.CONFIRMED).count(),
            "dismissed": flags.filter(review_status=SuspiciousTransactionFlag.ReviewStatus.DISMISSED).count(),
        }
        base["recent_reversal_history"] = list(
            PaymentReversal.objects.filter(payment__obligation__funeral_event__community=community)
            .exclude(status=PaymentReversal.Status.PENDING)
            .select_related("payment")
            .order_by("-requested_at")[:10]
            .values("id", "payment__amount", "status", "reason", "requested_at")
        )

    return base


def _collector_view(user):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    outstanding = report_services.outstanding_members_report(community=user.community)
    return {
        "today_performance": report_services.collector_performance_report(collector=user, start_date=today, end_date=today),
        "week_performance": report_services.collector_performance_report(collector=user, start_date=week_start, end_date=today),
        # 'Whole office today' — every collector in the community
        # combined, not just this one's own tally, so a collector can
        # see the office's overall pace alongside their own personal
        # numbers above. collector=None is what makes this
        # community-wide rather than scoped to the caller.
        "whole_office_today": report_services.daily_report(community=user.community, on_date=today, collector=None),
        # 'Customers owing' — how many members still owe something on
        # any currently open funeral, community-wide, matched to the
        # members_to_follow_up list below rather than a separate count
        # that could ever disagree with it.
        "customers_owing_count": outstanding["outstanding_member_count"],
        "active_funerals": _active_funerals_summary(user.community),
        # "Collection analytics" — this collector's own daily pattern,
        # not the whole community's, matching the same trend-chart
        # treatment every other role's dashboard already gets.
        "collections_trend": _collector_collections_trend(user),
        # "Assigned members" — an honest interpretation given no
        # separate geographic/route assignment concept exists in this
        # platform: every member with a real, outstanding balance on a
        # currently open funeral, the genuine worklist a collector
        # actually needs, not a decorative roster.
        "members_to_follow_up": outstanding["members"][:20],
        # 'Collectors should also have a place in their dashboard
        # where they can see those who have paid and who have not
        # paid.' The other half — who's already settled, community
        # -wide, not just this collector's own personal tally.
        "paid_members": report_services.members_payment_status_report(community=user.community)["paid_members"][:20],
    }


def _family_arrears_officer_view(user, member):
    """
    'We have a family arrears collector who is responsible for
    managing and collecting his family arrears only... each family
    will have their own family arrears collector.' Deliberately its
    own function, not a member of _COLLECTOR_ROLES above — every
    community-wide query _collector_view makes (outstanding_members_report,
    _active_funerals_summary, members_payment_status_report with no
    family filter) would leak every other family's data to a role
    that should only ever see their own family's arrears. This
    collector's own performance figures still come from the same
    collector_performance_report every other collector role uses
    (already scoped by the `collector` argument, not by community),
    the only thing genuinely different here is the arrears/paid lists,
    which are family-scoped from the ground up.
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    family_arrears = _family_arrears_officer_family(member)
    if family_arrears is None:
        return {"message": "Not currently linked to a family — ask your Family Head to confirm your account is set up correctly."}

    arrears_entries = funeral_services.lookup_family_arrears(family=family_arrears)
    return {
        "family_id": str(family_arrears.id),
        "family_name": family_arrears.name,
        "today_performance": report_services.collector_performance_report(collector=user, start_date=today, end_date=today),
        "week_performance": report_services.collector_performance_report(collector=user, start_date=week_start, end_date=today),
        "customers_owing_count": len(arrears_entries),
        "collections_trend": _collector_collections_trend(user),
        # The genuine worklist — every family member with a real,
        # outstanding balance on a closed funeral, oldest debt first
        # within each, matching the same shape members_to_follow_up
        # already has on _collector_view so the frontend can reuse it.
        "members_to_follow_up": [
            {"member_id": e["member_id"], "member_name": e["member_name"], "total_owed": e["total_owed"], "funeral_count": len(e["obligations"])}
            for e in arrears_entries[:20]
        ],
        "paid_members": report_services.members_payment_status_report(community=user.community, family=family_arrears)["paid_members"][:20],
    }


def _family_arrears_officer_family(member):
    """member.family, or None if this account has no linked member or family at all — kept separate so the caller's None-check reads plainly rather than a chain of `and`s."""
    return member.family if member is not None and member.family_id else None


def _collector_collections_trend(user, days: int = 7) -> list:
    """Same fix as _collections_trend above, scoped to this collector's own payments — a single grouped query instead of one daily_report call per day."""
    from django.db.models import Sum
    from django.db.models.functions import TruncDate
    from funerals.models import ContributionPayment

    today = date.today()
    start = today - timedelta(days=days - 1)
    contrib_by_day = dict(
        ContributionPayment.objects.filter(obligation__community=user.community, collected_by=user, paid_at__date__gte=start, paid_at__date__lte=today)
        .annotate(day=TruncDate("paid_at")).values("day").annotate(total=Sum("amount")).values_list("day", "total")
    )
    trend = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        trend.append({"date": day.isoformat(), "total": str(contrib_by_day.get(day) or Decimal("0"))})
    return trend


def _family_role_view(user, member):
    """
    'All the executive user roles should have analytics views based on
    what they have access to... family head/secretary/treasurer should
    have analytics views of their family (only their family
    information). Family head has oversight of all family activities,
    the treasurer has oversight of all financial information and
    aspects.' Genuinely different data per role now, not the same
    section three times over — every figure here is this member's own
    family only, the same scoping already enforced everywhere else on
    this platform (search_members, the Family Fund page, etc.).
    """
    if member.family_id is None:
        return {"family": None, "message": "You're not currently assigned to a family."}
    from communication.services import list_upcoming_meetings
    from family_funds.services import family_financial_overview, funeral_expenditure_summary, funeral_expenses_for_family, funds_for_family, fund_summary
    from family_funds.models import FamilyFuneralExpense

    family = member.family
    is_head = user.role == "family_head"
    is_treasurer = user.role == "family_treasurer"
    is_secretary = user.role == "family_secretary"

    base = {
        "family_id": str(family.id),
        "family_name": family.name,
        "role": user.role,
        "statement": report_services.family_statement(family),
        "member_compliance": report_services.family_member_compliance_breakdown(family),
        "upcoming_meetings": list(
            list_upcoming_meetings(user.community, family=family)[:5]
            .values("id", "title", "scheduled_for", "location", "family_id")
        ),
        "my_desk_assignments": _my_active_desk_assignments(user),
    }

    # 'Family head has oversight of all family activities' AND 'the
    # treasurer has oversight of all financial information and
    # aspects' — both are this family's own finance officers (matches
    # family_funds' own is_family_finance_officer check exactly), so
    # both get the full financial picture and the pending approvals
    # that are actually theirs to decide.
    if is_head or is_treasurer:
        base["financial_overview"] = family_financial_overview(family)
        base["pending_expense_approvals"] = list(
            funeral_expenses_for_family(family).filter(status=FamilyFuneralExpense.Status.PENDING)
            .select_related("funeral_event", "recorded_by")
            .order_by("-date_purchased")[:10]
            .values("id", "item_name", "seller_name", "amount", "date_purchased", "funeral_event__deceased_name", "recorded_by__username")
        )

    # 'The family head needs more tasks features... check it and add
    # features that need to be added.' tasks_assigned_by_family_head
    # already existed in tasks/services.py but was never actually wired
    # into anything — a real, "built but never surfaced" gap. "Head of
    # each family should be able to register their members and assign
    # them a task" makes this genuinely the Head's own oversight, not
    # something Treasurer or Secretary need on their dashboard too.
    if is_head:
        from tasks.models import MemberTask
        from tasks.services import tasks_assigned_by_family_head

        family_tasks = tasks_assigned_by_family_head(family)
        _Status = MemberTask.Status
        base["task_summary"] = family_tasks.aggregate(
            pending=django_models.Count("id", filter=django_models.Q(status=_Status.PENDING)),
            in_progress=django_models.Count("id", filter=django_models.Q(status=_Status.IN_PROGRESS)),
            awaiting_your_approval=django_models.Count("id", filter=django_models.Q(status=_Status.PENDING_APPROVAL)),
            done=django_models.Count("id", filter=django_models.Q(status=_Status.DONE)),
            overdue=django_models.Count("id", filter=django_models.Q(due_date__lt=timezone.now().date()) & ~django_models.Q(status=_Status.DONE)),
        )
        base["tasks_awaiting_approval"] = list(
            family_tasks.filter(status=MemberTask.Status.PENDING_APPROVAL)
            .select_related("assigned_to")
            .order_by("-updated_at")[:10]
            .values("id", "title", "assigned_to__full_name", "due_date")
        )
        # 'Family head should have the analytics view of all the
        # activities in the family... all activities in the family or
        # family executive should submit to [the Family Head].' Every
        # summary above already exists as an aggregate (counts,
        # totals); this is the one thing genuinely missing — a real,
        # chronological "who did what when" across every kind of
        # family activity, not just one category at a time. Head-only:
        # this is oversight of everyone else's work, not something a
        # Secretary or Treasurer reviewing their own slice needs.
        base["activity_feed"] = _family_activity_feed(family)

    # The Treasurer specifically gets deeper detail than the Head does
    # — the fund-by-fund breakdown and the full approved/pending/
    # rejected split, not just the combined net-position figure.
    if is_treasurer:
        base["expenditure_summary"] = funeral_expenditure_summary(family)
        base["fund_summaries"] = [fund_summary(f) for f in funds_for_family(family)]
        # 'Each treasurer should have access to data of those who have
        # paid in his family and who haven't.' Scoped to this family
        # only — the same family_id filter members_payment_status_report
        # already supports, not a separate, parallel rule.
        base["payment_status"] = report_services.members_payment_status_report(community=user.community, family=family)
        # 'The family finance officer only works when the funeral is
        # from his family... they have to know anything about
        # transactions for a funeral in their family.' Only the
        # funerals where the deceased is from THIS family — never
        # another family's, the same family filter as everything else
        # in this block.
        base["money_received_per_funeral"] = _money_received_per_funeral(user.community, family=family)

    # 'The secretary who recorded it and the family head can both see
    # pending and rejected expenses too.' Not an approval queue for the
    # Secretary (they can't approve), but their own record-keeping
    # history — what they've submitted and its current status.
    if is_secretary:
        base["my_recorded_expenses"] = list(
            funeral_expenses_for_family(family).filter(recorded_by=user)
            .select_related("funeral_event")
            .order_by("-date_purchased")[:10]
            .values("id", "item_name", "amount", "status", "date_purchased", "funeral_event__deceased_name", "rejection_reason")
        )

    return base


def _family_activity_feed(family, limit: int = 30) -> list:
    """
    A real, chronological log of what's actually happened within one
    family — member registrations, payments collected, expenses
    recorded, and tasks completed — merged into one time-ordered list
    rather than four separate counts. Deliberately built here, not
    routed through the platform's own audit_log app: that log only
    ever records platform-level events (role changes, funeral-opening
    decisions, billing), never day-to-day activity like a registration
    or a payment, so it would not have delivered what was actually
    asked for. Every entry is read-only, drawn from data these roles
    already write in the ordinary course of their work — nothing new
    is logged anywhere, this only ever re-reads what's already there.
    """
    from family_funds.models import FamilyFuneralExpense
    from tasks.models import MemberTask

    entries = []

    for m in Member.objects.filter(family=family).select_related("registered_by").order_by("-created_at")[:limit]:
        entries.append({
            "type": "member_registered", "at": m.created_at.isoformat(),
            "description": f"{m.full_name} registered" + (f" by {m.registered_by.username}" if m.registered_by_id else ""),
        })

    from funerals.models import ContributionPayment
    for p in (
        ContributionPayment.objects.filter(obligation__member__family=family)
        .exclude(method=ContributionPayment.Method.WALLET)
        .select_related("obligation__member", "obligation__funeral_event")
        .order_by("-paid_at")[:limit]
    ):
        entries.append({
            "type": "payment_recorded", "at": p.paid_at.isoformat(),
            "description": f"{p.obligation.member.full_name} paid {p.amount} ({p.get_method_display()}) toward {p.obligation.funeral_event.deceased_name}'s funeral" + (f" — collected by {p.collector_name}" if p.collector_name else ""),
        })

    for e in FamilyFuneralExpense.objects.filter(family=family).select_related("recorded_by", "funeral_event").order_by("-created_at")[:limit]:
        entries.append({
            "type": f"expense_{e.status}", "at": e.created_at.isoformat(),
            "description": f"{e.item_name} ({e.amount}) recorded" + (f" by {e.recorded_by.username}" if e.recorded_by_id else "") + f" — {e.get_status_display().lower()}",
        })

    for t in MemberTask.objects.filter(assigned_to__family=family, status=MemberTask.Status.DONE).select_related("assigned_to").order_by("-updated_at")[:limit]:
        entries.append({"type": "task_completed", "at": t.updated_at.isoformat(), "description": f"{t.assigned_to.full_name} completed \"{t.title}\""})

    entries.sort(key=lambda e: e["at"], reverse=True)
    return entries[:limit]


def _my_active_desk_assignments(user) -> list:
    """
    'Apart from the collector, no user-role type should have front
    desk features to collect money' narrowed the Front Desk nav link
    to the Collector role only — but a Family Head/Secretary/Treasurer
    (or anyone else) who's genuinely been assigned and approved for a
    specific funeral's desk still needs a real way to reach that page.
    This is that way: a direct link on their own dashboard, the same
    pattern already used for a bereaved rep's own funeral and a family
    officer's own fund.
    """
    from funerals.models import FuneralDeskAssignment
    return list(
        FuneralDeskAssignment.objects.filter(user=user, is_active=True)
        .select_related("funeral_event")
        .values("funeral_event_id", "funeral_event__deceased_name", "desk_type")
    )


def _member_view(user, member):
    receipts = report_services.my_receipts(user=user)

    # "No executive user role should have the button to receive
    # donations" — since an executive can never legitimately be a
    # registered donation-account holder (see gifts.services.
    # register_donation_account_holder), this section is omitted
    # entirely for them here rather than always shown as zeros. This
    # matters specifically because of "Personal Dashboard": switching
    # context gives every executive this exact _member_view, so
    # without this check, every single executive would see a
    # "Donations Received" section on their own dashboard that could
    # never possibly be anything but empty.
    from accounts.models import EXECUTIVE_ROLES
    donations_received = None
    if user.role not in EXECUTIVE_ROLES:
        from gifts.services import donations_received_by_member
        donations_received = donations_received_by_member(member)

    family_info = None
    if member.family_id:
        family = member.family
        family_info = {
            "family_id": str(family.id),
            "family_name": family.name,
            "family_head_name": family.family_head.full_name if family.family_head_id else None,
            "family_secretary_name": family.family_secretary.full_name if family.family_secretary_id else None,
            "family_treasurer_name": family.family_treasurer.full_name if family.family_treasurer_id else None,
        }

    from communication import services as communication_services
    upcoming_meetings = list(
        communication_services.list_upcoming_meetings(member.community, family=member.family if member.family_id else None)[:5]
        .values("id", "title", "scheduled_for", "location", "family_id")
    )

    from welfare.models import WelfareObligation
    welfare_obligations = list(
        WelfareObligation.objects.filter(member=member, campaign__status="active")
        .select_related("campaign", "campaign__category")
        .values("id", "campaign__title", "campaign__category__name", "expected_amount", "amount_paid")[:10]
    )

    # 'The personal dashboard need the my receipt, donation, welfare
    # and contribution and task.' Real tasks assigned specifically to
    # THIS person — not committee-level task summaries, which live
    # under the Committee Positions section for those actually
    # organizing a funeral.
    from tasks.models import MemberTask
    my_tasks = list(
        MemberTask.objects.filter(assigned_to=member).exclude(status=MemberTask.Status.DONE)
        .select_related("funeral_event")
        .values("id", "title", "status", "due_date", "funeral_event__deceased_name")[:10]
    )

    return {
        "membership_number": member.membership_number,
        "defaulter_tier": member.defaulter_tier,
        "missed_contributions_count": member.missed_contributions_count,
        "recent_receipts": receipts["receipts"][:5],
        "active_funerals": _active_funerals_summary(member.community),
        # "Any amount paid should reflect on the person's dashboard... for
        # transparency and accountability" — only meaningfully non-empty
        # for members who've actually registered as a donation-account
        # holder for some funeral; otherwise this is just zeros.
        "donations_received": donations_received,
        "family_info": family_info,
        "upcoming_meetings": upcoming_meetings,
        "welfare_obligations": welfare_obligations,
        "my_tasks": my_tasks,
        "my_desk_assignments": _my_active_desk_assignments(user),
    }


def _notification_officer_view(community):
    from communication.models import DeliveryAttempt
    recent = Notification.objects.filter(community=community).order_by("-created_at")[:10]
    attempts = DeliveryAttempt.objects.filter(notification__community=community)
    return {
        "recent_notifications": [
            {"id": str(n.id), "message": n.message, "created_at": n.created_at.isoformat()} for n in recent
        ],
        "delivery_totals_by_status": {
            status: attempts.filter(status=status).count() for status, _ in DeliveryAttempt.Status.choices
        },
    }


def _guest_view(community):
    return {"active_funerals": _active_funerals_summary(community, limit=20)}


# Roles sharing the same view of the data — grouped explicitly rather
# than duplicated, so the mapping below stays a legible, one-line-per
# -role table of "who sees what."
_COMMUNITY_OVERVIEW_ROLES = {Role.COMMUNITY_ADMIN, Role.CHAIRMAN, Role.SECRETARY}
_FINANCIAL_OFFICER_ROLES = {Role.TREASURER, Role.FINANCIAL_SECRETARY, Role.AUDITOR}
_FAMILY_OFFICER_ROLES = {Role.FAMILY_HEAD, Role.FAMILY_SECRETARY, Role.FAMILY_TREASURER}
# 'All executive personal dashboard is the same as the community
# member dashboard since they are members.' Arrears Collector shares
# Collector's own dashboard and its collections/arrears data — the
# same underlying concept, just scoped differently.
#
# family_arrears_officer and town_elders_arrears_officer stay on the
# family/Town-Elders oversight dashboard, NOT here, even though their
# job is collecting rather than overseeing — _collector_view below
# queries community-wide (outstanding_members_report, active funerals
# across the whole community), and neither of those two roles should
# ever see anything beyond their own family or Town Elders group.
# Moving them here without first making _collector_view genuinely
# family-aware would leak community-wide data to a narrowly-scoped
# role — a real risk, not just a preference, so left for a dedicated
# pass rather than attempted under time pressure here.
_COLLECTOR_ROLES = {Role.COLLECTOR}  # the Arrears Collector has its own view below — two different jobs, two different dashboards
# Town-Elders-scoped executives share the Traditional Leader's own
# dashboard, the Town Elders group's equivalent of the family officer
# roles sharing the Family Head's.
_TOWN_ELDERS_OFFICER_ROLES = {Role.TOWN_ELDERS_ARREARS_OFFICER}
# 'The registration officer is not allowed to see the financial oversight; his
# responsibility is to manage the community's information.' All three
# registration roles get their own member-information dashboard and never the
# Chief's, community's, or family's financial overview.
_REGISTRATION_ROLES = {Role.TOWN_REGISTRATION_OFFICER, Role.COMMUNITY_REGISTRATION_DESK, Role.FAMILY_REGISTRATION_OFFICER}


def _registration_officer_view(user) -> dict:
    """
    Member information only — no collections, no ledgers, no expenses.
    The registry analytics already scope themselves to the role's
    jurisdiction (community-wide, Town Elders, or own family).
    """
    from datetime import date
    from members.services import member_registry_analytics
    today = date.today()
    mine = Member.objects.filter(community=user.community, registered_by=user)
    return {
        "registry": member_registry_analytics(actor=user),
        "my_registrations_total": mine.count(),
        "my_registrations_this_month": mine.filter(created_at__year=today.year, created_at__month=today.month).count(),
        "registers_town_elders_only": user.role == Role.TOWN_REGISTRATION_OFFICER,
    }


def _arrears_collector_view(user) -> dict:
    """
    'The arrears collector should have more options.' Built around
    closed-funeral debt, not today's open funeral: the community-wide
    worklist (largest total first), totals, this officer's own
    collections, and the trend.
    """
    from datetime import date, timedelta
    from funerals.services import lookup_community_arrears
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    worklist = lookup_community_arrears(community=user.community)
    total = sum((Decimal(r["total_owed"]) for r in worklist), Decimal("0"))
    return {
        "members_owing_count": len(worklist),
        "total_arrears_outstanding": str(total),
        "closed_funerals_with_arrears": len({f["funeral_id"] for r in worklist for f in r["funerals"]}),
        "largest_single_debt": worklist[0]["total_owed"] if worklist else "0",
        "worklist": worklist[:50],
        "today_performance": report_services.collector_performance_report(collector=user, start_date=today, end_date=today),
        "week_performance": report_services.collector_performance_report(collector=user, start_date=week_start, end_date=today),
        "collections_trend": _collections_trend(user.community, include_gift_cash=False),
    }


def build_dashboard(user) -> dict:
    community = user.community
    member = getattr(user, "member_profile", None)

    if user.is_superuser or user.role == Role.PLATFORM_ADMIN:
        from tenants.models import Announcement, Community, PlanInterestSubmission, PlatformBillingRecord, SubscriptionPlan
        from accounts.models import User
        from django.db.models import Q
        from tenants.services import communities_needing_subscription_attention
        from members.models import Member
        from funerals.models import FuneralEvent as _FuneralEvent
        from support.models import SupportTicket

        active_communities = Community.objects.filter(is_active=True)
        unpaid_records = PlatformBillingRecord.objects.filter(status=PlatformBillingRecord.Status.UNPAID)
        return {
            "role": user.role or "platform_admin",
            "sections": {
                "platform_overview": {
                    "community_count": active_communities.count(),
                    "permanent_community_count": active_communities.filter(access_expires_at__isnull=True).count(),
                    "temporary_community_count": active_communities.filter(access_expires_at__isnull=False).count(),
                    "total_members_platform_wide": Member.objects.filter(community__is_active=True, status="active").count(),
                    "total_active_funerals_platform_wide": _FuneralEvent.objects.filter(
                        community__is_active=True, status=_FuneralEvent.Status.ACTIVE,
                    ).count(),
                    "pending_announcements_count": Announcement.objects.filter(status=Announcement.Status.PENDING).count(),
                    "uncontacted_plan_interest_count": PlanInterestSubmission.objects.filter(contacted=False).count(),
                    # 'The platform admin should have more control to manage
                    # all the community platform.' All three of these were
                    # already fully built and working — sending a reminder,
                    # tracking billing, handling support — but invisible
                    # from this landing page, so a Platform Admin had no way
                    # to actually notice any of them needed attention.
                    "communities_needing_subscription_attention_count": communities_needing_subscription_attention().count(),
                    "unpaid_billing_total": str(sum((r.amount for r in unpaid_records), Decimal("0"))),
                    "unpaid_billing_count": unpaid_records.count(),
                    "open_support_ticket_count": SupportTicket.objects.filter(status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS]).count(),
                    "communities": list(active_communities.values("id", "name", "slug")[:50]),
                    # The platform-console overview, modeled on the
                    # reference layout: KPI tiles up top, then
                    # "subscriptions by status", "communities by plan",
                    # and "recent registrations" side by side.
                    "total_users_platform_wide": User.objects.filter(community__is_active=True, is_active=True).count(),
                    "subscription_revenue_total": str(sum((r.amount for r in PlatformBillingRecord.objects.filter(status=PlatformBillingRecord.Status.PAID)), Decimal("0"))),
                    "subscriptions_by_status": {
                        "active": active_communities.filter(Q(access_expires_at__isnull=True) | Q(access_expires_at__gt=timezone.now())).count(),
                        "expired": active_communities.filter(access_expires_at__isnull=False, access_expires_at__lte=timezone.now()).count(),
                        "suspended": Community.objects.filter(is_active=False).count(),
                    },
                    "communities_by_plan": [
                        {"plan_code": p.code, "plan_name": p.name, "community_count": p.communities.filter(is_active=True).count()}
                        for p in SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order")
                    ],
                    "recent_registrations": list(
                        Community.objects.order_by("-created_at")[:8].values("id", "name", "slug", "is_active", "created_at", "subscription_plan__name")
                    ),
                }
            },
        }

    if community is None:
        return {"role": user.role, "sections": {}}

    # "When using Personal Dashboard" — an executive who has switched
    # context sees exactly what a Community Member sees, regardless of
    # their actual stored role, which never changes here. This is the
    # ONE place "Personal Dashboard" means something different from
    # just being a Community Member: everyone else already always sees
    # their normal dashboard, since active_context only ever moves off
    # "executive" for a role in EXECUTIVE_ROLES in the first place.
    #
    # "Personal account is the same community member dashboard, and
    # they are not allowed to see funeral fund or execute task." Fixed
    # here: this branch used to also inject family_fund_overview for
    # anyone who happened to be a Family Head/Secretary/Treasurer —
    # exactly the funeral-fund visibility this context is supposed to
    # hide. member_overview alone is the whole point of "personal."
    if not user.is_superuser and user.active_context == "personal" and member:
        return {"role": user.role, "sections": {"member_overview": _member_view(user, member)}}

    if user.role == Role.ARREARS_COLLECTOR:
        sections = {"arrears_collector_overview": _arrears_collector_view(user)}
    elif user.role in _REGISTRATION_ROLES:
        sections = {"registration_overview": _registration_officer_view(user)}
    elif user.role == Role.TRADITIONAL_LEADER or user.role in _TOWN_ELDERS_OFFICER_ROLES:
        sections = {"traditional_leader_overview": _traditional_leader_view(community)}
    elif user.role in _COMMUNITY_OVERVIEW_ROLES:
        # Community Admin keeps platform-level oversight; Chairman and
        # Secretary — same tier as the rest of the funeral committee —
        # get everything except the donation figures.
        include_gift_cash = user.is_superuser or user.role == Role.COMMUNITY_ADMIN
        # 'The community chair is to have upper control over the
        # community ledger and the system... his role is to approve
        # community request and have all activities analytics view.'
        # Chairman-specific, alongside Community Admin (who already
        # gets more than Chairman/Secretary via include_gift_cash
        # above) — Secretary doesn't get this, the same way Family
        # Treasurer/Secretary don't get the family activity feed
        # either, that oversight belongs to the one role actually
        # reviewing everyone else's work.
        include_activity_feed = user.is_superuser or user.role in (Role.COMMUNITY_ADMIN, Role.CHAIRMAN)
        sections = {"community_overview": _community_overview(community, include_gift_cash=include_gift_cash, include_activity_feed=include_activity_feed)}
    elif user.role in _FINANCIAL_OFFICER_ROLES:
        sections = {"financial_overview": _financial_officer_view(user)}
    elif user.role in _COLLECTOR_ROLES:
        sections = {"collector_performance": _collector_view(user)}
    elif user.role == Role.FAMILY_ARREARS_OFFICER:
        sections = {"family_arrears_officer_performance": _family_arrears_officer_view(user, member)}
    elif user.role in _FAMILY_OFFICER_ROLES:
        sections = {"family_overview": _family_role_view(user, member) if member else {"family": None}}
    elif user.role == Role.NOTIFICATION_OFFICER:
        sections = {"notifications_overview": _notification_officer_view(community)}
    elif user.role == Role.BEREAVED_REP:
        # Whichever currently-active funeral(s) this person's own family
        # is the deceased's family for — real analytics and oversight,
        # not just a static list, since a family can genuinely have
        # more than one active funeral at once (a second bereavement
        # while the first hasn't closed yet) and this role represents
        # the family, not any one specific funeral.
        funerals = FuneralEvent.objects.filter(
            community=community, status=FuneralEvent.Status.ACTIVE,
            deceased_family=member.family if member else None,
        )
        from funeral_logistics.services import funeral_financial_overview
        from funerals.services import funeral_summary
        funeral_entries = []
        total_expected = Decimal("0")
        total_collected = Decimal("0")
        for f in funerals:
            overview = funeral_financial_overview(f)
            summary = funeral_summary(f)
            expected = summary["own_family"]["expected_total"] + summary["general"]["expected_total"]
            collected = summary["own_family"]["collected_total"] + summary["general"]["collected_total"]
            outstanding_count = summary["own_family"]["partial_count"] + summary["own_family"]["unpaid_count"] + summary["general"]["partial_count"] + summary["general"]["unpaid_count"]
            total_expected += expected
            total_collected += collected
            funeral_entries.append({
                "funeral_id": str(f.id), "deceased_name": f.deceased_name,
                "overview": overview,
                "expected_total": str(expected), "collected_total": str(collected),
                "collection_progress_pct": round(float(collected / expected * 100), 1) if expected > 0 else 0,
                "outstanding_count": outstanding_count,
            })
        sections = {
            "bereaved_funerals": funeral_entries,
            "family_summary": {
                "active_funeral_count": len(funeral_entries),
                "total_expected": str(total_expected),
                "total_collected": str(total_collected),
                "member_compliance": report_services.family_member_compliance_breakdown(member.family) if member and member.family_id else [],
            },
        }
    elif user.role == Role.COMMUNITY_MEMBER:
        sections = {"member_overview": _member_view(user, member) if member else {"message": "No member profile linked yet."}}
    else:  # Guest and anything else unrecognized: the safest, most public-facing default
        sections = {"public_overview": _guest_view(community)}

    # Additive, not exclusive — "abusuapanin can assign any of his
    # members to use like secretary and finance dashboards." Whoever
    # that assigned member is (regardless of their platform-wide role,
    # which never changes) sees this section ALONGSIDE whatever their
    # base role already shows. A Community Admin who happens to also be
    # a family's own treasurer sees both community_overview AND this.
    family_fund_section = _family_fund_overview_for_officer(member)
    if family_fund_section is not None:
        sections["family_fund_overview"] = family_fund_section

    # Same additive principle: committee membership is orthogonal to
    # platform-wide role — an ordinary Community Member appointed to a
    # funeral's committee sees this alongside their normal dashboard,
    # not instead of it. "Committee members should only access
    # information related to the funeral event they are assigned to" —
    # each entry here is scoped to exactly one funeral.
    committee_section = _committee_positions_overview(member)
    if committee_section:
        sections["committee_positions"] = committee_section

    return {"role": user.role, "sections": sections}


def _committee_positions_overview(member) -> list:
    """
    'Manage funeral planning activities... View contribution summaries.
    Monitor expenses... Track event progress. View attendance.' Every
    ACTIVE funeral this member holds a committee position for, each
    with a real, working snapshot scoped to exactly that one funeral —
    never another funeral's data, matching "committee members should
    only access information related to the funeral event they are
    assigned to."
    """
    if member is None:
        return []
    from funerals.models import FuneralCommitteePosition, FuneralEvent
    from funeral_logistics.models import FuneralAttendance
    from funeral_logistics.services import funeral_financial_overview
    from tasks.models import MemberTask
    from communication import services as communication_services

    positions = FuneralCommitteePosition.objects.filter(
        member=member, funeral_event__status=FuneralEvent.Status.ACTIVE,
    ).select_related("funeral_event")

    result = []
    for position in positions:
        funeral = position.funeral_event
        task_counts = MemberTask.objects.filter(funeral_event=funeral).aggregate(
            total=django_models.Count("id"),
            done=django_models.Count("id", filter=django_models.Q(status=MemberTask.Status.DONE)),
            pending_approval=django_models.Count("id", filter=django_models.Q(status=MemberTask.Status.PENDING_APPROVAL)),
        )
        result.append({
            "funeral_id": str(funeral.id),
            "deceased_name": funeral.deceased_name,
            "your_title": position.title,
            "task_summary": task_counts,
            "contribution_summary": funeral_financial_overview(funeral),
            "attendance_count": FuneralAttendance.objects.filter(funeral_event=funeral).count(),
            "upcoming_meetings": list(
                communication_services.list_upcoming_meetings(member.community, funeral=funeral)[:5]
                .values("id", "title", "scheduled_for", "location")
            ),
        })
    return result


def _family_fund_overview_for_officer(member):
    if member is None:
        return None
    from django.db.models import Q
    from family_funds.services import funds_for_family, fund_summary

    officer_families = Family.objects.filter(
        Q(family_head_id=member.id) | Q(family_secretary_id=member.id) | Q(family_treasurer_id=member.id)
    ).distinct()
    if not officer_families:
        return None

    result = []
    for family in officer_families:
        funds = funds_for_family(family)
        result.append({
            "family_id": str(family.id),
            "family_name": family.name,
            "your_role": (
                "head" if family.family_head_id == member.id else
                "secretary" if family.family_secretary_id == member.id else "treasurer"
            ),
            "funds": [fund_summary(f) for f in funds],
        })
    return result

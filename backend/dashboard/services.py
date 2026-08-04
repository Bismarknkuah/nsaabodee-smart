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


def _community_overview(community, include_gift_cash: bool = True):
    today = date.today()
    return {
        "active_funerals": FuneralEvent.objects.filter(community=community, status=FuneralEvent.Status.ACTIVE).count(),
        "active_member_count": Member.objects.filter(community=community, status="active").count(),
        "family_count": Family.objects.filter(community=community, status="active").count(),
        "defaulter_count": Member.objects.filter(community=community).exclude(defaulter_tier="none").count(),
        "today_collections": report_services.daily_report(community=community, on_date=today, include_gift_cash=include_gift_cash),
        "outstanding_members": report_services.outstanding_members_report(community=community),
        "recent_active_funerals": _active_funerals_summary(community),
        "collections_trend": _collections_trend(community, include_gift_cash=include_gift_cash),
    }


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
        "expenses_month_to_date": report_services.expense_statement(
            community=community, start_date=date.today().replace(day=1), end_date=date.today(),
        ),
    }


def _community_welfare_fund_summary(community) -> dict:
    """'View community welfare fund statistics' — every family's fund, aggregated community-wide. Never a per-family or per-contributor breakdown, matching the same oversight-not-operational-detail principle."""
    from family_funds.models import FamilyFund, FamilyFundContribution

    funds = FamilyFund.objects.filter(family__community=community, is_active=True)
    contributions = FamilyFundContribution.objects.filter(fund__family__community=community)
    return {
        "active_fund_count": funds.count(),
        "total_contributions_ever": str(sum((c.amount for c in contributions), Decimal("0"))),
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


def _financial_officer_view(community, on_date=None):
    """
    Treasurer / Financial Secretary / Auditor — "the funeral committee
    should have access to all the money paid except the donations":
    include_gift_cash is always False here, no role check needed, since
    none of the three roles that reach this function are the
    Community-Admin-tier oversight role that keeps full visibility.
    """
    from funerals.models import FuneralEvent as _FuneralEvent, PaymentReversal
    on_date = on_date or date.today()
    month_start = on_date.replace(day=1)
    return {
        "today": report_services.daily_report(community=community, on_date=on_date, include_gift_cash=False),
        "month_to_date": report_services.collections_report(community=community, start_date=month_start, end_date=on_date, include_gift_cash=False),
        "expenses_month_to_date": report_services.expense_statement(community=community, start_date=month_start, end_date=on_date),
        "outstanding_members": report_services.outstanding_members_report(community=community),
        "collections_trend": _collections_trend(community, include_gift_cash=False),
        # "Pending approvals" — real counts from the two approval
        # workflows this platform already has, not a placeholder.
        "pending_funeral_openings_count": _FuneralEvent.objects.filter(
            community=community, status=_FuneralEvent.Status.PENDING_APPROVAL,
        ).count(),
        "pending_payment_reversals_count": PaymentReversal.objects.filter(
            payment__obligation__funeral_event__community=community, status=PaymentReversal.Status.PENDING,
        ).count(),
    }


def _collector_view(user):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    outstanding = report_services.outstanding_members_report(community=user.community)
    return {
        "today_performance": report_services.collector_performance_report(collector=user, start_date=today, end_date=today),
        "week_performance": report_services.collector_performance_report(collector=user, start_date=week_start, end_date=today),
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
    }


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


def _family_role_view(member):
    if member.family_id is None:
        return {"family": None, "message": "You're not currently assigned to a family."}
    from communication.services import list_upcoming_meetings

    return {
        "family_name": member.family.name,
        "statement": report_services.family_statement(member.family),
        "member_compliance": report_services.family_member_compliance_breakdown(member.family),
        "upcoming_meetings": list(
            list_upcoming_meetings(member.community, family=member.family)[:5]
            .values("id", "title", "scheduled_for", "location", "family_id")
        ),
    }


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


def build_dashboard(user) -> dict:
    community = user.community
    member = getattr(user, "member_profile", None)

    if user.is_superuser or user.role == Role.PLATFORM_ADMIN:
        from tenants.models import Announcement, Community, PlanInterestSubmission
        from members.models import Member
        from funerals.models import FuneralEvent as _FuneralEvent

        active_communities = Community.objects.filter(is_active=True)
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
                    "communities": list(active_communities.values("id", "name", "slug")[:50]),
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
    if not user.is_superuser and user.active_context == "personal" and member:
        sections = {"member_overview": _member_view(user, member)}
        family_fund_section = _family_fund_overview_for_officer(member)
        if family_fund_section is not None:
            sections["family_fund_overview"] = family_fund_section
        return {"role": user.role, "sections": sections}

    if user.role == Role.TRADITIONAL_LEADER:
        sections = {"traditional_leader_overview": _traditional_leader_view(community)}
    elif user.role in _COMMUNITY_OVERVIEW_ROLES:
        # Community Admin keeps platform-level oversight; Chairman and
        # Secretary — same tier as the rest of the funeral committee —
        # get everything except the donation figures.
        include_gift_cash = user.is_superuser or user.role == Role.COMMUNITY_ADMIN
        sections = {"community_overview": _community_overview(community, include_gift_cash=include_gift_cash)}
    elif user.role in _FINANCIAL_OFFICER_ROLES:
        sections = {"financial_overview": _financial_officer_view(community)}
    elif user.role == Role.COLLECTOR:
        sections = {"collector_performance": _collector_view(user)}
    elif user.role in _FAMILY_OFFICER_ROLES:
        sections = {"family_overview": _family_role_view(member) if member else {"family": None}}
    elif user.role == Role.NOTIFICATION_OFFICER:
        sections = {"notifications_overview": _notification_officer_view(community)}
    elif user.role == Role.BEREAVED_REP:
        # Whichever currently-active funeral(s) this person's own family
        # is the deceased's family for — the financial picture a
        # bereaved family representative actually needs to see.
        funerals = FuneralEvent.objects.filter(
            community=community, status=FuneralEvent.Status.ACTIVE,
            deceased_family=member.family if member else None,
        )
        from funeral_logistics.services import funeral_financial_overview
        sections = {
            "bereaved_funerals": [
                {"funeral_id": str(f.id), "deceased_name": f.deceased_name, "overview": funeral_financial_overview(f)}
                for f in funerals
            ]
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

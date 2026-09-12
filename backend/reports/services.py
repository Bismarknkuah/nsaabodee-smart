"""
Read-only reporting over data that already exists across every ledger
built so far. Nothing here writes anything, and nothing here merges the
underlying ledgers' bookkeeping — a "Cash Summary" report legitimately
adds contribution cash and gift cash together because a collector
physically reconciling a cash box at the end of the day doesn't care
which ledger a note came from; that is a different question from "does
this obligation's balance include gift money", which the answer is
always no (see funerals/services.py and gifts/services.py — those never
touch each other). A report is a view over money already recorded; it is
not itself where the recording happens.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from funerals.models import ContributionPayment, FuneralEvent
from funeral_logistics.models import FuneralExpense
from gifts.models import GiftDonation
from members.models import Member


def _payment_method_breakdown(cash_amount, momo_amount, bank_amount, other_amount):
    return {
        "cash": str(cash_amount or Decimal("0")),
        "mobile_money": str(momo_amount or Decimal("0")),
        "bank": str(bank_amount or Decimal("0")),
        "other": str(other_amount or Decimal("0")),
    }


def _method_totals(queryset, method_field="method", amount_field="amount"):
    totals = {}
    for method_value in ["cash", "mobile_money", "bank", "other"]:
        totals[method_value] = queryset.filter(**{method_field: method_value}).aggregate(
            total=Sum(amount_field)
        )["total"] or Decimal("0")
    return totals


def mark_contribution_receipt_printed(*, payment: ContributionPayment):
    """
    Called by the collecting device once its thermal printer confirms the
    physical receipt actually printed. Idempotent: calling this twice (a
    collector taps "print" again because they're not sure it worked) just
    updates the same timestamp, never creates a duplicate record — there
    is nothing here for a duplicate to corrupt.
    """
    from django.utils import timezone
    payment.printed_at = timezone.now()
    payment.save(update_fields=["printed_at"])
    return payment


def mark_gift_receipt_printed(*, donation: GiftDonation):
    from django.utils import timezone
    donation.printed_at = timezone.now()
    donation.save(update_fields=["printed_at"])
    return donation


def generate_payment_qr_code_base64(payment: ContributionPayment) -> str:
    """Same reusable qrcode.make(...) -> PNG -> base64 pattern already used for Member.qr_payload — see members.services.generate_qr_code_base64."""
    import base64
    import io
    import qrcode

    img = qrcode.make(payment.qr_payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def verify_receipt(*, payment: ContributionPayment) -> dict:
    """
    'All receipt printed should have the QR scanner so when they scan
    it should confirm the amount they paid and who received the pay, I
    mean the collector.' What scanning a printed receipt's QR code
    actually returns — exactly those two facts, plus enough context
    (whose funeral, when) to be a genuine confirmation rather than a
    bare number.
    """
    return {
        "payment_id": str(payment.id),
        "receipt_number": payment.receipt_number,
        "amount": str(payment.amount),
        "method": payment.method,
        "collector_name": payment.collector_name,
        "member_name": payment.obligation.member.full_name,
        "deceased_name": payment.obligation.funeral_event.deceased_name,
        "paid_at": payment.paid_at.isoformat(),
    }


def unprinted_receipts(*, community) -> dict:
    """
    Every CASH payment or gift that has no confirmed physical printout
    yet — the operational answer to "everyone who pays must get a
    receipt": this is the list of people who technically don't have one
    in hand yet, so a supervisor can chase them down and reprint. Only
    cash entries are listed here, since electronic-method payments were
    never meant to be printed in the first place (see
    reports.receipts.py's delivery_channel) — an unprinted momo receipt
    isn't a problem to fix, it's the correct, expected state.
    """
    unprinted_payments = ContributionPayment.objects.filter(
        obligation__community=community, method="cash", printed_at__isnull=True
    ).select_related("obligation__member", "obligation__funeral_event")
    unprinted_gifts = GiftDonation.objects.filter(
        community=community, payment_method="cash", printed_at__isnull=True
    ).select_related("funeral_event")

    return {
        "unprinted_contribution_payments": [
            {
                "payment_id": str(p.id),
                "receipt_number": p.receipt_number,
                "member_name": p.obligation.member.full_name,
                "amount": str(p.amount),
                "funeral_deceased_name": p.obligation.funeral_event.deceased_name,
                "paid_at": p.paid_at.isoformat(),
            }
            for p in unprinted_payments
        ],
        "unprinted_gift_donations": [
            {
                "donation_id": str(d.id),
                "receipt_number": d.receipt_number,
                "donor_name": d.donor_name,
                "amount": str(d.amount_cash),
                "funeral_deceased_name": d.funeral_event.deceased_name,
                "given_at": d.given_at.isoformat(),
            }
            for d in unprinted_gifts
        ],
    }


def collections_report(*, community, start_date: date, end_date: date, collector=None, include_gift_cash: bool = True) -> dict:
    """
    Powers the Daily/Weekly/Monthly/Annual statements: every mandatory
    contribution payment AND every gift's cash portion collected in the
    window, broken down by payment method, optionally scoped to one
    collector (this is what a collector's "Today's Collections" / "Cash
    Summary" / "MoMo Summary" dashboard tiles are reading from).

    `include_gift_cash` exists specifically for "the funeral committee
    should have access to all the money paid except the donations" —
    the community-wide aggregate reports the committee (Treasurer,
    Chairman, Secretary, Auditor) sees are generated with this False
    (see reports/views.py and dashboard/services.py, which decide this
    per-role), while a COLLECTOR'S OWN performance report still includes
    it: that's an operational cash-reconciliation need (a collector
    physically holding both contribution and gift cash needs their own
    total), not a governance view into total community donations.
    """
    payments = ContributionPayment.objects.filter(
        obligation__community=community, paid_at__date__gte=start_date, paid_at__date__lte=end_date,
    )
    donations = GiftDonation.objects.filter(
        community=community, given_at__date__gte=start_date, given_at__date__lte=end_date,
    )
    if collector is not None:
        payments = payments.filter(collected_by=collector)
        donations = donations.filter(collected_by=collector)

    contribution_totals = _method_totals(payments, method_field="method")

    if include_gift_cash:
        # Gifts with amount_cash=0 (item-only) correctly contribute nothing to a method total.
        gift_totals = _method_totals(donations, method_field="payment_method", amount_field="amount_cash")
        gift_section = {
            "count": donations.exclude(amount_cash=0).count(),
            "total": str(donations.aggregate(total=Sum("amount_cash"))["total"] or Decimal("0")),
            "by_method": {k: str(v) for k, v in gift_totals.items()},
        }
        combined = {
            method: str(contribution_totals[method] + gift_totals[method])
            for method in ["cash", "mobile_money", "bank", "other"]
        }
        receipts_issued = payments.count() + donations.count()
    else:
        gift_section = None
        combined = {method: str(contribution_totals[method]) for method in ["cash", "mobile_money", "bank", "other"]}
        receipts_issued = payments.count()

    result = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "collector_id": str(collector.id) if collector else None,
        "contributions": {
            "count": payments.count(),
            "total": str(payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")),
            "by_method": {k: str(v) for k, v in contribution_totals.items()},
        },
        "combined_cash_position_by_method": combined,
        "receipts_issued": receipts_issued,
    }
    if gift_section is not None:
        result["gift_cash"] = gift_section
    return result


def daily_report(*, community, on_date: date, collector=None, include_gift_cash: bool = True) -> dict:
    return collections_report(community=community, start_date=on_date, end_date=on_date, collector=collector, include_gift_cash=include_gift_cash)


def weekly_report(*, community, week_start: date, collector=None, include_gift_cash: bool = True) -> dict:
    return collections_report(community=community, start_date=week_start, end_date=week_start + timedelta(days=6), collector=collector, include_gift_cash=include_gift_cash)


def monthly_report(*, community, year: int, month: int, collector=None, include_gift_cash: bool = True) -> dict:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
    return collections_report(community=community, start_date=start, end_date=end, collector=collector, include_gift_cash=include_gift_cash)


def annual_report(*, community, year: int, collector=None, include_gift_cash: bool = True) -> dict:
    return collections_report(community=community, start_date=date(year, 1, 1), end_date=date(year, 12, 31), collector=collector, include_gift_cash=include_gift_cash)


def family_statement(family) -> dict:
    """
    Everything the abusuapanin (family head) needs, all four ledgers a
    funeral of his family actually touches:

      - Family Ledger: his own family's members, paying the own-family
        rate — they never pay the community's general rate for their
        own family's funeral, only this one.
      - Community Ledger: what everyone ELSE in the community paid
        (the general rate) specifically toward a funeral where his
        family was the deceased's family — this is money the wider
        community raised FOR his family, not money his family raised.
      - Guest Ledger: cash from visiting well-wishers whose names
        aren't in the system at all, recorded by the cashier on the
        spot, tied to which of the deceased's relatives they came
        because of.
      - Town Leaders Ledger: the same idea, tracked separately out of
        respect for the standing of the town's chief and elders.

    Also kept for historical context: what this family's OWN members
    paid as outsiders on OTHER families' funerals — not part of "his"
    funeral's four ledgers, but relevant to a family's overall standing.
    """
    from funerals.models import ContributionObligation

    own_family_obligations = ContributionObligation.objects.filter(
        funeral_event__deceased_family=family, rate_type="own_family"
    )
    community_obligations = ContributionObligation.objects.filter(
        funeral_event__deceased_family=family, rate_type="general"
    )
    member_ids = family.members.values_list("id", flat=True)
    as_outsider_obligations = ContributionObligation.objects.filter(member_id__in=member_ids, rate_type="general")

    def _bucket(qs):
        return {
            "obligation_count": qs.count(),
            "expected_total": str(qs.aggregate(total=Sum("expected_amount"))["total"] or Decimal("0")),
            "collected_total": str(qs.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")),
        }

    def _gift_bucket(category):
        donations = GiftDonation.objects.filter(recipient_family=family, donor_category=category)
        total = sum((d.total_value for d in donations), Decimal("0"))
        return {"donor_count": donations.count(), "total_value": str(total)}

    def _donation_receivers_breakdown():
        """
        "All amount received in your name has to reflect for transparency
        and accountability" — the abusuapanin's own audit view: every
        registered receiver for this family's funerals, and exactly how
        much has been attributed to each of them. This is the same
        underlying data each receiver sees on their own dashboard
        (gifts.services.donations_received_by_member) — the family head
        just sees everyone's at once, for oversight.
        """
        donations = GiftDonation.objects.filter(
            funeral_event__deceased_family=family, received_by_member__isnull=False
        ).select_related("received_by_member")
        totals: dict = {}
        for d in donations:
            entry = totals.setdefault(str(d.received_by_member_id), {
                "member_id": str(d.received_by_member_id),
                "member_name": d.received_by_member.full_name,
                "donation_count": 0,
                "total_received": Decimal("0"),
            })
            entry["donation_count"] += 1
            entry["total_received"] += d.total_value
        return [{**v, "total_received": str(v["total_received"])} for v in totals.values()]

    return {
        "family_id": str(family.id),
        "family_name": family.name,
        "member_count": family.members.filter(status="active").count(),
        "family_ledger": _bucket(own_family_obligations),
        "community_ledger": _bucket(community_obligations),
        "guest_ledger": _gift_bucket(GiftDonation.DonorCategory.GUEST),
        "town_leaders_ledger": _gift_bucket(GiftDonation.DonorCategory.TOWN_LEADER),
        "donation_receivers": _donation_receivers_breakdown(),
        # Kept under their original names for backward compatibility with
        # anything already reading this response — family_ledger above is
        # the same numbers as as_deceaseds_family, just under the name
        # this pass's terminology actually uses.
        "as_deceaseds_family": _bucket(own_family_obligations),
        "members_as_outsiders_elsewhere": _bucket(as_outsider_obligations),
        "gifts_received": {
            "total_cash": str(
                GiftDonation.objects.filter(recipient_family=family).aggregate(total=Sum("amount_cash"))["total"]
                or Decimal("0")
            ),
        },
    }


def family_member_compliance_breakdown(family) -> list:
    """
    'View members who have paid. View members with outstanding
    contributions. View members flagged as defaulters.' family_statement
    above gives the Family Head aggregate totals; this is the genuinely
    different, per-member view the spec separately asks for — legitimate
    here in a way it isn't for the Chief's community-wide dashboard,
    since these are the Family Head's own family's members, not
    strangers' private financial detail.
    """
    from funerals.models import ContributionObligation, FuneralEvent

    members = list(family.members.filter(status="active").order_by("full_name"))
    obligations = ContributionObligation.objects.filter(
        member__family=family, funeral_event__status=FuneralEvent.Status.ACTIVE,
    ).select_related("member")

    by_member: dict = {}
    for o in obligations:
        entry = by_member.setdefault(o.member_id, {"paid_count": 0, "outstanding_count": 0, "total_owed": Decimal("0")})
        if o.payment_status == "paid":
            entry["paid_count"] += 1
        else:
            entry["outstanding_count"] += 1
            entry["total_owed"] += o.balance

    return [
        {
            "member_id": str(m.id),
            "member_name": m.full_name,
            "defaulter_tier": m.defaulter_tier,
            "paid_count": by_member.get(m.id, {}).get("paid_count", 0),
            "outstanding_count": by_member.get(m.id, {}).get("outstanding_count", 0),
            "total_owed": str(by_member.get(m.id, {}).get("total_owed", Decimal("0"))),
        }
        for m in members
    ]


def collector_performance_report(*, collector, start_date: date, end_date: date) -> dict:
    base = collections_report(community=collector.community, start_date=start_date, end_date=end_date, collector=collector)
    base["collector_name"] = collector.get_full_name() or collector.username
    return base


def funeral_statement(funeral: FuneralEvent) -> dict:
    """One-stop statement for a single funeral, gathering all three ledgers' totals already computed elsewhere."""
    from funeral_logistics.services import funeral_financial_overview
    return funeral_financial_overview(funeral)


def outstanding_members_report(*, community) -> dict:
    """
    Every member with an unpaid or partially-paid obligation on any
    currently ACTIVE (not yet closed) funeral — distinct from the
    Defaulters Dashboard (members/services.py), which only counts misses
    on funerals that have already CLOSED. This report is "who still owes
    money right now", not "who has a track record of not paying".
    """
    from funerals.models import ContributionObligation

    obligations = ContributionObligation.objects.filter(
        community=community, funeral_event__status=FuneralEvent.Status.ACTIVE,
    ).select_related("member", "funeral_event")

    outstanding = [o for o in obligations if o.payment_status != "paid"]
    by_member: dict = {}
    for o in outstanding:
        entry = by_member.setdefault(o.member_id, {"member_name": o.member.full_name, "total_owed": Decimal("0"), "funeral_count": 0})
        entry["total_owed"] += o.balance
        entry["funeral_count"] += 1

    return {
        "community_id": str(community.id),
        "outstanding_member_count": len(by_member),
        "members": [
            {"member_id": str(mid), "member_name": v["member_name"], "total_owed": str(v["total_owed"]), "funeral_count": v["funeral_count"]}
            for mid, v in sorted(by_member.items(), key=lambda kv: kv[1]["total_owed"], reverse=True)
        ],
    }


def members_payment_status_report(*, community, family=None) -> dict:
    """
    'Make it transparent to the community treasurer to have data of
    those who have paid, and also collectors should also have a place
    in their dashboard where they can see those who have paid and who
    have not paid. Each treasurer should have access to data of those
    who have paid in his family and who haven't.'

    Both sides of the same picture, on every currently ACTIVE funeral —
    who's paid in full, and who still owes — in one call, since a
    genuine transparency view needs both, not just the defaulter half
    this platform already had. `family=None` is community-wide (the
    Community Treasurer/Collector's own view); passing a specific
    family scopes it to that family's own members only (the Family
    Treasurer's own view) — the exact same family-scoping already
    enforced everywhere else on this platform, not a separate,
    parallel rule.
    """
    from funerals.models import ContributionObligation

    obligations = ContributionObligation.objects.filter(
        community=community, funeral_event__status=FuneralEvent.Status.ACTIVE,
    ).select_related("member", "funeral_event")
    if family is not None:
        obligations = obligations.filter(member__family=family)

    paid_by_member: dict = {}
    outstanding_by_member: dict = {}
    for o in obligations:
        if o.payment_status == "paid":
            entry = paid_by_member.setdefault(o.member_id, {"member_name": o.member.full_name, "total_paid": Decimal("0"), "funeral_count": 0})
            entry["total_paid"] += o.amount_paid
            entry["funeral_count"] += 1
        else:
            entry = outstanding_by_member.setdefault(o.member_id, {"member_name": o.member.full_name, "total_owed": Decimal("0"), "funeral_count": 0})
            entry["total_owed"] += o.balance
            entry["funeral_count"] += 1

    return {
        "community_id": str(community.id),
        "family_id": str(family.id) if family else None,
        "family_name": family.name if family else None,
        "paid_member_count": len(paid_by_member),
        "outstanding_member_count": len(outstanding_by_member),
        "paid_members": [
            {"member_id": str(mid), "member_name": v["member_name"], "total_paid": str(v["total_paid"]), "funeral_count": v["funeral_count"]}
            for mid, v in sorted(paid_by_member.items(), key=lambda kv: kv[1]["total_paid"], reverse=True)
        ],
        "outstanding_members": [
            {"member_id": str(mid), "member_name": v["member_name"], "total_owed": str(v["total_owed"]), "funeral_count": v["funeral_count"]}
            for mid, v in sorted(outstanding_by_member.items(), key=lambda kv: kv[1]["total_owed"], reverse=True)
        ],
    }


def town_elders_ledger_report(*, community) -> dict:
    """
    'They should also be registered as town elders which consist of
    the chief, queen mother, linguist, and other town executive...
    the community ledger is for all community members excluding town
    elders who have their own ledger.' The dedicated, complete ledger
    view for that separate group — unlike outstanding_members_report
    above, this deliberately includes fully-paid obligations too, not
    only outstanding ones, since the Traditional Leader overseeing
    this ledger (per set_town_elder_rate's own authority) needs the
    full picture of the group he's the head of, not just a defaulter
    list.
    """
    from funerals.models import ContributionObligation

    obligations = (
        ContributionObligation.objects.filter(community=community, rate_type=ContributionObligation.RateType.TOWN_ELDER)
        .select_related("member", "funeral_event")
        .order_by("member__full_name", "-funeral_event__collection_start_date")
    )

    by_member: dict = {}
    for o in obligations:
        entry = by_member.setdefault(o.member_id, {
            "member_name": o.member.full_name,
            "title": o.member.town_elder_title,
            "expected_total": Decimal("0"),
            "collected_total": Decimal("0"),
            "funeral_count": 0,
        })
        entry["expected_total"] += o.expected_amount
        entry["collected_total"] += o.amount_paid
        entry["funeral_count"] += 1

    members = [
        {
            "member_id": str(mid),
            "member_name": v["member_name"],
            "title": v["title"],
            "expected_total": str(v["expected_total"]),
            "collected_total": str(v["collected_total"]),
            "outstanding_total": str(v["expected_total"] - v["collected_total"]),
            "funeral_count": v["funeral_count"],
        }
        for mid, v in by_member.items()
    ]
    return {
        "community_id": str(community.id),
        "town_elder_count": len(members),
        "current_rate": str(community.default_town_leader_amount),
        "members": sorted(members, key=lambda m: m["member_name"]),
    }


def member_outstanding_obligations(member) -> list[dict]:
    """
    Every unpaid/partially-paid obligation for ONE member, across every
    currently active funeral — the concrete, obligation-ID-bearing list
    a "pay now" screen actually needs (unlike outstanding_members_report,
    which only aggregates a community-wide total per member and can't
    itself be paid against). Powers both the member's own self-service
    "my obligations" view and a collector's front-desk lookup for
    someone standing in front of them — same underlying data, reached
    through two different permission-gated endpoints.
    """
    from funerals.models import ContributionObligation, FuneralEvent

    obligations = ContributionObligation.objects.filter(
        member=member, funeral_event__status=FuneralEvent.Status.ACTIVE,
    ).select_related("funeral_event", "funeral_event__deceased_family")

    return [
        {
            "obligation_id": str(o.id),
            "funeral_id": str(o.funeral_event_id),
            "deceased_name": o.funeral_event.deceased_name,
            "deceased_family_name": o.funeral_event.deceased_family.name,
            "rate_type": o.rate_type,
            "expected_amount": str(o.expected_amount),
            "amount_paid": str(o.amount_paid),
            "balance": str(o.balance),
            "payment_status": o.payment_status,
        }
        for o in obligations if o.payment_status != "paid"
    ]


def my_receipts(*, user) -> dict:
    """
    Every receipt belonging to the Member profile linked to this User —
    every contribution payment they made AND every gift they gave (as a
    known donor), combined into one chronological list for their
    personal "My Receipts" dashboard. This is exactly the "those who pay
    physical can still get the e-receipt in their dashboard" requirement:
    a receipt appears here regardless of payment method or delivery
    channel, cash-printed or momo-electronic alike — the dashboard is
    simply always-available proof, on top of however it was delivered at
    the moment of payment.

    Returns an explicit "no_member_profile" flag rather than raising,
    since "this login has no linked member yet" is an ordinary state
    (most Users aren't linked to a Member at all), not an error.
    """
    from . import receipts as receipts_module

    member = getattr(user, "member_profile", None)
    if member is None:
        return {"has_member_profile": False, "receipts": []}

    payments = ContributionPayment.objects.filter(obligation__member=member).select_related(
        "obligation__member__family", "obligation__funeral_event", "collected_by"
    )
    donations = GiftDonation.objects.filter(donor_member=member).select_related(
        "recipient_family", "funeral_event", "collected_by"
    )

    entries = []
    for p in payments:
        data = receipts_module.contribution_receipt_data(p)
        data["payment_id"] = str(p.id)
        entries.append(data)
    for d in donations:
        data = receipts_module.gift_receipt_data(d)
        data["donation_id"] = str(d.id)
        entries.append(data)

    entries.sort(key=lambda e: (e["date"], e["time"]), reverse=True)
    return {"has_member_profile": True, "member_name": member.full_name, "receipts": entries}


def funeral_full_ledger_breakdown(funeral) -> dict:
    """
    The four-ledger picture for ONE funeral, not aggregated across a
    family's whole history the way family_statement() is: Family Ledger
    and Community Ledger from the mandatory contribution ledger
    (funerals.services.funeral_summary already computes exactly this
    split), plus Guest Ledger and Town Leaders Ledger from Gift Donations
    (gifts.services.donations_by_category). Nothing here recomputes
    numbers that already exist elsewhere and are already tested there —
    this just puts all four side by side for one funeral.
    """
    from funerals import services as funeral_services
    from funerals.services import funeral_summary
    from gifts.services import donations_by_category
    from gifts.models import GiftDonation

    contributions = funeral_summary(funeral)
    gift_categories = donations_by_category(funeral)["by_category"]

    return {
        "funeral_id": str(funeral.id),
        "deceased_name": funeral.deceased_name,
        "deceased_family_name": funeral.deceased_family.name,
        "family_ledger": {
            "member_count": contributions["own_family"]["member_count"],
            "expected_total": contributions["own_family"]["expected_total"],
            "collected_total": contributions["own_family"]["collected_total"],
        },
        "community_ledger": {
            "member_count": contributions["general"]["member_count"],
            "expected_total": contributions["general"]["expected_total"],
            "collected_total": contributions["general"]["collected_total"],
        },
        "guest_ledger": gift_categories.get(GiftDonation.DonorCategory.GUEST, {"donor_count": 0, "total_value": "0"}),
        "town_leaders_ledger": gift_categories.get(GiftDonation.DonorCategory.TOWN_LEADER, {"donor_count": 0, "total_value": "0"}),
        # A fifth, genuinely distinct ledger from the four above — 'the
        # community ledger is for all community members excluding town
        # elders who have their own ledger and they pay higher than all
        # the member.' This is the Town Elders' own MANDATORY
        # contribution ledger (Chief, Queen Mother, Linguist, other town
        # executives), never to be confused with town_leaders_ledger
        # above, which is voluntary GIFT money from donors who happen to
        # be categorized as town leaders — a different ledger entirely.
        "town_elders_contribution_ledger": {
            "member_count": contributions["town_elder"]["member_count"],
            "expected_total": contributions["town_elder"]["expected_total"],
            "collected_total": contributions["town_elder"]["collected_total"],
        },
        # The two ledgers built to genuinely different rules than the
        # five above — Asupedeɛ (auto-enrolled, but its own separate
        # model and collection window) and In-Law (request-and-approval,
        # never auto-enrolled at all). See funerals.services.asupede_summary
        # / in_law_summary for what each actually aggregates.
        "asupede_ledger": funeral_services.asupede_summary(funeral),
        "in_law_ledger": funeral_services.in_law_summary(funeral),
    }


def funeral_daily_breakdown(funeral, include_gift_cash: bool = True) -> dict:
    """
    'It starts Friday and closes Sunday evening but they should be able
    to know the amount they received each day.' Every day from this
    funeral's own `collection_start_date` through either today (if still
    collecting) or its actual `collection_end_date`/close date (once
    closed) — including days with genuinely zero collections, so a
    quiet Saturday shows as GH₵0, not a gap in the list.

    `include_gift_cash` follows the same "funeral committee sees all the
    money paid except the donations" rule as collections_report() — the
    view layer decides this per-role (Community Admin+ or this family's
    own head get the full picture; the rest of the committee sees
    contributions only, per day).
    """
    from funerals.models import ContributionPayment
    from gifts.models import GiftDonation

    def _as_date(value):
        # A FuneralEvent returned directly from .objects.create(...) can
        # still carry whatever raw type was passed in (e.g. a plain
        # "2026-07-03" string) until it's reloaded from the database —
        # arithmetic below needs a real date object either way.
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    start = _as_date(funeral.collection_start_date)
    end = _as_date(funeral.collection_end_date) if funeral.collection_end_date else date.today()
    if funeral.status == "closed" and funeral.updated_at:
        end = max(end, funeral.updated_at.date())
    end = max(end, start)

    days = []
    current = start
    while current <= end:
        contributions = ContributionPayment.objects.filter(obligation__funeral_event=funeral, paid_at__date=current)
        contributions_total = contributions.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        # 'After each day of every funeral the system should be able to
        # calculate all money received from the town elders ledger, the
        # community ledger and sum them together.' Broken out by the
        # obligation's own rate_type — own_family stays out of this
        # specific combined figure on purpose (it's already its own,
        # separate ledger, shown elsewhere); this combined total is
        # specifically the two the request names.
        town_elder_total = contributions.filter(obligation__rate_type="town_elder").aggregate(total=Sum("amount"))["total"] or Decimal("0")
        community_ledger_total = contributions.filter(obligation__rate_type="general").aggregate(total=Sum("amount"))["total"] or Decimal("0")

        day_entry = {
            "date": current.isoformat(),
            "contributions_total": str(contributions_total),
            "contributions_count": contributions.count(),
            "town_elders_ledger_total": str(town_elder_total),
            "community_ledger_total": str(community_ledger_total),
            "town_elders_and_community_combined_total": str(town_elder_total + community_ledger_total),
        }
        if include_gift_cash:
            gifts = GiftDonation.objects.filter(funeral_event=funeral, given_at__date=current)
            gifts_total = gifts.aggregate(total=Sum("amount_cash"))["total"] or Decimal("0")
            day_entry["gifts_total"] = str(gifts_total)
            day_entry["gifts_count"] = gifts.count()
            day_entry["combined_total"] = str(contributions_total + gifts_total)
        else:
            day_entry["combined_total"] = str(contributions_total)
        days.append(day_entry)
        current += timedelta(days=1)

    return {
        "funeral_id": str(funeral.id),
        "collection_start_date": start.isoformat(),
        "collection_end_date": _as_date(funeral.collection_end_date).isoformat() if funeral.collection_end_date else None,
        "status": funeral.status,
        "days": days,
        "grand_total": str(sum((Decimal(d["combined_total"]) for d in days), Decimal("0"))),
        "town_elders_and_community_grand_total": str(sum((Decimal(d["town_elders_and_community_combined_total"]) for d in days), Decimal("0"))),
    }


def expense_statement(*, community, start_date: date, end_date: date) -> dict:
    expenses = FuneralExpense.objects.filter(community=community, incurred_on__gte=start_date, incurred_on__lte=end_date)
    by_category: dict = {}
    for e in expenses:
        by_category[e.category] = by_category.get(e.category, Decimal("0")) + e.amount
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "expense_count": expenses.count(),
        "total": str(expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")),
        "by_category": {k: str(v) for k, v in by_category.items()},
    }


def members_export_rows(*, community, actor) -> list:
    """
    'All data should be downloaded or printable... upload data when
    necessary.' Reuses members.services.search_members directly rather
    than a separate query, so a printed/exported member list can
    NEVER show more than the same person would already see on the
    Members page itself — the family-scoping for Family Head/
    Secretary/Treasurer is enforced there once, not reimplemented
    (and potentially gotten wrong) here.

    Every field bulk_update_members can actually write back is
    included here too — 'download it or upload to update it' is a
    genuine round trip, not just a one-way report, so the exported
    file has to carry enough to be a real working copy of the
    underlying record, not a summary of it.
    """
    from members import services as member_services

    members = member_services.search_members(community=community, actor=actor).select_related("family")
    return [
        {
            "membership_number": m.membership_number,
            "full_name": m.full_name,
            "family_name": m.family.name if m.family else "",
            "gender": m.gender,
            "status": m.status,
            "phone": m.phone,
            "email": m.email,
            "date_of_birth": m.date_of_birth.isoformat() if m.date_of_birth else "",
            "occupation": m.occupation,
            "address": m.address,
            "ghana_card_number": m.ghana_card_number or "",
            "mother_name": m.mother_name,
            "father_name": m.father_name,
            "hometown": m.hometown,
            "marital_status": m.marital_status,
            "spouse_name": m.spouse_name,
            "emergency_contact_name": m.emergency_contact_name,
            "emergency_contact_phone": m.emergency_contact_phone,
            "defaulter_tier": m.defaulter_tier,
        }
        for m in members
    ]

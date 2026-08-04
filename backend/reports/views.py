from datetime import date, datetime

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from families.models import Family
from funerals.models import ContributionPayment, FuneralEvent
from gifts.models import GiftDonation
from . import pdf as pdf_module
from . import receipts, services
from .permissions import CanViewOwnPerformance, CanViewReceipts, CanViewReports, is_family_head_of


def _parse_date(value: str, fallback: date) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date() if value else fallback


def _includes_gift_cash_for(user) -> bool:
    """
    "The funeral committee should have access to all the money paid
    except the donations." Community Admin (and above) keeps genuine
    platform-level oversight (fraud review, disputes); the rest of the
    committee — Treasurer, Chairman, Secretary, Financial Secretary,
    Auditor — get every one of these aggregate reports WITHOUT the gift
    -cash figures folded in, same restriction as the raw gift ledger
    itself (see gifts/views.py's _can_view_gift_ledger).
    """
    return user.is_superuser or user.can_manage_families()


def _report_pdf_response(report: dict, community_name: str, period_label: str) -> HttpResponse:
    pdf_bytes = pdf_module.collections_report_pdf(report, community_name, period_label)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="collections-{period_label.replace(" ", "-")}.pdf"'
    return response


class DailyCollectionsReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        on_date = _parse_date(request.query_params.get("date"), date.today())
        report = services.daily_report(community=request.user.community, on_date=on_date, include_gift_cash=_includes_gift_cash_for(request.user))
        if request.query_params.get("export") == "pdf":
            return _report_pdf_response(report, request.user.community.name, f"Daily — {on_date.isoformat()}")
        return Response(report)


class WeeklyCollectionsReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        week_start = _parse_date(request.query_params.get("week_start"), date.today())
        report = services.weekly_report(community=request.user.community, week_start=week_start, include_gift_cash=_includes_gift_cash_for(request.user))
        if request.query_params.get("export") == "pdf":
            return _report_pdf_response(report, request.user.community.name, f"Week of {week_start.isoformat()}")
        return Response(report)


class MonthlyCollectionsReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        today = date.today()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))
        report = services.monthly_report(community=request.user.community, year=year, month=month, include_gift_cash=_includes_gift_cash_for(request.user))
        if request.query_params.get("export") == "pdf":
            return _report_pdf_response(report, request.user.community.name, f"{year}-{month:02d}")
        return Response(report)


class AnnualCollectionsReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        year = int(request.query_params.get("year", date.today().year))
        report = services.annual_report(community=request.user.community, year=year, include_gift_cash=_includes_gift_cash_for(request.user))
        if request.query_params.get("export") == "pdf":
            return _report_pdf_response(report, request.user.community.name, str(year))
        return Response(report)


class MyPerformanceReportView(APIView):
    """A collector's own daily/weekly/monthly performance — no management role required."""
    permission_classes = [IsAuthenticated, CanViewOwnPerformance]

    def get(self, request):
        start = _parse_date(request.query_params.get("start_date"), date.today())
        end = _parse_date(request.query_params.get("end_date"), date.today())
        return Response(services.collector_performance_report(collector=request.user, start_date=start, end_date=end))


class FuneralLedgerBreakdownView(APIView):
    """GET -> the four-ledger picture for one funeral. Guest/Town Leaders ledgers
    (donations) are only included for this family's own head, Community Admin+, or a superuser —
    the rest of the committee sees Family/Community ledgers only, per _includes_gift_cash_for."""
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        from .permissions import REPORT_VIEWING_ROLES
        qs = FuneralEvent.objects.all() if request.user.is_superuser else FuneralEvent.objects.filter(community=request.user.community)
        funeral = get_object_or_404(qs, id=funeral_id)
        allowed = (
            request.user.is_superuser
            or request.user.role in REPORT_VIEWING_ROLES
            or is_family_head_of(request.user, funeral.deceased_family)
        )
        if not allowed:
            return Response({"detail": "Not permitted to view this funeral's ledger breakdown."}, status=403)

        breakdown = services.funeral_full_ledger_breakdown(funeral)
        if not (_includes_gift_cash_for(request.user) or is_family_head_of(request.user, funeral.deceased_family)):
            breakdown.pop("guest_ledger", None)
            breakdown.pop("town_leaders_ledger", None)
        return Response(breakdown)


class FuneralDailyBreakdownView(APIView):
    """GET -> per-day collection totals for one funeral. 'It starts Friday and closes Sunday evening but they should be able to know the amount they received each day.'"""
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        from .permissions import REPORT_VIEWING_ROLES
        qs = FuneralEvent.objects.all() if request.user.is_superuser else FuneralEvent.objects.filter(community=request.user.community)
        funeral = get_object_or_404(qs, id=funeral_id)
        allowed = (
            request.user.is_superuser
            or request.user.role in REPORT_VIEWING_ROLES
            or is_family_head_of(request.user, funeral.deceased_family)
        )
        if not allowed:
            return Response({"detail": "Not permitted to view this funeral's daily breakdown."}, status=403)

        include_gift_cash = _includes_gift_cash_for(request.user) or is_family_head_of(request.user, funeral.deceased_family)
        return Response(services.funeral_daily_breakdown(funeral, include_gift_cash=include_gift_cash))


class FamilyStatementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, family_id):
        from .permissions import REPORT_VIEWING_ROLES
        qs = Family.objects.all() if request.user.is_superuser else Family.objects.filter(community=request.user.community)
        family = get_object_or_404(qs, id=family_id)

        allowed = (
            request.user.is_superuser
            or request.user.role in REPORT_VIEWING_ROLES
            or is_family_head_of(request.user, family)
        )
        if not allowed:
            return Response({"detail": "Not permitted to view this family's statement."}, status=403)

        statement = services.family_statement(family)
        if not (_includes_gift_cash_for(request.user) or is_family_head_of(request.user, family)):
            statement.pop("guest_ledger", None)
            statement.pop("town_leaders_ledger", None)
            statement.pop("gifts_received", None)
            statement.pop("donation_receivers", None)

        if request.query_params.get("export") == "pdf":
            pdf_bytes = pdf_module.family_statement_pdf(statement, family.community.name)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="family-statement-{family.slug}.pdf"'
            return response
        return Response(statement)


class OutstandingMembersReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        return Response(services.outstanding_members_report(community=request.user.community))


class ExpenseStatementView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        today = date.today()
        start = _parse_date(request.query_params.get("start_date"), today.replace(day=1))
        end = _parse_date(request.query_params.get("end_date"), today)
        return Response(services.expense_statement(community=request.user.community, start_date=start, end_date=end))


def _get_payment(request, payment_id):
    qs = ContributionPayment.objects.select_related("obligation__member__family", "obligation__funeral_event", "collected_by")
    if not request.user.is_superuser:
        qs = qs.filter(obligation__community=request.user.community)
    return get_object_or_404(qs, id=payment_id)


def _get_donation(request, donation_id):
    qs = GiftDonation.objects.select_related("recipient_family", "funeral_event", "collected_by")
    if not request.user.is_superuser:
        qs = qs.filter(community=request.user.community)
    return get_object_or_404(qs, id=donation_id)


class MyReceiptsView(APIView):
    """
    A member's own receipts dashboard — no management role required,
    just an authenticated User whose account happens to be linked to a
    Member profile. See reports.services.my_receipts for why an
    unlinked account gets an empty, explicit result rather than a 404.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.my_receipts(user=request.user))


class MyOutstandingObligationsView(APIView):
    """
    "Add MoMo pay prompts for members to pay their contributions...
    very easy" — this is the concrete list a member's own dashboard
    renders as "Pay now" buttons (see PayViaMomoDialog on the frontend,
    which already existed for the funeral committee's ledger view; this
    endpoint is what makes the SAME dialog usable from a member's own,
    self-service side instead of requiring them to find their own row
    in the full funeral ledger).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            return Response([])
        return Response(services.member_outstanding_obligations(member))


class MemberOutstandingObligationsView(APIView):
    """
    Same data as MyOutstandingObligationsView, but for a COLLECTOR
    looking someone up at the front desk — "can also visit the desk at
    the funeral grounds to make payment there." Gated to collecting
    roles rather than open to any authenticated user, since this reveals
    another person's specific balances, not just your own.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, member_id):
        from django.shortcuts import get_object_or_404
        from members.models import Member
        if not (request.user.is_superuser or request.user.can_manage_families() or request.user.role == Role.COLLECTOR):
            return Response({"detail": "Not permitted to look up another member's obligations."}, status=403)
        qs = Member.objects.all() if request.user.is_superuser else Member.objects.filter(community=request.user.community)
        member = get_object_or_404(qs, id=member_id)
        return Response(services.member_outstanding_obligations(member))


class ContributionReceiptView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def get(self, request, payment_id):
        payment = _get_payment(request, payment_id)
        return Response(receipts.contribution_receipt_data(payment))


class ContributionReceiptTextView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def get(self, request, payment_id):
        payment = _get_payment(request, payment_id)
        text = receipts.contribution_receipt_text(payment, payment.obligation.community.name)
        return HttpResponse(text, content_type="text/plain")


class ContributionReceiptPdfView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def get(self, request, payment_id):
        payment = _get_payment(request, payment_id)
        data = receipts.contribution_receipt_data(payment)
        pdf_bytes = pdf_module.contribution_receipt_pdf(data, payment.obligation.community.name)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="receipt-{data["receipt_number"]}.pdf"'
        return response


class MarkContributionReceiptPrintedView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def post(self, request, payment_id):
        payment = _get_payment(request, payment_id)
        services.mark_contribution_receipt_printed(payment=payment)
        return Response(receipts.contribution_receipt_data(payment))


class MarkGiftReceiptPrintedView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def post(self, request, donation_id):
        donation = _get_donation(request, donation_id)
        services.mark_gift_receipt_printed(donation=donation)
        return Response(receipts.gift_receipt_data(donation))


class UnprintedReceiptsView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        return Response(services.unprinted_receipts(community=request.user.community))


class GiftReceiptView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def get(self, request, donation_id):
        donation = _get_donation(request, donation_id)
        return Response(receipts.gift_receipt_data(donation))


class GiftReceiptTextView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def get(self, request, donation_id):
        donation = _get_donation(request, donation_id)
        text = receipts.gift_receipt_text(donation, donation.community.name)
        return HttpResponse(text, content_type="text/plain")


class GiftReceiptPdfView(APIView):
    permission_classes = [IsAuthenticated, CanViewReceipts]

    def get(self, request, donation_id):
        donation = _get_donation(request, donation_id)
        data = receipts.gift_receipt_data(donation)
        pdf_bytes = pdf_module.gift_receipt_pdf(data, donation.community.name)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="receipt-{data["receipt_number"]}.pdf"'
        return response

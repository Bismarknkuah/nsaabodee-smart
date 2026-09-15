from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from families.models import Family
from families.services import is_family_finance_officer, is_family_officer
from members.models import Member
from . import services
from .models import FamilyFund, FamilyFundContribution, FamilyFuneralExpense
from .permissions import CanAccessFamilyFund
from .serializers import FamilyFundContributionSerializer, FamilyFundSerializer, FamilyFuneralExpenseSerializer


def _get_family(request, family_id):
    qs = Family.objects.all() if request.user.is_superuser else Family.objects.filter(community=request.user.community)
    return get_object_or_404(qs, id=family_id)


def _require_officer(request, family):
    if not is_family_officer(request.user, family):
        return Response(
            {"detail": "Only this family's own head, secretary, treasurer, or a community administrator can access its fund."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


class FamilyFundListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        return Response(FamilyFundSerializer(services.funds_for_family(family), many=True).data)

    def post(self, request, family_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        name = request.data.get("name", "").strip()
        if not name:
            return Response({"name": "A fund name is required."}, status=status.HTTP_400_BAD_REQUEST)
        fund = services.create_family_fund(
            family=family, name=name, description=request.data.get("description", ""), actor=request.user,
        )
        return Response(FamilyFundSerializer(fund).data, status=status.HTTP_201_CREATED)


class FamilyFundContributionListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id, fund_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        fund = get_object_or_404(FamilyFund, id=fund_id, family=family)
        return Response(FamilyFundContributionSerializer(fund.contributions.select_related("member"), many=True).data)

    def post(self, request, family_id, fund_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        fund = get_object_or_404(FamilyFund, id=fund_id, family=family)

        member_id = request.data.get("member_id")
        try:
            member = Member.objects.get(id=member_id, community=family.community)
        except (Member.DoesNotExist, ValueError, TypeError):
            return Response({"member_id": "Member not found in this community."}, status=status.HTTP_400_BAD_REQUEST)

        from decimal import Decimal, InvalidOperation
        try:
            amount = Decimal(str(request.data.get("amount")))
        except (InvalidOperation, TypeError):
            return Response({"amount": "A valid amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            contribution = services.record_fund_contribution(
                fund=fund, member=member, amount=amount,
                payment_method=request.data.get("payment_method", FamilyFundContribution.PaymentMethod.CASH),
                recorded_by=request.user, client_op_id=request.data.get("client_op_id"),
            )
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages if hasattr(exc, "messages") else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FamilyFundContributionSerializer(contribution).data, status=status.HTTP_201_CREATED)


class FamilyFundSummaryView(APIView):
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id, fund_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        fund = get_object_or_404(FamilyFund, id=fund_id, family=family)
        return Response(services.fund_summary(fund))


class FamilyFundContributionReceiptView(APIView):
    """
    "The system should print individual receipts once money is entered
    paid, and it should be very quick" — the same text/PDF receipt
    pattern used for contributions and gifts, for a fund contribution.
    """
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id, fund_id, contribution_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        fund = get_object_or_404(FamilyFund, id=fund_id, family=family)
        contribution = get_object_or_404(FamilyFundContribution, id=contribution_id, fund=fund)

        from reports.receipts import fund_contribution_receipt_text

        if request.query_params.get("export") == "pdf":
            from django.http import HttpResponse
            from reports.pdf import fund_contribution_receipt_pdf
            from reports.receipts import fund_contribution_receipt_data
            pdf_bytes = fund_contribution_receipt_pdf(fund_contribution_receipt_data(contribution), family.community.name)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="fund-receipt-{contribution.receipt_number}.pdf"'
            return response

        text = fund_contribution_receipt_text(contribution, family.community.name)
        return Response({"text": text})


# --- Family Funeral Expense Tracking (secretary records, treasurer approves, head oversees) ---

class FamilyFuneralExpenseListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        funeral_id = request.query_params.get("funeral_event")
        funeral_event = None
        if funeral_id:
            from funerals.models import FuneralEvent
            funeral_event = get_object_or_404(FuneralEvent, id=funeral_id, community=family.community)
        expenses = services.funeral_expenses_for_family(family, funeral_event)
        return Response(FamilyFuneralExpenseSerializer(expenses, many=True).data)

    def post(self, request, family_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied

        from funerals.models import FuneralEvent
        funeral_event = get_object_or_404(FuneralEvent, id=request.data.get("funeral_event"), community=family.community)

        paid_by_member = None
        if request.data.get("paid_by_member_id"):
            paid_by_member = get_object_or_404(Member, id=request.data["paid_by_member_id"], community=family.community)

        from decimal import Decimal, InvalidOperation
        try:
            amount = Decimal(str(request.data.get("amount")))
        except (InvalidOperation, TypeError):
            return Response({"amount": "A valid amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            expense = services.record_funeral_expense(
                family=family, funeral_event=funeral_event, item_name=request.data.get("item_name", ""),
                seller_name=request.data.get("seller_name", ""), seller_contact=request.data.get("seller_contact", ""),
                amount=amount, date_purchased=request.data.get("date_purchased"),
                paid_by_member=paid_by_member, recorded_by=request.user,
            )
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages if hasattr(exc, "messages") else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FamilyFuneralExpenseSerializer(expense).data, status=status.HTTP_201_CREATED)


class FamilyFuneralExpenseDecisionView(APIView):
    """POST {action: "approve"|"reject", reason?} — only this family's own treasurer (the "finance officer"), or Community Admin+."""
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def post(self, request, family_id, expense_id):
        family = _get_family(request, family_id)
        if not is_family_officer(request.user, family):
            return Response({"detail": "Not permitted to view this family's expenses."}, status=status.HTTP_403_FORBIDDEN)
        if not is_family_finance_officer(request.user, family):
            return Response(
                {"detail": "Only this family's own treasurer (finance officer) can approve or reject an expense."},
                status=status.HTTP_403_FORBIDDEN,
            )

        expense = get_object_or_404(FamilyFuneralExpense, id=expense_id, family=family)
        action = request.data.get("action")

        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            if action == "approve":
                services.approve_funeral_expense(expense=expense, actor=request.user)
            elif action == "reject":
                services.reject_funeral_expense(expense=expense, actor=request.user, reason=request.data.get("reason", ""))
            else:
                return Response({"action": "Must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages if hasattr(exc, "messages") else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FamilyFuneralExpenseSerializer(expense).data)


class FamilyFuneralExpenditureSummaryView(APIView):
    """'Family expenses should also be printable or downloaded' — same JSON by default; ?export=pdf for a real, itemized document."""
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        funeral_id = request.query_params.get("funeral_event")
        funeral_event = None
        if funeral_id:
            from funerals.models import FuneralEvent
            funeral_event = get_object_or_404(FuneralEvent, id=funeral_id, community=family.community)
        summary = services.funeral_expenditure_summary(family, funeral_event)

        if request.query_params.get("export") == "pdf":
            expenses = FamilyFuneralExpenseSerializer(services.funeral_expenses_for_family(family, funeral_event), many=True).data
            from reports import pdf as pdf_module
            pdf_bytes = pdf_module.family_expenses_pdf(
                community_name=family.community.name, family_name=family.name, summary=summary,
                expenses=expenses, deceased_name=funeral_event.deceased_name if funeral_event else None,
            )
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{family.name}-expenses.pdf"'
            return response
        return Response(summary)


class FamilyFinancialOverviewView(APIView):
    """GET -> one combined picture for the abusuapanin: total fund contributions vs. total approved spend, and the net position."""
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        funeral_id = request.query_params.get("funeral_event")
        funeral_event = None
        if funeral_id:
            from funerals.models import FuneralEvent
            funeral_event = get_object_or_404(FuneralEvent, id=funeral_id, community=family.community)
        return Response(services.family_financial_overview(family, funeral_event))


class FamilyFuneralExpenseVoucherView(APIView):
    """GET -> a printable voucher for one APPROVED expense (text, or ?export=pdf) — a paper trail for the seller and the family alike."""
    permission_classes = [IsAuthenticated, CanAccessFamilyFund]

    def get(self, request, family_id, expense_id):
        family = _get_family(request, family_id)
        denied = _require_officer(request, family)
        if denied:
            return denied
        expense = get_object_or_404(FamilyFuneralExpense, id=expense_id, family=family)

        from reports.receipts import funeral_expense_voucher_data, funeral_expense_voucher_text
        if request.query_params.get("export") == "pdf":
            if expense.status != FamilyFuneralExpense.Status.APPROVED:
                return Response({"detail": "Only an approved expense has a voucher."}, status=status.HTTP_400_BAD_REQUEST)
            from django.http import HttpResponse
            from reports.pdf import funeral_expense_voucher_pdf
            pdf_bytes = funeral_expense_voucher_pdf(funeral_expense_voucher_data(expense), family.community.name)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="expense-voucher-{expense.id}.pdf"'
            return response

        text = funeral_expense_voucher_text(expense, family.community.name)
        return Response({"text": text})

from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from funerals.models import FuneralEvent
from . import services
from .models import FuneralExpense
from .serializers import (
    DecideExpenseStatusSerializer,
    FuneralAttendanceSerializer,
    FuneralExpenseSerializer,
    RecordAttendanceSerializer,
    RecordExpenseSerializer,
)
from .permissions import CanRecordAttendance, CanRecordExpenses


def _get_funeral(request, funeral_id):
    qs = FuneralEvent.objects.all() if request.user.is_superuser else FuneralEvent.objects.filter(community=request.user.community)
    return get_object_or_404(qs, id=funeral_id)


class FuneralExpenseListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanRecordExpenses]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        from nsaabodeeq.pagination import paginate_response
        return paginate_response(request, funeral.expenses.all(), FuneralExpenseSerializer)

    def post(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        serializer = RecordExpenseSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        expense = serializer.save()
        return Response(FuneralExpenseSerializer(expense).data, status=status.HTTP_201_CREATED)


class DecideExpenseStatusView(APIView):
    """'Payment status... Credit payments create liabilities.' Approve out of Pending Approval, mark a Credit paid, or record a Partial payment's running total — same authority as recording the expense in the first place."""
    permission_classes = [IsAuthenticated, CanRecordExpenses]

    def post(self, request, funeral_id, expense_id):
        funeral = _get_funeral(request, funeral_id)
        expense = get_object_or_404(FuneralExpense, id=expense_id, funeral_event=funeral)
        serializer = DecideExpenseStatusSerializer(data=request.data, context={"request": request, "expense": expense})
        serializer.is_valid(raise_exception=True)
        try:
            updated = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FuneralExpenseSerializer(updated).data)


class CommunityLiabilitiesView(APIView):
    """'Credit payments create liabilities' — every unsettled expense across the whole community, not just one funeral at a time."""
    permission_classes = [IsAuthenticated, CanRecordExpenses]

    def get(self, request):
        liabilities = services.list_expense_liabilities(community=request.user.community)
        return Response(FuneralExpenseSerializer(liabilities, many=True).data)


class CommunityExpensesOverviewView(APIView):
    """'The funeral expenses should have its own link to be one of the multiple tasks' — a real, dedicated overview across every active funeral, not just outstanding/credit ones."""
    permission_classes = [IsAuthenticated, CanRecordExpenses]

    def get(self, request):
        return Response(services.community_expenses_overview(request.user.community))


class ExpenseSummaryView(APIView):
    permission_classes = [IsAuthenticated, CanRecordExpenses]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        return Response(services.expense_summary(funeral))


class FuneralAttendanceListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanRecordAttendance]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        from nsaabodeeq.pagination import paginate_response
        return paginate_response(request, funeral.attendance_records.select_related("member"), FuneralAttendanceSerializer)

    def post(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        serializer = RecordAttendanceSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(FuneralAttendanceSerializer(record).data, status=status.HTTP_201_CREATED)


class AttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated, CanRecordAttendance]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        return Response(services.attendance_summary(funeral))


class FinancialOverviewView(APIView):
    permission_classes = [IsAuthenticated, CanRecordExpenses]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        return Response(services.funeral_financial_overview(funeral))

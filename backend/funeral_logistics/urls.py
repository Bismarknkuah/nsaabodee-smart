from django.urls import path

from .views import (
    AttendanceSummaryView,
    CommunityExpensesOverviewView,
    CommunityLiabilitiesView,
    DecideExpenseStatusView,
    ExpenseSummaryView,
    FinancialOverviewView,
    FuneralAttendanceListCreateView,
    FuneralExpenseListCreateView,
)

urlpatterns = [
    path("funerals/<uuid:funeral_id>/expenses/", FuneralExpenseListCreateView.as_view(), name="funeral-expenses"),
    path("funerals/<uuid:funeral_id>/expenses/summary/", ExpenseSummaryView.as_view(), name="funeral-expenses-summary"),
    path("funerals/<uuid:funeral_id>/expenses/<uuid:expense_id>/status/", DecideExpenseStatusView.as_view(), name="funeral-expense-status"),
    path("expenses/liabilities/", CommunityLiabilitiesView.as_view(), name="community-expense-liabilities"),
    path("expenses/overview/", CommunityExpensesOverviewView.as_view(), name="community-expenses-overview"),
    path("funerals/<uuid:funeral_id>/attendance/", FuneralAttendanceListCreateView.as_view(), name="funeral-attendance"),
    path("funerals/<uuid:funeral_id>/attendance/summary/", AttendanceSummaryView.as_view(), name="funeral-attendance-summary"),
    path("funerals/<uuid:funeral_id>/financial-overview/", FinancialOverviewView.as_view(), name="funeral-financial-overview"),
]

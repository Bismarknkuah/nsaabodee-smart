from django.urls import path

from .views import (
    FamilyFinancialOverviewView,
    FamilyFundContributionListCreateView,
    FamilyFundContributionReceiptView,
    FamilyFundListCreateView,
    FamilyFundSummaryView,
    FamilyFuneralExpenseDecisionView,
    FamilyFuneralExpenseListCreateView,
    FamilyFuneralExpenditureSummaryView,
    FamilyFuneralExpenseVoucherView,
)

urlpatterns = [
    path("families/<uuid:family_id>/funds/", FamilyFundListCreateView.as_view(), name="family-funds"),
    path("families/<uuid:family_id>/funds/<uuid:fund_id>/contributions/", FamilyFundContributionListCreateView.as_view(), name="family-fund-contributions"),
    path("families/<uuid:family_id>/funds/<uuid:fund_id>/summary/", FamilyFundSummaryView.as_view(), name="family-fund-summary"),
    path("families/<uuid:family_id>/funds/<uuid:fund_id>/contributions/<uuid:contribution_id>/receipt/", FamilyFundContributionReceiptView.as_view(), name="family-fund-contribution-receipt"),

    path("families/<uuid:family_id>/funeral-expenses/", FamilyFuneralExpenseListCreateView.as_view(), name="family-funeral-expenses"),
    path("families/<uuid:family_id>/funeral-expenses/<uuid:expense_id>/decision/", FamilyFuneralExpenseDecisionView.as_view(), name="family-funeral-expense-decision"),
    path("families/<uuid:family_id>/funeral-expenses/<uuid:expense_id>/voucher/", FamilyFuneralExpenseVoucherView.as_view(), name="family-funeral-expense-voucher"),
    path("families/<uuid:family_id>/funeral-expenses/summary/", FamilyFuneralExpenditureSummaryView.as_view(), name="family-funeral-expenditure-summary"),
    path("families/<uuid:family_id>/financial-overview/", FamilyFinancialOverviewView.as_view(), name="family-financial-overview"),
]

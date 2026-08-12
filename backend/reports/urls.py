from django.urls import path

from . import views

urlpatterns = [
    path("reports/collections/daily/", views.DailyCollectionsReportView.as_view(), name="report-daily"),
    path("reports/collections/weekly/", views.WeeklyCollectionsReportView.as_view(), name="report-weekly"),
    path("reports/collections/monthly/", views.MonthlyCollectionsReportView.as_view(), name="report-monthly"),
    path("reports/collections/annual/", views.AnnualCollectionsReportView.as_view(), name="report-annual"),
    path("reports/collections/my-performance/", views.MyPerformanceReportView.as_view(), name="report-my-performance"),
    path("reports/families/<uuid:family_id>/statement/", views.FamilyStatementView.as_view(), name="report-family-statement"),
    path("reports/funerals/<uuid:funeral_id>/ledger-breakdown/", views.FuneralLedgerBreakdownView.as_view(), name="report-funeral-ledger-breakdown"),
    path("reports/funerals/<uuid:funeral_id>/daily-breakdown/", views.FuneralDailyBreakdownView.as_view(), name="report-funeral-daily-breakdown"),
    path("reports/outstanding-members/", views.OutstandingMembersReportView.as_view(), name="report-outstanding-members"),
    path("reports/expenses/", views.ExpenseStatementView.as_view(), name="report-expenses"),
    path("my-receipts/", views.MyReceiptsView.as_view(), name="my-receipts"),
    path("my-obligations/", views.MyOutstandingObligationsView.as_view(), name="my-obligations"),
    path("reports/members/<uuid:member_id>/outstanding-obligations/", views.MemberOutstandingObligationsView.as_view(), name="member-outstanding-obligations"),
    path("receipts/contribution-payments/<uuid:payment_id>/", views.ContributionReceiptView.as_view(), name="receipt-contribution"),
    path("receipts/contribution-payments/<uuid:payment_id>/text/", views.ContributionReceiptTextView.as_view(), name="receipt-contribution-text"),
    path("receipts/contribution-payments/<uuid:payment_id>/pdf/", views.ContributionReceiptPdfView.as_view(), name="receipt-contribution-pdf"),
    path("receipts/contribution-payments/<uuid:payment_id>/mark-printed/", views.MarkContributionReceiptPrintedView.as_view(), name="receipt-contribution-mark-printed"),
    path("receipts/gift-donations/<uuid:donation_id>/", views.GiftReceiptView.as_view(), name="receipt-gift"),
    path("receipts/gift-donations/<uuid:donation_id>/text/", views.GiftReceiptTextView.as_view(), name="receipt-gift-text"),
    path("receipts/gift-donations/<uuid:donation_id>/pdf/", views.GiftReceiptPdfView.as_view(), name="receipt-gift-pdf"),
    path("receipts/gift-donations/<uuid:donation_id>/mark-printed/", views.MarkGiftReceiptPrintedView.as_view(), name="receipt-gift-mark-printed"),
    path("reports/unprinted-receipts/", views.UnprintedReceiptsView.as_view(), name="report-unprinted-receipts"),
]

from django.urls import path

from .views import (
    AllReceiversDonationStatementView,
    ApproveDonationAccountRegistrationView,
    DonationAccountRegistrationListCreateView,
    GiftCategoryBreakdownView,
    GiftDonationListCreateView,
    GiftDonationReconciliationView,
    GiftSummaryView,
    MyDonationsReceivedView,
    PendingDonationAccountRegistrationsView,
)

urlpatterns = [
    path("funerals/<uuid:funeral_id>/gifts/", GiftDonationListCreateView.as_view(), name="funeral-gifts"),
    path("funerals/<uuid:funeral_id>/gifts/reconciliation/", GiftDonationReconciliationView.as_view(), name="funeral-gifts-reconciliation"),
    path("funerals/<uuid:funeral_id>/gifts/summary/", GiftSummaryView.as_view(), name="funeral-gifts-summary"),
    path("funerals/<uuid:funeral_id>/gifts/by-category/", GiftCategoryBreakdownView.as_view(), name="funeral-gifts-by-category"),
    path("funerals/<uuid:funeral_id>/donation-accounts/", DonationAccountRegistrationListCreateView.as_view(), name="funeral-donation-accounts"),
    path("funerals/<uuid:funeral_id>/donation-accounts/all-receivers-statement/", AllReceiversDonationStatementView.as_view(), name="funeral-all-receivers-statement"),
    path("donation-accounts/pending/", PendingDonationAccountRegistrationsView.as_view(), name="donation-accounts-pending"),
    path("donation-accounts/<uuid:registration_id>/approve/", ApproveDonationAccountRegistrationView.as_view(), name="donation-accounts-approve"),
    path("my-donations-received/", MyDonationsReceivedView.as_view(), name="my-donations-received"),
]

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApproveDeskAssignmentView,
    ApprovePaymentReversalView,
    FuneralEventViewSet,
    LedgerWalletsView,
    LedgerWalletTransactionsView,
    LedgerWalletWithdrawView,
    ListPaymentReversalsView,
    PendingDeskAssignmentsView,
    RecordPaymentsAcrossActiveFuneralsView,
    RejectPaymentReversalView,
    RequestPaymentReversalView,
)

router = DefaultRouter()
router.register("funerals", FuneralEventViewSet, basename="funeral")

urlpatterns = router.urls + [
    path("members/record-payments-across-active-funerals/", RecordPaymentsAcrossActiveFuneralsView.as_view(), name="record-payments-across-active-funerals"),
    path("payments/<uuid:payment_id>/request-reversal/", RequestPaymentReversalView.as_view(), name="payment-request-reversal"),
    path("payment-reversals/", ListPaymentReversalsView.as_view(), name="payment-reversal-list"),
    path("payment-reversals/<uuid:reversal_id>/approve/", ApprovePaymentReversalView.as_view(), name="payment-reversal-approve"),
    path("payment-reversals/<uuid:reversal_id>/reject/", RejectPaymentReversalView.as_view(), name="payment-reversal-reject"),
    path("desk-assignments/pending/", PendingDeskAssignmentsView.as_view(), name="desk-assignments-pending"),
    path("desk-assignments/<uuid:assignment_id>/approve/", ApproveDeskAssignmentView.as_view(), name="desk-assignments-approve"),
    path("ledger-wallets/", LedgerWalletsView.as_view(), name="ledger-wallets"),
    path("ledger-wallets/<uuid:wallet_id>/transactions/", LedgerWalletTransactionsView.as_view(), name="ledger-wallet-transactions"),
    path("ledger-wallets/<uuid:wallet_id>/withdraw/", LedgerWalletWithdrawView.as_view(), name="ledger-wallet-withdraw"),
]

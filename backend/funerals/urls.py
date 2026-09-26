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
    RequestArrearsCorrectionView,
    ListArrearsCorrectionRequestsView,
    ApproveArrearsCorrectionView,
    RejectArrearsCorrectionView,
    ArrearsWorklistView,
    ArrearsPositionView,
    CollectArrearsView,
)

router = DefaultRouter()
router.register("funerals", FuneralEventViewSet, basename="funeral")

urlpatterns = router.urls + [
    path("members/record-payments-across-active-funerals/", RecordPaymentsAcrossActiveFuneralsView.as_view(), name="record-payments-across-active-funerals"),
    path("payments/<uuid:payment_id>/request-reversal/", RequestPaymentReversalView.as_view(), name="payment-request-reversal"),
    path("payment-reversals/", ListPaymentReversalsView.as_view(), name="payment-reversal-list"),
    path("payment-reversals/<uuid:reversal_id>/approve/", ApprovePaymentReversalView.as_view(), name="payment-reversal-approve"),
    path("payment-reversals/<uuid:reversal_id>/reject/", RejectPaymentReversalView.as_view(), name="payment-reversal-reject"),
    path("obligations/<uuid:obligation_id>/request-arrears-correction/", RequestArrearsCorrectionView.as_view(), name="obligation-request-arrears-correction"),
    path("arrears-corrections/", ListArrearsCorrectionRequestsView.as_view(), name="arrears-correction-list"),
    path("arrears/worklist/", ArrearsWorklistView.as_view(), name="arrears-worklist"),
    path("arrears/members/<uuid:member_id>/position/", ArrearsPositionView.as_view(), name="arrears-position"),
    path("arrears/members/<uuid:member_id>/collect/", CollectArrearsView.as_view(), name="arrears-collect"),
    path("arrears-corrections/<uuid:correction_id>/approve/", ApproveArrearsCorrectionView.as_view(), name="arrears-correction-approve"),
    path("arrears-corrections/<uuid:correction_id>/reject/", RejectArrearsCorrectionView.as_view(), name="arrears-correction-reject"),
    path("desk-assignments/pending/", PendingDeskAssignmentsView.as_view(), name="desk-assignments-pending"),
    path("desk-assignments/<uuid:assignment_id>/approve/", ApproveDeskAssignmentView.as_view(), name="desk-assignments-approve"),
    path("ledger-wallets/", LedgerWalletsView.as_view(), name="ledger-wallets"),
    path("ledger-wallets/<uuid:wallet_id>/transactions/", LedgerWalletTransactionsView.as_view(), name="ledger-wallet-transactions"),
    path("ledger-wallets/<uuid:wallet_id>/withdraw/", LedgerWalletWithdrawView.as_view(), name="ledger-wallet-withdraw"),
]

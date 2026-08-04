from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApproveDeskAssignmentView,
    ApprovePaymentReversalView,
    FuneralEventViewSet,
    ListPaymentReversalsView,
    PendingDeskAssignmentsView,
    RejectPaymentReversalView,
    RequestPaymentReversalView,
)

router = DefaultRouter()
router.register("funerals", FuneralEventViewSet, basename="funeral")

urlpatterns = router.urls + [
    path("payments/<uuid:payment_id>/request-reversal/", RequestPaymentReversalView.as_view(), name="payment-request-reversal"),
    path("payment-reversals/", ListPaymentReversalsView.as_view(), name="payment-reversal-list"),
    path("payment-reversals/<uuid:reversal_id>/approve/", ApprovePaymentReversalView.as_view(), name="payment-reversal-approve"),
    path("payment-reversals/<uuid:reversal_id>/reject/", RejectPaymentReversalView.as_view(), name="payment-reversal-reject"),
    path("desk-assignments/pending/", PendingDeskAssignmentsView.as_view(), name="desk-assignments-pending"),
    path("desk-assignments/<uuid:assignment_id>/approve/", ApproveDeskAssignmentView.as_view(), name="desk-assignments-approve"),
]

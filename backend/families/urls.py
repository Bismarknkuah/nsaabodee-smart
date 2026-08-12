from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApproveBereavedRepView,
    CreateBereavedRepView,
    DeactivateBereavedRepView,
    FamilyViewSet,
    PendingBereavedRepAssignmentsView,
)

router = DefaultRouter()
router.register("families", FamilyViewSet, basename="family")

urlpatterns = router.urls + [
    path("families/<uuid:family_id>/bereaved-rep/", CreateBereavedRepView.as_view(), name="family-bereaved-rep-create"),
    path("bereaved-rep-assignments/pending/", PendingBereavedRepAssignmentsView.as_view(), name="bereaved-rep-pending"),
    path("bereaved-rep-assignments/<uuid:assignment_id>/approve/", ApproveBereavedRepView.as_view(), name="bereaved-rep-approve"),
    path("bereaved-rep-assignments/<uuid:assignment_id>/deactivate/", DeactivateBereavedRepView.as_view(), name="bereaved-rep-deactivate"),
]

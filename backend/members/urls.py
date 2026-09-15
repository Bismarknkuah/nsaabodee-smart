from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CollectorNominationsView, DecideCollectorNominationView, MemberArrearsView, MemberViewSet

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")

urlpatterns = [
    path("members/collector-nominations/", CollectorNominationsView.as_view(), name="collector-nominations"),
    path("members/collector-nominations/<uuid:nomination_id>/decide/", DecideCollectorNominationView.as_view(), name="collector-nomination-decide"),
    path("members/<uuid:member_id>/arrears/", MemberArrearsView.as_view(), name="member-arrears"),
] + router.urls

from rest_framework.routers import DefaultRouter

from .views import DeliveryAttemptViewSet, MeetingViewSet

router = DefaultRouter()
router.register("delivery-attempts", DeliveryAttemptViewSet, basename="delivery-attempt")
router.register("meetings", MeetingViewSet, basename="meeting")

urlpatterns = router.urls

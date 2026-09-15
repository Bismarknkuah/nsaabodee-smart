from rest_framework.routers import DefaultRouter

from .views import MemberTaskViewSet

router = DefaultRouter()
router.register("tasks", MemberTaskViewSet, basename="task")

urlpatterns = router.urls

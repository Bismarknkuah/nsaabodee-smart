from django.urls import path

from .views import AuditLogView

urlpatterns = [
    path("audit-log/", AuditLogView.as_view(), name="audit-log"),
]

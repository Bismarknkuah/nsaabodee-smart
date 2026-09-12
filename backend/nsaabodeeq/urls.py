from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("tenants.urls")),
    path("api/", include("families.urls")),
    path("api/", include("funerals.urls")),
    path("api/", include("members.urls")),
    path("api/", include("contribution_rules.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("gifts.urls")),
    path("api/", include("funeral_logistics.urls")),
    path("api/", include("reports.urls")),
    path("api/", include("communication.urls")),
    path("api/", include("dashboard.urls")),
    path("api/", include("payments.urls")),
    path("api/", include("ai_features.urls")),
    path("api/", include("tasks.urls")),
    path("api/", include("family_funds.urls")),
    path("api/", include("messaging.urls")),
    path("api/", include("audit_log.urls")),
    path("api/", include("support.urls")),
    path("api/", include("welfare.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

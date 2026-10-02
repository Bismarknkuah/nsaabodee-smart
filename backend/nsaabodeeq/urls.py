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
    path("api/", include("documents.urls")),
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

# Uploaded files (member photos, logos, announcement images, documents). Django's `static()` helper returns
# nothing when DEBUG is off, which is why every uploaded picture 404'd in production ("the pictures on the
# homepage aren't showing, including those I upload"). When an S3 bucket is configured the storage backend
# hands out its own URLs and this route is simply never hit; without one, serve from MEDIA_ROOT in every
# environment. (Railway's disk is wiped on each deploy, so S3 — AWS_STORAGE_BUCKET_NAME and friends — is still
# the durable answer; this makes the pictures show in the meantime.)
from django.urls import re_path
from django.views.static import serve as _serve_media

urlpatterns += [re_path(r"^media/(?P<path>.*)$", _serve_media, {"document_root": settings.MEDIA_ROOT}, name="media")]

from django.urls import path

from .views import DocumentDownloadView, DocumentListUploadView

urlpatterns = [
    path("documents/", DocumentListUploadView.as_view(), name="documents"),
    path("documents/<uuid:document_id>/", DocumentDownloadView.as_view(), name="document-download"),
]

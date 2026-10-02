import uuid

from django.conf import settings
from django.db import models


def _upload_to(instance, filename):
    scope = f"f{str(instance.family_id)[:8]}" if instance.family_id else "c"
    return f"docs/{str(instance.community_id)[:8]}/{scope}/{uuid.uuid4().hex[:8]}-{filename[-80:]}"


class Document(models.Model):
    """
    'All financial secretaries and all secretaries at all levels should
    be able to upload or download files, PDF or Excel documents.' A
    community's records (family=None) or one family's own (family set):
    minutes, statements, spreadsheets, scanned receipts.
    """

    ALLOWED_EXTENSIONS = ("pdf", "xlsx", "xls", "csv", "docx", "doc", "png", "jpg", "jpeg")
    MAX_BYTES = 15 * 1024 * 1024

    class Kind(models.TextChoices):
        MINUTES = "minutes", "Meeting minutes"
        STATEMENT = "statement", "Financial statement"
        RECEIPT = "receipt", "Receipt / invoice"
        REGISTER = "register", "Register / list"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="documents")
    family = models.ForeignKey("families.Family", null=True, blank=True, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTHER)
    file = models.FileField(upload_to=_upload_to, max_length=300)
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

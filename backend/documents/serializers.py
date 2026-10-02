from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    family_name = serializers.CharField(source="family.name", read_only=True, default=None)
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True, default=None)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = Document
        fields = ["id", "title", "kind", "kind_label", "original_name", "size_bytes", "family", "family_name", "uploaded_by_username", "created_at"]

from rest_framework import serializers

from .models import AuditLogEntry


class AuditLogEntrySerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source="community.name", read_only=True, default=None)

    class Meta:
        model = AuditLogEntry
        fields = [
            "id", "category", "action", "actor_username", "actor_role", "community", "community_name",
            "target_type", "target_id", "target_label", "description", "metadata", "created_at",
        ]
        read_only_fields = fields

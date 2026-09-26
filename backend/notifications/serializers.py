from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    related_member_name = serializers.CharField(source="related_member.full_name", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ["id", "category", "message", "recipient_role", "related_member", "related_member_name",
                  "is_read", "created_at"]

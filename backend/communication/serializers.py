from rest_framework import serializers

from .models import CommunityMeeting, DeliveryAttempt


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAttempt
        fields = ["id", "notification", "channel", "recipient_address", "status", "provider_response", "attempted_at"]


class CommunityMeetingSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = CommunityMeeting
        fields = ["id", "title", "description", "scheduled_for", "location", "is_cancelled", "created_by_username", "created_at"]
        read_only_fields = ["id", "is_cancelled", "created_by_username", "created_at"]

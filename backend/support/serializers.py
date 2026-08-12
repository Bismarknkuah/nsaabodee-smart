from rest_framework import serializers

from .models import SupportTicket, SupportTicketMessage


class SupportTicketSerializer(serializers.ModelSerializer):
    submitted_by_username = serializers.CharField(source="submitted_by.username", read_only=True)
    community_name = serializers.CharField(source="community.name", read_only=True, default=None)

    class Meta:
        model = SupportTicket
        fields = [
            "id", "submitted_by_username", "community_name", "subject", "description",
            "status", "priority", "created_at", "updated_at", "resolved_at",
        ]
        read_only_fields = [f for f in fields if f not in ("subject", "description", "priority")]


class SupportTicketMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = SupportTicketMessage
        fields = ["id", "ticket", "sender_username", "content", "created_at"]
        read_only_fields = ["id", "ticket", "sender_username", "created_at"]

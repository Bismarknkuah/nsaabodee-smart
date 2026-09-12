from rest_framework import serializers

from .models import Channel, ChannelMessage


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ["id", "channel_type", "name", "community", "family", "created_at"]
        read_only_fields = fields


class ChannelMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    sender_role = serializers.CharField(source="sender.role", read_only=True)

    class Meta:
        model = ChannelMessage
        fields = ["id", "channel", "sender_username", "sender_role", "content", "created_at"]
        read_only_fields = ["id", "channel", "sender_username", "sender_role", "created_at"]

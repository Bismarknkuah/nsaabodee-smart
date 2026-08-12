from rest_framework import serializers

from .models import ChatbotMessage, MeetingSummary, SuspiciousTransactionFlag


class MeetingSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingSummary
        fields = ["id", "transcript", "summary", "decisions", "action_items", "created_at"]
        read_only_fields = ["id", "summary", "decisions", "action_items", "created_at"]


class SuspiciousTransactionFlagSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="payment.obligation.member.full_name", read_only=True)
    amount = serializers.DecimalField(source="payment.amount", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = SuspiciousTransactionFlag
        fields = ["id", "payment", "member_name", "amount", "reason", "detail", "review_status", "flagged_at"]
        read_only_fields = ["id", "member_name", "amount", "reason", "detail", "flagged_at"]


class ChatbotMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotMessage
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = fields


class AskChatbotSerializer(serializers.Serializer):
    """'Add chatbot to all user types.' Pure input validation — the view calls services.ask_chatbot directly, the same pattern MeetingSummaryView uses, so a genuine 503 (provider not configured) stays distinguishable from an ordinary 400 (bad input)."""
    message = serializers.CharField()

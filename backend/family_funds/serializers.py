from rest_framework import serializers

from .models import FamilyFund, FamilyFundContribution, FamilyFuneralExpense


class FamilyFundSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyFund
        fields = ["id", "family", "name", "description", "is_active", "created_at"]
        read_only_fields = ["id", "family", "is_active", "created_at"]


class FamilyFundContributionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = FamilyFundContribution
        fields = ["id", "fund", "member", "member_name", "amount", "payment_method", "receipt_number", "paid_at"]
        read_only_fields = ["id", "member_name", "receipt_number", "paid_at"]


class FamilyFuneralExpenseSerializer(serializers.ModelSerializer):
    paid_by_member_name = serializers.CharField(source="paid_by_member.full_name", read_only=True, default=None)
    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)
    approved_by_name = serializers.CharField(source="approved_by.get_full_name", read_only=True, default=None)
    funeral_deceased_name = serializers.CharField(source="funeral_event.deceased_name", read_only=True)

    class Meta:
        model = FamilyFuneralExpense
        fields = [
            "id", "family", "funeral_event", "funeral_deceased_name", "item_name", "seller_name",
            "seller_contact", "amount", "date_purchased", "paid_by_member", "paid_by_member_name",
            "status", "recorded_by_name", "approved_by_name", "approved_at", "rejection_reason", "created_at",
        ]
        read_only_fields = [
            "id", "family", "funeral_deceased_name", "paid_by_member_name", "status",
            "recorded_by_name", "approved_by_name", "approved_at", "rejection_reason", "created_at",
        ]

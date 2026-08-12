from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from members.models import Member
from . import services
from .models import FuneralAttendance, FuneralExpense


class FuneralExpenseSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source="buyer.full_name", read_only=True, default=None)
    recorded_by_username = serializers.CharField(source="recorded_by.username", read_only=True, default=None)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True, default=None)
    balance_owed = serializers.SerializerMethodField()

    class Meta:
        model = FuneralExpense
        fields = [
            "id", "funeral_event", "description", "category", "item_name", "quantity", "unit_price", "amount",
            "supplier_name", "buyer", "buyer_name", "notes", "invoice",
            "payment_method", "status", "amount_paid", "balance_owed",
            "voucher_number", "incurred_on", "recorded_by_username", "approved_by_username", "approved_at", "created_at",
        ]
        read_only_fields = ["id", "voucher_number", "created_at", "recorded_by_username", "approved_by_username", "approved_at", "balance_owed"]

    def get_balance_owed(self, obj):
        return str(obj.amount - obj.amount_paid)


class RecordExpenseSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255)
    category = serializers.ChoiceField(choices=FuneralExpense.Category.choices)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)
    item_name = serializers.CharField(required=False, allow_blank=True, default="")
    supplier_name = serializers.CharField(required=False, allow_blank=True, default="")
    buyer_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    invoice = serializers.FileField(required=False, allow_null=True, default=None)
    payment_method = serializers.ChoiceField(choices=FuneralExpense.PaymentMethod.choices,
                                              required=False, default=FuneralExpense.PaymentMethod.CASH)
    incurred_on = serializers.DateField()
    client_op_id = serializers.UUIDField(required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        data = dict(self.validated_data)
        buyer_id = data.pop("buyer_id", None)
        buyer = None
        if buyer_id:
            try:
                buyer = Member.objects.get(id=buyer_id, community=funeral.community)
            except Member.DoesNotExist:
                raise serializers.ValidationError({"buyer_id": "Member not found in this community."})
        try:
            return services.record_expense(funeral=funeral, recorded_by=request.user, buyer=buyer, **data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class DecideExpenseStatusSerializer(serializers.Serializer):
    """'Payment status... Credit payments create liabilities.'"""
    status = serializers.ChoiceField(choices=FuneralExpense.Status.choices)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)

    def save(self, **kwargs):
        request = self.context["request"]
        expense = self.context["expense"]
        try:
            return services.decide_expense_status(expense=expense, actor=request.user, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class FuneralAttendanceSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True, default=None)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = FuneralAttendance
        fields = ["id", "funeral_event", "member", "member_name", "guest_name", "display_name", "attended_at"]

    def get_display_name(self, obj):
        return obj.member.full_name if obj.member_id else obj.guest_name


class RecordAttendanceSerializer(serializers.Serializer):
    member_id = serializers.UUIDField(required=False, allow_null=True)
    guest_name = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        member = None
        if self.validated_data.get("member_id"):
            try:
                member = Member.objects.get(id=self.validated_data["member_id"], community=request.user.community)
            except Member.DoesNotExist:
                raise serializers.ValidationError({"member_id": "Member not found in this community."})
        try:
            return services.record_attendance(
                funeral=funeral, member=member, guest_name=self.validated_data.get("guest_name", ""),
                recorded_by=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))

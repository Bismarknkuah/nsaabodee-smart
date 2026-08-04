from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from funerals.models import ContributionObligation, FuneralEvent
from members.models import Member
from . import services
from .models import MomoPaymentRequest


class MomoPaymentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MomoPaymentRequest
        fields = [
            "id", "target_type", "obligation", "funeral_event", "donor_name", "received_by_member",
            "reference_id", "phone_number", "amount", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "target_type", "reference_id", "status", "created_at", "updated_at"]


class SubmitMomoOtpSerializer(serializers.Serializer):
    """The one extra step MTN mobile money (via Paystack) needs — see payments.services.submit_momo_otp."""
    otp = serializers.CharField(max_length=10)


class InitiateMomoPaymentSerializer(serializers.Serializer):
    """Mandatory contribution (Ledger 1) via MoMo."""
    obligation_id = serializers.UUIDField()
    phone_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            obligation = ContributionObligation.objects.get(
                id=self.validated_data["obligation_id"], community=request.user.community
            )
        except ContributionObligation.DoesNotExist:
            raise serializers.ValidationError({"obligation_id": "Obligation not found in this community."})

        try:
            return services.initiate_momo_payment(
                obligation=obligation,
                phone_number=self.validated_data["phone_number"],
                amount=self.validated_data["amount"],
                initiated_by=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class InitiateMomoGiftPaymentSerializer(serializers.Serializer):
    """Gift / donation (Ledger 2) via MoMo — optionally earmarked to a registered donation-account holder."""
    funeral_id = serializers.UUIDField()
    phone_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    donor_name = serializers.CharField(max_length=255)
    received_by_member_id = serializers.UUIDField(required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        data = self.validated_data
        try:
            funeral = FuneralEvent.objects.get(id=data["funeral_id"], community=request.user.community)
        except FuneralEvent.DoesNotExist:
            raise serializers.ValidationError({"funeral_id": "Funeral not found in this community."})

        received_by_member = None
        if data.get("received_by_member_id"):
            try:
                received_by_member = Member.objects.get(id=data["received_by_member_id"], community=request.user.community)
            except Member.DoesNotExist:
                raise serializers.ValidationError({"received_by_member_id": "Member not found in this community."})

        try:
            return services.initiate_momo_gift_payment(
                funeral=funeral,
                phone_number=data["phone_number"],
                amount=data["amount"],
                donor_name=data["donor_name"],
                received_by_member=received_by_member,
                initiated_by=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))

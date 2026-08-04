from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from families.models import Family
from members.models import Member
from . import services
from .models import DonationAccountRegistration, GiftDonation


class GiftDonationSerializer(serializers.ModelSerializer):
    donor_member_name = serializers.CharField(source="donor_member.full_name", read_only=True, default=None)
    recipient_family_name = serializers.CharField(source="recipient_family.name", read_only=True)
    received_by_member_name = serializers.CharField(source="received_by_member.full_name", read_only=True, default=None)
    total_value = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = GiftDonation
        fields = [
            "id", "funeral_event", "recipient_family", "recipient_family_name",
            "donor_name", "donor_phone", "donor_member", "donor_member_name",
            "donor_category", "donor_hometown", "connected_relative_name",
            "relationship_to_recipient",
            "received_by_member", "received_by_member_name",
            "amount_cash", "gift_item", "estimated_item_value", "total_value",
            "payment_method", "receipt_number", "given_at",
        ]
        read_only_fields = ["id", "recipient_family_name", "donor_member_name", "received_by_member_name",
                            "total_value", "receipt_number", "given_at"]


class MaskedGiftDonationSerializer(GiftDonationSerializer):
    """
    'They must not have access to the private information of individuals
    who register solely to make gift donations unless that information
    is required for reconciliation, auditing, or legal compliance.' The
    financial and categorical picture (amount, item, category, method,
    receipt, timing) stays fully real — "monitor collections" and "view
    financial summaries" are explicitly still allowed. Only the donor's
    own identifying details are replaced with a stable, anonymous label
    (the same donor keeps the same label within one funeral's list, so
    patterns — "Donor #3 gave three times" — are still visible without
    ever revealing who Donor #3 actually is).
    """
    donor_name = serializers.SerializerMethodField()
    donor_phone = serializers.SerializerMethodField()
    donor_hometown = serializers.SerializerMethodField()
    connected_relative_name = serializers.SerializerMethodField()

    def get_donor_name(self, obj):
        return f"Donor #{self._anonymous_index(obj)}"

    def get_donor_phone(self, obj):
        return ""

    def get_donor_hometown(self, obj):
        return ""

    def get_connected_relative_name(self, obj):
        return ""

    def _anonymous_index(self, obj) -> int:
        registry = self.context.setdefault("_donor_anonymity_registry", {})
        key = obj.donor_phone or obj.donor_name
        if key not in registry:
            registry[key] = len(registry) + 1
        return registry[key]


class RecordGiftDonationSerializer(serializers.Serializer):
    donor_name = serializers.CharField(max_length=255)
    donor_phone = serializers.CharField(required=False, allow_blank=True, default="")
    donor_member_id = serializers.UUIDField(required=False, allow_null=True)
    donor_category = serializers.ChoiceField(choices=GiftDonation.DonorCategory.choices, required=False, allow_null=True, default=None)
    donor_hometown = serializers.CharField(required=False, allow_blank=True, default="")
    connected_relative_name = serializers.CharField(required=False, allow_blank=True, default="")
    relationship_to_recipient = serializers.CharField(required=False, allow_blank=True, default="")
    received_by_member_id = serializers.UUIDField(required=False, allow_null=True)
    amount_cash = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default="0")
    gift_item = serializers.CharField(required=False, allow_blank=True, default="")
    estimated_item_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    payment_method = serializers.ChoiceField(choices=GiftDonation.PaymentMethod.choices, required=False,
                                              default=GiftDonation.PaymentMethod.CASH)
    recipient_family_id = serializers.UUIDField(required=False, allow_null=True)
    client_op_id = serializers.UUIDField(required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        data = self.validated_data

        donor_member = None
        if data.get("donor_member_id"):
            try:
                donor_member = Member.objects.get(id=data["donor_member_id"], community=request.user.community)
            except Member.DoesNotExist:
                raise serializers.ValidationError({"donor_member_id": "Member not found in this community."})

        received_by_member = None
        if data.get("received_by_member_id"):
            try:
                received_by_member = Member.objects.get(id=data["received_by_member_id"], community=request.user.community)
            except Member.DoesNotExist:
                raise serializers.ValidationError({"received_by_member_id": "Member not found in this community."})

        recipient_family = None
        if data.get("recipient_family_id"):
            try:
                recipient_family = Family.objects.get(id=data["recipient_family_id"], community=request.user.community)
            except Family.DoesNotExist:
                raise serializers.ValidationError({"recipient_family_id": "Family not found in this community."})

        try:
            return services.record_gift_donation(
                funeral=funeral,
                donor_name=data["donor_name"],
                donor_phone=data.get("donor_phone", ""),
                donor_member=donor_member,
                donor_category=data.get("donor_category"),
                donor_hometown=data.get("donor_hometown", ""),
                connected_relative_name=data.get("connected_relative_name", ""),
                relationship_to_recipient=data.get("relationship_to_recipient", ""),
                received_by_member=received_by_member,
                amount_cash=data.get("amount_cash", 0),
                gift_item=data.get("gift_item", ""),
                estimated_item_value=data.get("estimated_item_value"),
                payment_method=data.get("payment_method", GiftDonation.PaymentMethod.CASH),
                collected_by=request.user,
                client_op_id=data.get("client_op_id"),
                recipient_family=recipient_family,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class DonationAccountRegistrationSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = DonationAccountRegistration
        fields = ["id", "funeral_event", "member", "member_name", "is_active", "registered_at"]
        read_only_fields = ["id", "member_name", "is_active", "registered_at"]


class RegisterDonationAccountHolderSerializer(serializers.Serializer):
    member_id = serializers.UUIDField()

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        try:
            member = Member.objects.get(id=self.validated_data["member_id"], community=request.user.community)
        except Member.DoesNotExist:
            raise serializers.ValidationError({"member_id": "Member not found in this community."})

        try:
            return services.register_donation_account_holder(funeral=funeral, member=member, actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))

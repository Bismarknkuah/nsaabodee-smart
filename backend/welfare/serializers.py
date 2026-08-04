from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from families.models import Family
from members.models import Member
from . import services
from .models import ContributionCampaign, ContributionCategory, WelfareObligation, WelfarePayment


class ContributionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributionCategory
        fields = [
            "id", "name", "purpose", "is_mandatory", "amount_type", "fixed_amount",
            "frequency", "required_family_approvals", "is_active", "created_at",
        ]
        read_only_fields = ["id", "is_active", "created_at"]


class CreateContributionCategorySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    purpose = serializers.CharField(required=False, allow_blank=True, default="")
    is_mandatory = serializers.BooleanField(required=False, default=True)
    amount_type = serializers.ChoiceField(choices=ContributionCategory.AmountType.choices, required=False, default=ContributionCategory.AmountType.FIXED)
    fixed_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)
    frequency = serializers.ChoiceField(choices=ContributionCategory.Frequency.choices, required=False, default=ContributionCategory.Frequency.ONE_TIME)
    required_family_approvals = serializers.IntegerField(required=False, default=2, min_value=1, max_value=10)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            return services.create_contribution_category(community=request.user.community, actor=request.user, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ContributionCampaignSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    family_name = serializers.CharField(source="family.name", read_only=True, default=None)
    initiated_by_username = serializers.CharField(source="initiated_by.username", read_only=True, default=None)

    class Meta:
        model = ContributionCampaign
        fields = [
            "id", "category", "category_name", "community", "family", "family_name",
            "title", "amount", "due_date", "status", "initiated_by_username", "created_at",
        ]
        read_only_fields = ["id", "category_name", "community", "family_name", "status", "initiated_by_username", "created_at"]


class InitiateCommunityCampaignSerializer(serializers.Serializer):
    category_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)
    due_date = serializers.DateField(required=False, allow_null=True, default=None)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            category = ContributionCategory.objects.get(id=self.validated_data["category_id"], community=request.user.community)
        except ContributionCategory.DoesNotExist:
            raise serializers.ValidationError({"category_id": "Category not found in your community."})
        try:
            return services.initiate_community_campaign(
                category=category, title=self.validated_data["title"], amount=self.validated_data["amount"],
                due_date=self.validated_data["due_date"], actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class InitiateFamilyCampaignSerializer(serializers.Serializer):
    category_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, default=None)
    due_date = serializers.DateField(required=False, allow_null=True, default=None)

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            category = ContributionCategory.objects.get(id=self.validated_data["category_id"], community=request.user.community)
        except ContributionCategory.DoesNotExist:
            raise serializers.ValidationError({"category_id": "Category not found in your community."})
        try:
            return services.initiate_family_campaign(
                category=category, family=family, title=self.validated_data["title"], amount=self.validated_data["amount"],
                due_date=self.validated_data["due_date"], actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class DecideFamilyCampaignSerializer(serializers.Serializer):
    approve = serializers.BooleanField(default=True)

    def save(self, **kwargs):
        request = self.context["request"]
        campaign = self.context["campaign"]
        try:
            return services.decide_family_campaign(campaign=campaign, actor=request.user, approve=self.validated_data["approve"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class WelfareObligationSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)

    class Meta:
        model = WelfareObligation
        fields = ["id", "campaign", "member", "member_name", "expected_amount", "amount_paid", "balance", "payment_status", "generated_at"]
        read_only_fields = fields


class RecordWelfarePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    method = serializers.ChoiceField(choices=WelfarePayment.Method.choices)
    client_op_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def save(self, **kwargs):
        request = self.context["request"]
        obligation = self.context["obligation"]
        try:
            return services.record_welfare_payment(obligation=obligation, collector=request.user, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))

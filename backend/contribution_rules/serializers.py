from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from families.models import Family
from . import services


class UpdateGeneralRatesSerializer(serializers.Serializer):
    male_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    female_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            services.update_general_rates(
                community=request.user.community,
                male_amount=self.validated_data["male_amount"],
                female_amount=self.validated_data["female_amount"],
                reason=self.validated_data.get("reason", ""),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return services.list_rules(request.user.community)


class UpdateFamilyTierRatesSerializer(serializers.Serializer):
    head_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    senior_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    junior_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    woman_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    town_leader_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            services.update_family_tier_rates(
                community=request.user.community,
                head_amount=self.validated_data["head_amount"],
                senior_amount=self.validated_data["senior_amount"],
                junior_amount=self.validated_data["junior_amount"],
                woman_amount=self.validated_data["woman_amount"],
                town_leader_amount=self.validated_data["town_leader_amount"],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return services.list_rules(request.user.community)


class SetStatusExemptionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["active", "inactive", "deceased"])
    is_exempt = serializers.BooleanField()

    def save(self, **kwargs):
        request = self.context["request"]
        services.set_status_exemption(
            community=request.user.community,
            status=self.validated_data["status"],
            is_exempt=self.validated_data["is_exempt"],
            actor=request.user,
        )
        return services.list_rules(request.user.community)


class UpdateDefaulterThresholdsSerializer(serializers.Serializer):
    warning = serializers.IntegerField(min_value=1)
    high_warning = serializers.IntegerField(min_value=1)
    flag = serializers.IntegerField(min_value=1)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            services.update_defaulter_thresholds(
                community=request.user.community,
                warning=self.validated_data["warning"],
                high_warning=self.validated_data["high_warning"],
                flag=self.validated_data["flag"],
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return services.list_rules(request.user.community)


class PreviewObligationsSerializer(serializers.Serializer):
    deceased_family_id = serializers.UUIDField()

    def to_preview(self, community):
        try:
            family = Family.objects.get(id=self.validated_data["deceased_family_id"], community=community)
        except Family.DoesNotExist:
            raise serializers.ValidationError({"deceased_family_id": "Family not found in this community."})
        return services.preview_obligations(community=community, deceased_family=family)

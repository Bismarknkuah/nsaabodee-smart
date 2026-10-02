from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from families.models import Family
from members.models import Member
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


class UpdateTownElderPerTitleRatesSerializer(serializers.Serializer):
    """'The expected contribution may differ according to the elder's official position' — every title independent and optional."""
    chief_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    queen_mother_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    linguist_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    other_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            community = services.set_town_elder_per_title_rates(
                community=request.user.community,
                chief_amount=self.validated_data.get("chief_amount"),
                queen_mother_amount=self.validated_data.get("queen_mother_amount"),
                linguist_amount=self.validated_data.get("linguist_amount"),
                other_amount=self.validated_data.get("other_amount"),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
        return {
            "default_town_leader_amount": str(community.default_town_leader_amount),
            "default_town_elder_chief_amount": str(community.default_town_elder_chief_amount) if community.default_town_elder_chief_amount is not None else None,
            "default_town_elder_queen_mother_amount": str(community.default_town_elder_queen_mother_amount) if community.default_town_elder_queen_mother_amount is not None else None,
            "default_town_elder_linguist_amount": str(community.default_town_elder_linguist_amount) if community.default_town_elder_linguist_amount is not None else None,
            "default_town_elder_other_amount": str(community.default_town_elder_other_amount) if community.default_town_elder_other_amount is not None else None,
        }


class SetFamilyPositionRateSerializer(serializers.Serializer):
    """'The exact amounts must remain configurable... do not implement the Family Ledger as every family member pays GHS X.'"""
    position = serializers.ChoiceField(choices=[c[0] for c in Member.FamilyPosition.choices])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            services.set_family_position_rate(
                community=request.user.community,
                position=self.validated_data["position"],
                amount=self.validated_data["amount"],
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
        from .models import FamilyPositionRate
        return {
            r.position: str(r.amount)
            for r in FamilyPositionRate.objects.filter(community=request.user.community)
        }

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from members.models import Member
from . import services
from .models import Family, FamilyAuditLog, FamilyOfficerPosition


class FamilyHeadMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "full_name", "gender", "status"]


class FamilySerializer(serializers.ModelSerializer):
    family_head = FamilyHeadMiniSerializer(read_only=True)
    family_secretary = FamilyHeadMiniSerializer(read_only=True)
    family_treasurer = FamilyHeadMiniSerializer(read_only=True)
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Family
        fields = [
            "id", "name", "slug", "description", "status",
            "family_head", "family_secretary", "family_treasurer", "member_count", "merged_into",
            "recommended_family_rate", "standing_family_rate",
            "created_at", "updated_at", "deactivated_at", "deleted_at",
        ]
        read_only_fields = [
            "id", "slug", "status", "family_head", "family_secretary", "family_treasurer", "member_count",
            "merged_into", "recommended_family_rate", "standing_family_rate",
            "created_at", "updated_at", "deactivated_at", "deleted_at",
        ]


class FamilyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            return services.create_family(
                community=request.user.community,
                name=self.validated_data["name"],
                description=self.validated_data.get("description", ""),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class RegisterFamilyWithHeadSerializer(serializers.Serializer):
    """
    'When a new family is created, the system must require the
    registration of the Family Head as part of the process.' The
    recommended way to create a family going forward — name/description
    plus a genuinely required Family Head profile and login, all created
    together. FamilyCreateSerializer above is untouched and still
    available for the rarer case a head genuinely isn't known yet.
    """
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")

    head_full_name = serializers.CharField(max_length=255)
    head_gender = serializers.ChoiceField(choices=[("male", "Male"), ("female", "Female")])
    head_username = serializers.CharField(max_length=150)
    head_password = serializers.CharField(write_only=True, min_length=8)

    head_phone = serializers.CharField(required=False, allow_blank=True, default="")
    head_email = serializers.EmailField(required=False, allow_blank=True, default="")
    head_ghana_card_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    head_address = serializers.CharField(required=False, allow_blank=True, default="")
    head_occupation = serializers.CharField(required=False, allow_blank=True, default="")
    head_date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    head_photo = serializers.ImageField(required=False, allow_null=True, default=None)

    def save(self, **kwargs):
        request = self.context["request"]
        data = self.validated_data
        try:
            family, head_member, head_user = services.register_family_with_head(
                community=request.user.community, name=data["name"], description=data.get("description", ""),
                actor=request.user,
                head_full_name=data["head_full_name"], head_gender=data["head_gender"],
                head_username=data["head_username"], head_password=data["head_password"],
                head_phone=data.get("head_phone", ""), head_email=data.get("head_email", ""),
                head_ghana_card_number=data.get("head_ghana_card_number") or None,
                head_address=data.get("head_address", ""), head_occupation=data.get("head_occupation", ""),
                head_date_of_birth=data.get("head_date_of_birth"), head_photo=data.get("head_photo"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
        return {"family": family, "head_member": head_member, "head_user": head_user}


class FamilyRenameSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            return services.rename_family(family=family, new_name=self.validated_data["name"], actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class FamilyMergeSerializer(serializers.Serializer):
    target_family_id = serializers.UUIDField()

    def save(self, **kwargs):
        request = self.context["request"]
        source = self.context["family"]
        try:
            target = Family.objects.get(
                id=self.validated_data["target_family_id"], community=request.user.community
            )
        except Family.DoesNotExist:
            raise serializers.ValidationError({"target_family_id": "Target family not found in this community."})
        try:
            return services.merge_families(source=source, target=target, actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class FamilyDeleteSerializer(serializers.Serializer):
    force = serializers.BooleanField(required=False, default=False)

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            return services.delete_family(family=family, actor=request.user, force=self.validated_data.get("force", False))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class TransferMembersSerializer(serializers.Serializer):
    member_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    target_family_id = serializers.UUIDField()

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            target_family = Family.objects.get(
                id=self.validated_data["target_family_id"], community=request.user.community
            )
        except Family.DoesNotExist:
            raise serializers.ValidationError({"target_family_id": "Target family not found in this community."})
        try:
            return services.transfer_members(
                member_ids=self.validated_data["member_ids"],
                target_family=target_family,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class AssignFamilyHeadSerializer(serializers.Serializer):
    member_id = serializers.UUIDField()

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            member = Member.objects.get(id=self.validated_data["member_id"], community=request.user.community)
        except Member.DoesNotExist:
            raise serializers.ValidationError({"member_id": "Member not found in this community."})
        try:
            return services.assign_family_head(family=family, member=member, actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class AssignFamilyOfficerSerializer(serializers.Serializer):
    member_id = serializers.UUIDField()
    officer_role = serializers.ChoiceField(choices=["secretary", "treasurer"])

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            member = Member.objects.get(id=self.validated_data["member_id"], community=request.user.community)
        except Member.DoesNotExist:
            raise serializers.ValidationError({"member_id": "Member not found in this community."})
        try:
            return services.assign_family_officer(
                family=family, member=member, officer_role=self.validated_data["officer_role"], actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class FamilyOfficerPositionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    appointed_by_username = serializers.CharField(source="appointed_by.username", read_only=True, default=None)

    class Meta:
        model = FamilyOfficerPosition
        fields = ["id", "family", "member", "member_name", "title", "appointed_by_username", "appointed_at"]
        read_only_fields = ["id", "family", "member_name", "appointed_by_username", "appointed_at"]


class AppointFamilyOfficerPositionSerializer(serializers.Serializer):
    """'Family Head can create: Assistant Family Head... Organizer, Welfare Officer... Custom positions allowed.'"""
    member_id = serializers.UUIDField()
    title = serializers.CharField(max_length=100)

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            member = Member.objects.get(id=self.validated_data["member_id"], community=request.user.community)
        except Member.DoesNotExist:
            raise serializers.ValidationError({"member_id": "Member not found in this community."})
        try:
            return services.appoint_family_officer_position(family=family, member=member, title=self.validated_data["title"], actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class RecommendFamilyRateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            return services.recommend_family_rate(
                family=family, amount=self.validated_data["amount"], actor=request.user
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class ApproveFamilyRateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            return services.approve_family_rate(
                family=family, actor=request.user, amount=self.validated_data.get("amount")
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class RejectFamilyRateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        request = self.context["request"]
        family = self.context["family"]
        try:
            return services.reject_family_rate(
                family=family, actor=request.user, reason=self.validated_data.get("reason", "")
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class FamilyAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True, default="")

    class Meta:
        model = FamilyAuditLog
        fields = ["id", "family", "action", "actor", "actor_name", "detail", "created_at"]

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from . import services
from .models import Announcement, AnnouncementReviewLog, Community, CommunityPayoutAccount, FeatureFlag, HomepageImage, PlanInterestSubmission, PlatformBillingRecord


class CommunitySerializer(serializers.ModelSerializer):
    is_access_expired = serializers.BooleanField(read_only=True)
    access_days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Community
        fields = [
            "id", "name", "slug", "region", "is_active", "default_general_male_amount", "default_general_female_amount",
            "created_at", "access_plan", "access_expires_at", "is_access_expired", "access_days_remaining",
            "logo", "primary_color", "secondary_color", "tagline", "required_funeral_approvals",
        ]
        read_only_fields = ["id", "slug", "is_active", "created_at", "is_access_expired", "access_days_remaining"]


class UpdateCommunitySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    region = serializers.CharField(max_length=255, required=False, allow_blank=True)
    default_general_male_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    default_general_female_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def save(self, **kwargs):
        community = self.context["community"]
        try:
            return services.update_community(community, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class OnboardCommunitySerializer(serializers.Serializer):
    community_name = serializers.CharField(max_length=255)
    region = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    admin_username = serializers.CharField(max_length=150)
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_email = serializers.EmailField(required=False, allow_blank=True, default="")
    default_general_male_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default="5")
    default_general_female_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default="3")
    # "Some people can also decide to rent or use the service
    # temporarily" — omit for the normal, ongoing/permanent community;
    # set this to create one with a real, enforced deadline from day one.
    access_days = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)
    access_plan = serializers.ChoiceField(choices=Community.AccessPlan.choices, required=False, default=None, allow_null=True)
    # "During registration, they must provide their preferred payout
    # account... All donations intended for the bereaved family should
    # be transferred directly to the account they provide." Required
    # ONLY for a temporary client (access_days set) — a permanent
    # community configures this afterward from its own admin console,
    # since it isn't tied to a single event the same way.
    payout_account_type = serializers.ChoiceField(choices=CommunityPayoutAccount.AccountType.choices, required=False, allow_null=True, default=None)
    payout_provider_name = serializers.CharField(required=False, allow_blank=True, default="")
    payout_account_number = serializers.CharField(required=False, allow_blank=True, default="")
    payout_account_holder_name = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("access_days") and not (attrs.get("payout_account_type") and attrs.get("payout_account_number") and attrs.get("payout_account_holder_name")):
            raise serializers.ValidationError(
                "A temporary/rental registration must include a payout account (Mobile Money or bank) — "
                "that's where donations for the bereaved family will be directed."
            )
        return attrs

    def save(self, **kwargs):
        data = self.validated_data
        try:
            community, admin_user = services.onboard_new_community(
                community_name=data["community_name"],
                region=data.get("region", ""),
                admin_username=data["admin_username"],
                admin_password=data["admin_password"],
                admin_email=data.get("admin_email", ""),
                default_general_male_amount=data.get("default_general_male_amount", 5),
                default_general_female_amount=data.get("default_general_female_amount", 3),
                actor=self.context["request"].user if "request" in self.context else None,
            )
            if data.get("access_days"):
                services.set_community_access_expiration(
                    community=community, days_from_now=data["access_days"], plan=data.get("access_plan"),
                )
            if data.get("payout_account_type"):
                # The account doesn't exist as a User yet at this exact
                # point in onboarding — but the community itself does,
                # and community-level authority is what the check
                # actually verifies, so passing admin_user (who IS this
                # community's own Community Admin) satisfies it correctly.
                services.add_payout_account(
                    community=community, actor=admin_user, account_type=data["payout_account_type"],
                    provider_name=data["payout_provider_name"], account_number=data["payout_account_number"],
                    account_holder_name=data["payout_account_holder_name"],
                )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
        return community, admin_user


class CommunityAdminSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    username = serializers.CharField()
    email = serializers.EmailField()


class AddCommunityAdminSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        community = self.context["community"]
        try:
            return services.add_community_admin(
                community=community, username=self.validated_data["username"],
                password=self.validated_data["password"], email=self.validated_data.get("email", ""),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ExtendAccessSerializer(serializers.Serializer):
    """Renews a temporary/rental community's access — extends from the current deadline if still running, or from now if it already lapsed."""
    additional_days = serializers.IntegerField(min_value=1)

    def save(self, **kwargs):
        community = self.context["community"]
        try:
            return services.extend_community_access(community=community, additional_days=self.validated_data["additional_days"], actor=self.context["request"].user if "request" in self.context else None)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class PayoutAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityPayoutAccount
        fields = ["id", "account_type", "provider_name", "account_number", "account_holder_name", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]


class AddPayoutAccountSerializer(serializers.Serializer):
    """'Configured by the Community Administrator' — for a community adding or changing where its electronic contributions should be directed, any time after it's already been set up."""
    account_type = serializers.ChoiceField(choices=CommunityPayoutAccount.AccountType.choices)
    provider_name = serializers.CharField()
    account_number = serializers.CharField()
    account_holder_name = serializers.CharField()

    def save(self, **kwargs):
        community = self.context["community"]
        actor = self.context["request"].user
        try:
            return services.add_payout_account(community=community, actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class PlatformBillingRecordSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, default=None)
    marked_paid_by_username = serializers.CharField(source="marked_paid_by.username", read_only=True, default=None)

    class Meta:
        model = PlatformBillingRecord
        fields = [
            "id", "community", "description", "amount", "status", "created_at",
            "created_by_username", "marked_paid_by_username", "marked_paid_at", "payment_reference",
        ]
        read_only_fields = fields


class CreateBillingRecordSerializer(serializers.Serializer):
    """'Subscription payments belong to the platform' — platform-admin only, exactly like writing an invoice."""
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def save(self, **kwargs):
        community = self.context["community"]
        actor = self.context["request"].user
        try:
            return services.create_billing_record(community=community, actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class MarkBillingRecordPaidSerializer(serializers.Serializer):
    payment_reference = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        record = self.context["record"]
        actor = self.context["request"].user
        try:
            return services.mark_billing_record_paid(record=record, actor=actor, payment_reference=self.validated_data.get("payment_reference", ""))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class HomepageImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = HomepageImage
        fields = ["id", "image_url", "caption", "subcaption", "display_order", "is_active", "created_at"]
        read_only_fields = ["id", "image_url", "created_at"]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class UploadHomepageImageSerializer(serializers.Serializer):
    """'The homepage live pictures... should be uploaded by the super admin.'"""
    image = serializers.ImageField()
    caption = serializers.CharField(required=False, allow_blank=True, default="")
    subcaption = serializers.CharField(required=False, allow_blank=True, default="")
    display_order = serializers.IntegerField(required=False, default=0)

    def save(self, **kwargs):
        actor = self.context["request"].user
        try:
            return services.upload_homepage_image(actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class PlanInterestSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanInterestSubmission
        fields = ["id", "plan_type", "name", "email", "phone", "message", "created_at", "contacted"]
        read_only_fields = fields


class SubmitPlanInterestSerializer(serializers.Serializer):
    """Public — 'coming soon' becomes real, actionable lead capture rather than a dead end."""
    plan_type = serializers.ChoiceField(choices=PlanInterestSubmission.PlanType.choices)
    name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    message = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        try:
            return services.submit_plan_interest(**self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class AnnouncementReviewLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = AnnouncementReviewLog
        fields = ["action", "actor_username", "notes", "created_at"]
        read_only_fields = fields


class AnnouncementSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source="community.name", read_only=True)
    submitted_by_username = serializers.CharField(source="submitted_by.username", read_only=True)
    reviewed_by_username = serializers.CharField(source="reviewed_by.username", read_only=True, default=None)
    image_url = serializers.SerializerMethodField()
    review_log = AnnouncementReviewLogSerializer(many=True, read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id", "community", "community_name", "title", "content", "image_url", "video_url", "status",
            "submitted_by_username", "submitted_at", "reviewed_by_username", "reviewed_at",
            "rejection_reason", "was_edited_by_reviewer", "review_log",
            "homepage_feature_requested", "featured_on_homepage",
        ]
        read_only_fields = [f for f in fields if f not in ("title", "content")]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class SubmitAnnouncementSerializer(serializers.Serializer):
    """'Has to be submitted by the community admin.'"""
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    image = serializers.ImageField(required=False, allow_null=True)
    video_url = serializers.URLField(required=False, allow_blank=True, default="")
    homepage_feature_requested = serializers.BooleanField(required=False, default=False)

    def save(self, **kwargs):
        community = self.context["community"]
        actor = self.context["request"].user
        try:
            return services.submit_announcement(community=community, actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ApproveAnnouncementSerializer(serializers.Serializer):
    """'The super admin can edit the content' — editing and approving happen in the same action. feature_on_homepage is the Platform Admin's own call on whatever homepage placement the Community Admin requested."""
    edited_title = serializers.CharField(required=False, allow_blank=True, default=None, allow_null=True)
    edited_content = serializers.CharField(required=False, allow_blank=True, default=None, allow_null=True)
    feature_on_homepage = serializers.BooleanField(required=False, default=None, allow_null=True)

    def save(self, **kwargs):
        announcement = self.context["announcement"]
        actor = self.context["request"].user
        try:
            return services.approve_announcement(announcement=announcement, actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class RejectAnnouncementSerializer(serializers.Serializer):
    """'Reject it with reasons.'"""
    reason = serializers.CharField()

    def save(self, **kwargs):
        announcement = self.context["announcement"]
        actor = self.context["request"].user
        try:
            return services.reject_announcement(announcement=announcement, actor=actor, reason=self.validated_data["reason"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ResubmitAnnouncementSerializer(serializers.Serializer):
    """'For the community admin to edit and resend again.'"""
    title = serializers.CharField(max_length=255, required=False, allow_null=True, default=None)
    content = serializers.CharField(required=False, allow_null=True, default=None)
    image = serializers.ImageField(required=False, allow_null=True, default=None)
    video_url = serializers.CharField(required=False, allow_null=True, default=None)

    def save(self, **kwargs):
        announcement = self.context["announcement"]
        actor = self.context["request"].user
        try:
            return services.resubmit_announcement(announcement=announcement, actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ["id", "key", "name", "description", "is_enabled", "updated_at"]
        read_only_fields = ["id", "key", "name", "description", "updated_at"]


class UpdateOwnBrandingSerializer(serializers.Serializer):
    """'Configure branding (logo, colors, community information)' — self-service, Community Admin only, own community only."""
    tagline = serializers.CharField(max_length=255, required=False, allow_blank=True)
    primary_color = serializers.CharField(max_length=7, required=False, allow_blank=True)
    secondary_color = serializers.CharField(max_length=7, required=False, allow_blank=True)

    def save(self, **kwargs):
        actor = self.context["request"].user
        try:
            return services.update_own_community_branding(actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class UploadOwnLogoSerializer(serializers.Serializer):
    logo = serializers.ImageField()

    def save(self, **kwargs):
        actor = self.context["request"].user
        try:
            return services.upload_own_community_logo(actor=actor, logo=self.validated_data["logo"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class UpdateApprovalWorkflowSerializer(serializers.Serializer):
    """'Configure approval workflows' — self-service, Community Admin only, own community only."""
    required_approvals = serializers.IntegerField(min_value=1, max_value=10)

    def save(self, **kwargs):
        actor = self.context["request"].user
        try:
            return services.update_required_funeral_approvals(actor=actor, required_approvals=self.validated_data["required_approvals"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ResetAdministratorPasswordSerializer(serializers.Serializer):
    """'Reset administrator accounts when requested.'"""
    username = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def save(self, **kwargs):
        community = self.context["community"]
        actor = self.context["request"].user
        try:
            return services.reset_administrator_password(
                community=community, username=self.validated_data["username"],
                new_password=self.validated_data["new_password"], actor=actor,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class UpdateApprovalWorkflowSerializer(serializers.Serializer):
    """'Configure approval workflows' — self-service, Community Admin only, own community only."""
    required_approvals = serializers.IntegerField(min_value=1, max_value=10)

    def save(self, **kwargs):
        actor = self.context["request"].user
        try:
            return services.update_required_funeral_approvals(actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class TerminateCommunityAccessSerializer(serializers.Serializer):
    """'Extend or terminate licenses.'"""
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        community = self.context["community"]
        actor = self.context["request"].user
        try:
            return services.terminate_community_access(community=community, actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ResetAdministratorPasswordSerializer(serializers.Serializer):
    """'Reset administrator accounts when requested.'"""
    username = serializers.CharField()
    new_password = serializers.CharField()

    def save(self, **kwargs):
        actor = self.context["request"].user
        try:
            return services.reset_administrator_password(actor=actor, **self.validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))

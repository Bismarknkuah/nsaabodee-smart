from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class CommunityMiniSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()


class NsaabodeeTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Standard username/password login (no separate "community login" step
    — which community a user belongs to is a property of their own
    account, not something they choose at sign-in), with a few extra
    claims embedded directly in the access token so a client can render
    the right UI immediately after login without an extra round-trip.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        # A fresh login issues a brand-new token, which never passes
        # through CommunityAwareJWTAuthentication (that only runs on
        # requests carrying an EXISTING token) — so the same expiration
        # check has to happen here too, or someone whose community's
        # rental period already ended could still log in for the first
        # time after it expired. AuthenticationFailed (401), not a plain
        # ValidationError (400) — matching the same status SimpleJWT
        # itself already uses for rejected credentials, so a client
        # doesn't need to special-case this rejection differently.
        user = self.user
        if user.community_id and user.community and user.community.is_access_expired:
            raise AuthenticationFailed(
                "This community's access period has ended. Contact your platform administrator to renew it."
            )
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["community_id"] = str(user.community_id) if user.community_id else None
        token["is_superuser"] = user.is_superuser
        return token


class UserMeSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source="community.name", read_only=True, default=None)
    linked_member_id = serializers.SerializerMethodField()
    linked_member_name = serializers.CharField(source="member_profile.full_name", read_only=True, default=None)
    profile_photo_url = serializers.SerializerMethodField()
    community_access_days_remaining = serializers.SerializerMethodField()
    community_access_expired = serializers.SerializerMethodField()
    can_switch_dashboard_context = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "role", "is_superuser",
            "community", "community_name", "linked_member_id", "linked_member_name", "profile_photo_url",
            "community_access_days_remaining", "community_access_expired", "phone_number",
            "active_context", "can_switch_dashboard_context",
        ]

    def get_can_switch_dashboard_context(self, obj):
        return obj.can_switch_dashboard_context()

    def get_linked_member_id(self, obj):
        member = getattr(obj, "member_profile", None)
        return str(member.id) if member else None

    def get_community_access_days_remaining(self, obj):
        return obj.community.access_days_remaining if obj.community_id else None

    def get_community_access_expired(self, obj):
        return obj.community.is_access_expired if obj.community_id else False

    def get_profile_photo_url(self, obj):
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        url = obj.profile_photo.url
        return request.build_absolute_uri(url) if request else url


class UpdateProfileSerializer(serializers.Serializer):
    """A person's own profile — email, photo, and phone number (which also enables phone+OTP login for this account). Never role, community, or username: those are administrative decisions, not self-service ones."""
    email = serializers.EmailField(required=False, allow_blank=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate_phone_number(self, value):
        value = value.strip()
        if value and User.objects.filter(phone_number=value).exclude(pk=self.context["request"].user.pk).exists():
            raise serializers.ValidationError("That phone number is already in use on another account.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        if "email" in self.validated_data:
            user.email = self.validated_data["email"]
        if "profile_photo" in self.validated_data:
            user.profile_photo = self.validated_data["profile_photo"]
        if "phone_number" in self.validated_data:
            # An empty string must become None, not "" — "" is not NULL
            # in SQL uniqueness terms, so two people both clearing their
            # phone number would otherwise collide on the unique
            # constraint the very next time either of them saved.
            user.phone_number = self.validated_data["phone_number"] or None
        user.save(update_fields=["email", "profile_photo", "phone_number"])
        return user


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class RequestOtpSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def save(self, **kwargs):
        from . import services
        try:
            return services.request_otp(self.validated_data["phone_number"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class VerifyOtpSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def save(self, **kwargs):
        from . import services
        try:
            user = services.verify_otp(self.validated_data["phone_number"], self.validated_data["code"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
        token = NsaabodeeTokenObtainPairSerializer.get_token(user)
        return {"access": str(token.access_token), "refresh": str(token)}


class ResetPasswordWithOtpSerializer(serializers.Serializer):
    """'Forgot password' — the same phone code already used for OTP sign-in, then a new password. Signs the person in immediately afterward, the same way verifying an OTP for sign-in already does, so they aren't asked to log in twice in a row."""
    phone_number = serializers.CharField()
    code = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def save(self, **kwargs):
        from . import services
        data = self.validated_data
        try:
            user = services.reset_password_with_otp(data["phone_number"], data["code"], data["new_password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
        token = NsaabodeeTokenObtainPairSerializer.get_token(user)
        return {"access": str(token.access_token), "refresh": str(token)}


class SwitchDashboardContextSerializer(serializers.Serializer):
    """'Switch to Personal Dashboard' — does not require logout, does not create another account, only changes permission context."""
    context = serializers.ChoiceField(choices=["executive", "personal"])

    def save(self, **kwargs):
        from . import services
        actor = self.context["request"].user
        try:
            return services.switch_dashboard_context(user=actor, context=self.validated_data["context"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))

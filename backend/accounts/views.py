from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User
from .serializers import ChangePasswordSerializer, NsaabodeeTokenObtainPairSerializer, RequestOtpSerializer, ResetPasswordWithOtpSerializer, SwitchDashboardContextSerializer, UpdateProfileSerializer, UserMeSerializer, VerifyOtpSerializer


class LoginView(TokenObtainPairView):
    """POST {username, password} -> {access, refresh}. The only unauthenticated endpoint in the whole API."""
    serializer_class = NsaabodeeTokenObtainPairSerializer
    permission_classes = [AllowAny]


class RefreshView(TokenRefreshView):
    """POST {refresh} -> {access, refresh} (rotated — see SIMPLE_JWT['ROTATE_REFRESH_TOKENS'])."""
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """
    POST {refresh} -> blacklists that refresh token so it can never mint
    another access token again — the real reason this app installed
    rest_framework_simplejwt.token_blacklist rather than just discarding
    tokens client-side, which would leave a lost/stolen phone's refresh
    token valid until it naturally expired (up to 30 days).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "'refresh' is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response({"detail": "Invalid or already-blacklisted refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """
    GET -> the logged-in user's own identity: role, community, and
    linked Member profile if any.
    PATCH -> update your own email/profile photo — deliberately never
    role, community, or username, which stay administrative decisions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserMeSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        serializer = UpdateProfileSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserMeSerializer(user, context={"request": request}).data)


class SwitchDashboardContextView(APIView):
    """'Switch to Personal Dashboard' — no logout, no new account, just a flip of which dashboard and which actions are live right now."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SwitchDashboardContextSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserMeSerializer(user, context={"request": request}).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed."})


class RequestOtpView(APIView):
    """Public — sending a code doesn't require being logged in already, obviously. Never reveals whether the phone number has a real account."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        demo_code = serializer.save()
        response = {"detail": "If that phone number is registered, a code has been sent."}
        if demo_code:
            # 'Demo mode' fallback only — see accounts.services.request_otp.
            # Real SMS delivery never reaches this branch; this exists so
            # phone+OTP sign-in is actually testable without a paid Twilio
            # account, not a way to skip verification for real users.
            response["demo_code"] = demo_code
            response["detail"] = "SMS isn't configured yet, so here's your code directly (demo mode only)."
        return Response(response)


class VerifyOtpView(APIView):
    """Public — this IS the login step for phone+OTP, alongside (not instead of) username/password login."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class ResetPasswordWithOtpView(APIView):
    """Public — 'forgot password.' Uses the same /api/auth/otp/request/ endpoint to send the code; this is the verify-and-set-new-password step."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordWithOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class DemoLoginView(APIView):
    """
    POST {role: "chairman"} -> {access, refresh} for that role's
    pre-seeded demo user (see accounts/management/commands/seed_demo_data.py)
    — no password needed. "Add quick demo access button for all types of
    users to test the system." Gated behind DEMO_MODE_ENABLED: a real
    production deployment turns this off entirely, since it bypasses
    password checking by design.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from django.conf import settings
        if not getattr(settings, "DEMO_MODE_ENABLED", False):
            return Response({"detail": "Demo access is not enabled on this deployment."}, status=status.HTTP_404_NOT_FOUND)

        role = request.data.get("role", "")
        try:
            user = User.objects.get(username=f"demo_{role}")
        except User.DoesNotExist:
            return Response(
                {"detail": f"No demo account for role '{role}'. Run 'python manage.py seed_demo_data' first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        refresh = NsaabodeeTokenObtainPairSerializer.get_token(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


class ManageableUsersView(APIView):
    """
    'The community admin should also have user management... where he
    can manage all the family head, community executives, community
    leader, collectors. Same as each family head... can manage on
    their family.' GET -> everyone this account is authorized to
    restrict, with their current feature settings.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from . import services

        try:
            users = services.list_manageable_users(actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        # 'Make the Family Head system settings have more options, to
        # let some act as treasurer, family contribution and donation
        # collector, and treasurer, secretary as well.' The frontend
        # needs the Head's own family to actually call the officer
        # -assignment and collector-nomination actions from this same
        # page — resolved once, here, rather than a second round trip.
        own_member = getattr(request.user, "member_profile", None)
        own_family = own_member.family if (own_member and own_member.family_id) else None
        return Response({
            "restrictable_features": services.restrictable_features_for(request.user),
            "own_family_id": str(own_family.id) if own_family else None,
            "own_family_name": own_family.name if own_family else None,
            "users": [
                {
                    "id": str(u.id), "username": u.username, "role": u.role,
                    "community_name": u.community.name if u.community else None,
                    "disabled_features": u.disabled_features,
                }
                for u in users
            ],
        })


class SetDisabledFeaturesView(APIView):
    """PATCH {target_id, disabled_features} -> restricts what one specific manageable user can see, never grants beyond what their role already allows."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from . import services

        target_id = request.data.get("target_id")
        disabled_features = request.data.get("disabled_features")
        if not target_id or not isinstance(disabled_features, list):
            return Response({"detail": "'target_id' and a 'disabled_features' list are required."}, status=status.HTTP_400_BAD_REQUEST)
        target = get_object_or_404(User, id=target_id)
        try:
            updated = services.set_disabled_features(target=target, features=disabled_features, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"id": str(updated.id), "username": updated.username, "disabled_features": updated.disabled_features})

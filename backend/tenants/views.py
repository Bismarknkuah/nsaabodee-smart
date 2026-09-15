from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Announcement, Community, CommunityPayoutAccount, FeatureFlag, HomepageImage, PlanInterestSubmission, PlatformBillingRecord
from .serializers import (
    AddCommunityAdminSerializer,
    AddPayoutAccountSerializer,
    AnnouncementSerializer,
    ApproveAnnouncementSerializer,
    CommunityAdminSerializer,
    CommunitySerializer,
    CreateBillingRecordSerializer,
    ExtendAccessSerializer,
    FeatureFlagSerializer,
    HomepageImageSerializer,
    MarkBillingRecordPaidSerializer,
    OnboardCommunitySerializer,
    PlanInterestSubmissionSerializer,
    PlatformBillingRecordSerializer,
    PayoutAccountSerializer,
    RejectAnnouncementSerializer,
    ResetAdministratorPasswordSerializer,
    CommunityBackupRecordSerializer,
    RestoreCommunityBackupSerializer,
    RestoreCommunityBackupFromFileSerializer,
    ResubmitAnnouncementSerializer,
    SubmitAnnouncementSerializer,
    SubmitPlanInterestSerializer,
    UpdateApprovalWorkflowSerializer,
    UpdateCommunitySerializer,
    UpdateOwnBrandingSerializer,
    UploadHomepageImageSerializer,
    UploadOwnLogoSerializer,
)


class _PlatformAdminOnly(APIView):
    """
    Shared gate for every view in this file: "I think it's the super
    admin who should add, edit, or remove a community." A Community
    Admin keeps full authority over their OWN community's day-to-day
    running (families, rates, members — unchanged); creating, editing,
    deactivating, or deleting the community ITSELF is platform-level.

    `capability`, when given, is checked via
    User.has_platform_admin_capability() — 'system settings should
    restrict or give access to the platform admin based on what they
    can do.' Omitted entirely on views where the action is either not
    yet capability-gated or is available to every Platform Admin
    unconditionally.
    """
    permission_classes = [IsAuthenticated]

    def check_platform_admin(self, request, capability: str = None):
        if not services.is_platform_admin(request.user):
            return Response({"detail": "Only a platform administrator can manage communities."}, status=status.HTTP_403_FORBIDDEN)
        if capability and not request.user.has_platform_admin_capability(capability):
            return Response(
                {"detail": f"Your Platform Admin account doesn't have the '{capability}' capability. Ask another Platform Admin to grant it."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None


class CommunityListView(_PlatformAdminOnly):
    """GET -> every community on the platform. POST -> create a new one, with its first Community Admin, in one step."""

    def get(self, request):
        denied = self.check_platform_admin(request)
        if denied:
            return denied
        return Response(CommunitySerializer(services.list_communities(), many=True).data)

    def post(self, request):
        denied = self.check_platform_admin(request, capability="manage_communities")
        if denied:
            return denied
        serializer = OnboardCommunitySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        community, admin_user = serializer.save()
        return Response({
            "community": CommunitySerializer(community).data,
            "admin": CommunityAdminSerializer({"id": admin_user.id, "username": admin_user.username, "email": admin_user.email}).data,
        }, status=status.HTTP_201_CREATED)


class CommunityDetailView(_PlatformAdminOnly):
    """GET -> one community's details. PATCH -> edit name/region/default rates."""

    def get(self, request, community_id):
        denied = self.check_platform_admin(request)
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        return Response(CommunitySerializer(community).data)

    def patch(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_communities")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        serializer = UpdateCommunitySerializer(data=request.data, context={"community": community}, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(CommunitySerializer(updated).data)

    def delete(self, request, community_id):
        """Permanent deletion — only succeeds for a community with no real data in it yet. See services.delete_empty_community."""
        denied = self.check_platform_admin(request, capability="manage_communities")
        if denied:
            return denied
        from django.core.exceptions import ValidationError
        community = get_object_or_404(Community, id=community_id)
        try:
            services.delete_empty_community(community)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommunityDeactivateView(_PlatformAdminOnly):
    """POST -> the safe, reversible "remove": hides the community without touching any of its data."""

    def post(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_communities")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        return Response(CommunitySerializer(services.deactivate_community(community, actor=request.user)).data)


class CommunityReactivateView(_PlatformAdminOnly):
    def post(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_communities")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        return Response(CommunitySerializer(services.reactivate_community(community, actor=request.user)).data)


class CommunityExtendAccessView(_PlatformAdminOnly):
    """POST {additional_days} -> renews a temporary/rental community's access period."""

    def post(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_access_periods")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        serializer = ExtendAccessSerializer(data=request.data, context={"community": community, "request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(CommunitySerializer(updated).data)


class CommunityTerminateAccessView(_PlatformAdminOnly):
    """POST -> 'Extend or terminate licenses.' Cuts a temporary/rental community's access short, right now."""

    def post(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_access_periods")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        try:
            updated = services.terminate_community_access(community=community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CommunitySerializer(updated).data)


class ResetAdministratorPasswordView(APIView):
    """POST {username, new_password} -> 'Reset administrator accounts when requested.' Not community-scoped — a Platform Admin account has no community at all, and a Community Admin's own community is looked up from their own record, not a URL parameter."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ResetAdministratorPasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        admin_user = serializer.save()
        return Response({"username": admin_user.username, "detail": "Password reset successfully."})


class CommunityMakePermanentView(_PlatformAdminOnly):
    """POST -> upgrades a temporary/rental community to ongoing, permanent access."""

    def post(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_communities")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        return Response(CommunitySerializer(services.make_community_permanent(community)).data)


class SendSubscriptionReminderView(_PlatformAdminOnly):
    """POST {message?} -> notifies every Community Admin of this community that a subscription payment is due, and records when/by whom on the Community itself."""

    def post(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_access_periods")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        message = request.data.get("message", "")
        try:
            sent_count = services.send_subscription_reminder(community=community, actor=request.user, message=message)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"sent_to_admin_count": sent_count, "community": CommunitySerializer(community).data})


class CommunitiesNeedingSubscriptionAttentionView(_PlatformAdminOnly):
    """GET -> every temporary/rental community whose access has expired or expires within 14 days — the actual worklist for sending reminders."""

    def get(self, request):
        denied = self.check_platform_admin(request)
        if denied:
            return denied
        communities = services.communities_needing_subscription_attention()
        return Response(CommunitySerializer(communities, many=True).data)


class PayoutAccountsView(APIView):
    """GET -> every payout account this community has configured. POST -> add another one. Community Admin of THIS community (or a platform admin) only — checked inside the service layer, not just here."""
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        return Response(PayoutAccountSerializer(services.list_payout_accounts(community), many=True).data)

    def post(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        serializer = AddPayoutAccountSerializer(data=request.data, context={"community": community, "request": request})
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        return Response(PayoutAccountSerializer(account).data, status=status.HTTP_201_CREATED)


class DeactivatePayoutAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id, account_id):
        account = get_object_or_404(CommunityPayoutAccount, id=account_id, community_id=community_id)
        try:
            services.deactivate_payout_account(account=account, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(PayoutAccountSerializer(account).data)


class BillingRecordsView(APIView):
    """
    GET -> this community's platform billing history (platform admin,
    or that community's own Community Admin — viewing only).
    POST -> create a new billing record (platform admin only).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        try:
            records = services.list_billing_records_for_viewing(community=community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(PlatformBillingRecordSerializer(records, many=True).data)

    def post(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        serializer = CreateBillingRecordSerializer(data=request.data, context={"community": community, "request": request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(PlatformBillingRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class MarkBillingRecordPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id, record_id):
        record = get_object_or_404(PlatformBillingRecord, id=record_id, community_id=community_id)
        serializer = MarkBillingRecordPaidSerializer(data=request.data, context={"record": record, "request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(PlatformBillingRecordSerializer(updated).data)


class WaiveBillingRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id, record_id):
        record = get_object_or_404(PlatformBillingRecord, id=record_id, community_id=community_id)
        try:
            updated = services.waive_billing_record(record=record, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(PlatformBillingRecordSerializer(updated).data)


class PlatformRevenueReportView(APIView):
    """'View revenue reports' — Platform Admin only, aggregating every community's platform billing records."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get("start_date") or None
        end_date = request.query_params.get("end_date") or None
        try:
            report = services.platform_revenue_report(actor=request.user, start_date=start_date, end_date=end_date)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(report)


class FeatureFlagsView(APIView):
    """'Manage feature flags' — Platform Admin only, both viewing and toggling."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            flags = services.list_feature_flags(actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(FeatureFlagSerializer(flags, many=True).data)


class ToggleFeatureFlagView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, key):
        is_enabled = request.data.get("is_enabled")
        if not isinstance(is_enabled, bool):
            return Response({"detail": "'is_enabled' must be true or false."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            flag = services.set_feature_flag_enabled(key=key, is_enabled=is_enabled, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(FeatureFlagSerializer(flag).data)


class FeatureFlagStatusView(APIView):
    """
    A deliberately unrestricted read — every signed-in user's chatbot
    widget and messaging nav link need this to know whether to show
    themselves at all, not just a Platform Admin managing them.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        services.ensure_default_feature_flags()
        return Response({flag.key: flag.is_enabled for flag in FeatureFlag.objects.all()})


class AllCommunityAdminsView(APIView):
    """
    'They can manage the platform admins on the community admins.' The
    one-query, platform-wide view a real "User Management" page needs
    — the per-community CommunityAdminsView below still exists for the
    Communities page's own per-community expansion.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            admins = services.list_all_community_admins(actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response([
            {"id": str(a.id), "username": a.username, "email": a.email, "community_id": str(a.community_id) if a.community_id else None, "community_name": a.community.name if a.community else None}
            for a in admins
        ])


class CommunityAdminsView(_PlatformAdminOnly):
    """GET -> every Community Admin login for this community. POST -> add another one."""

    def get(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_community_admins")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        admins = services.list_community_admins(community)
        return Response(CommunityAdminSerializer(
            [{"id": a.id, "username": a.username, "email": a.email} for a in admins], many=True
        ).data)

    def post(self, request, community_id):
        denied = self.check_platform_admin(request, capability="manage_community_admins")
        if denied:
            return denied
        community = get_object_or_404(Community, id=community_id)
        serializer = AddCommunityAdminSerializer(data=request.data, context={"community": community})
        serializer.is_valid(raise_exception=True)
        admin_user = serializer.save()
        return Response(
            CommunityAdminSerializer({"id": admin_user.id, "username": admin_user.username, "email": admin_user.email}).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformAdminsView(APIView):
    """'Managing platform administrators.' GET -> every Platform Admin login, platform-wide. POST -> create another one — deliberately create_user, never a Django superuser."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            admins = services.list_platform_admins(actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommunityAdminSerializer(
            [{"id": a.id, "username": a.username, "email": a.email} for a in admins], many=True
        ).data)

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")
        email = request.data.get("email", "")
        if not username or not password:
            return Response({"detail": "A username and password are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            new_admin = services.add_platform_admin(username=username, password=password, email=email, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            CommunityAdminSerializer({"id": new_admin.id, "username": new_admin.username, "email": new_admin.email}).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformAdminCapabilitiesView(APIView):
    """
    'System settings should provide more option that will restrict or
    give access to the platform admin based on what they can do.' GET
    -> the recognized capability keys (with their descriptions) plus
    every Platform Admin's current settings, so the frontend never has
    to hardcode the list. PATCH {target_id, capabilities} -> update one
    other Platform Admin's capabilities — never your own, enforced in
    services.update_platform_admin_capabilities.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounts.models import PLATFORM_ADMIN_CAPABILITIES, Role, User

        if not (request.user.is_superuser or request.user.has_platform_admin_capability("manage_platform_admins")):
            return Response({"detail": "Only a platform administrator with the 'manage_platform_admins' capability can view this."}, status=status.HTTP_403_FORBIDDEN)

        admins = User.objects.filter(role=Role.PLATFORM_ADMIN).order_by("username")
        return Response({
            "capability_definitions": PLATFORM_ADMIN_CAPABILITIES,
            "admins": [
                {
                    "id": str(a.id), "username": a.username,
                    "is_you": a.id == request.user.id,
                    "capabilities": {key: a.has_platform_admin_capability(key) for key in PLATFORM_ADMIN_CAPABILITIES},
                }
                for a in admins
            ],
        })

    def patch(self, request):
        from accounts.models import Role, User

        target_id = request.data.get("target_id")
        capabilities = request.data.get("capabilities")
        if not target_id or not isinstance(capabilities, dict):
            return Response({"detail": "'target_id' and a 'capabilities' object are required."}, status=status.HTTP_400_BAD_REQUEST)
        target = get_object_or_404(User, id=target_id, role=Role.PLATFORM_ADMIN)
        try:
            updated = services.update_platform_admin_capabilities(target=target, capabilities=capabilities, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"id": str(updated.id), "username": updated.username, "capabilities": updated.platform_admin_capabilities})


class MyCommunityBrandingView(APIView):
    """'Configure branding (logo, colors, community information)' — self-service, Community Admin only, own community only, no Platform Admin involvement needed."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "community_admin" or request.user.community_id is None:
            return Response({"detail": "Only a Community Admin has a community's branding to configure."}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommunitySerializer(request.user.community).data)

    def patch(self, request):
        serializer = UpdateOwnBrandingSerializer(data=request.data, context={"request": request}, partial=True)
        serializer.is_valid(raise_exception=True)
        community = serializer.save()
        return Response(CommunitySerializer(community).data)


class MyCommunityLogoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UploadOwnLogoSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        community = serializer.save()
        return Response(CommunitySerializer(community).data)


class MyApprovalWorkflowView(APIView):
    """'Configure approval workflows' — self-service, Community Admin only, own community only."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UpdateApprovalWorkflowSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        community = serializer.save()
        return Response(CommunitySerializer(community).data)


class HomepageImagesPublicView(APIView):
    """The public homepage's own read — no login, matching the page itself. Only ever active images."""
    permission_classes = [AllowAny]

    def get(self, request):
        images = services.list_public_homepage_images()
        return Response(HomepageImageSerializer(images, many=True, context={"request": request}).data)


class HomepageImagesManageView(APIView):
    """Platform-admin only — 'the homepage live pictures... should be uploaded by the super admin.'"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            images = services.list_all_homepage_images(actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(HomepageImageSerializer(images, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = UploadHomepageImageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        image = serializer.save()
        return Response(HomepageImageSerializer(image, context={"request": request}).data, status=status.HTTP_201_CREATED)


class HomepageImageDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, image_id):
        homepage_image = get_object_or_404(HomepageImage, id=image_id)
        try:
            services.deactivate_homepage_image(homepage_image=homepage_image, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)


class HomepageImageReactivateView(APIView):
    """POST -> brings a previously-deactivated image back."""
    permission_classes = [IsAuthenticated]

    def post(self, request, image_id):
        homepage_image = get_object_or_404(HomepageImage, id=image_id)
        try:
            updated = services.reactivate_homepage_image(homepage_image=homepage_image, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(HomepageImageSerializer(updated, context={"request": request}).data)


class HomepageImageDetailView(APIView):
    """PATCH -> edit caption/subcaption/display_order. DELETE -> permanent removal, distinct from deactivate."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, image_id):
        homepage_image = get_object_or_404(HomepageImage, id=image_id)
        try:
            updated = services.update_homepage_image(
                homepage_image=homepage_image, actor=request.user,
                caption=request.data.get("caption"), subcaption=request.data.get("subcaption"),
                display_order=request.data.get("display_order"),
            )
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(HomepageImageSerializer(updated, context={"request": request}).data)

    def delete(self, request, image_id):
        homepage_image = get_object_or_404(HomepageImage, id=image_id)
        try:
            services.delete_homepage_image(homepage_image=homepage_image, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubmitPlanInterestView(APIView):
    """Public — registering interest in a not-yet-available plan needs no login, matching the homepage itself."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SubmitPlanInterestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Thank you — we'll be in touch once this plan is available."}, status=status.HTTP_201_CREATED)


class PlanInterestSubmissionsView(APIView):
    """Platform-admin only — the actual, actionable list of leads 'coming soon' generates."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            submissions = services.list_plan_interest_submissions(actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(PlanInterestSubmissionSerializer(submissions, many=True).data)


class MarkPlanInterestContactedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, submission_id):
        submission = get_object_or_404(PlanInterestSubmission, id=submission_id)
        try:
            services.mark_plan_interest_contacted(submission=submission, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(PlanInterestSubmissionSerializer(submission).data)


class SubmitAnnouncementView(APIView):
    """'Has to be submitted by the community admin.'"""
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        serializer = SubmitAnnouncementSerializer(data=request.data, context={"community": community, "request": request})
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save()
        return Response(AnnouncementSerializer(announcement, context={"request": request}).data, status=status.HTTP_201_CREATED)


class CommunityAnnouncementsView(APIView):
    """A Community Admin's own view of everything they've submitted for their community — pending, approved, and rejected alike."""
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        try:
            announcements = services.list_announcements_for_own_community(community=community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(AnnouncementSerializer(announcements, many=True, context={"request": request}).data)


class ResubmitAnnouncementView(APIView):
    """
    'For the community admin to edit and resend again.' Authorization
    checked explicitly here (403) before the serializer runs — a
    different community's admin trying to touch this announcement is
    a wrong-role/wrong-community failure, not a data-validation one,
    and the established convention across this platform keeps those
    two kinds of failure on different status codes. A genuine state
    error from the service itself ('already resubmitted', 'not
    rejected') still surfaces as the serializer's own 400, unchanged.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, announcement_id):
        from tenants.services import _is_own_communitys_admin

        announcement = get_object_or_404(Announcement, id=announcement_id)
        if not _is_own_communitys_admin(request.user, announcement.community):
            return Response({"detail": "Only this community's own Community Admin can resubmit this announcement."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ResubmitAnnouncementSerializer(data=request.data, context={"announcement": announcement, "request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(AnnouncementSerializer(updated, context={"request": request}).data)


class PendingAnnouncementsReviewView(APIView):
    """Platform-admin only — every community's announcements still awaiting a decision."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            announcements = services.list_pending_announcements_for_review(actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(AnnouncementSerializer(announcements, many=True, context={"request": request}).data)


class ApproveAnnouncementView(APIView):
    """'The super admin has to approve it... and the super admin can edit the content.'"""
    permission_classes = [IsAuthenticated]

    def post(self, request, announcement_id):
        from tenants.services import is_platform_admin

        announcement = get_object_or_404(Announcement, id=announcement_id)
        if not is_platform_admin(request.user):
            return Response({"detail": "Only a platform administrator can approve an announcement."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ApproveAnnouncementSerializer(data=request.data, context={"announcement": announcement, "request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(AnnouncementSerializer(updated, context={"request": request}).data)


class RejectAnnouncementView(APIView):
    """'Reject it with reasons.'"""
    permission_classes = [IsAuthenticated]

    def post(self, request, announcement_id):
        from tenants.services import is_platform_admin

        announcement = get_object_or_404(Announcement, id=announcement_id)
        if not is_platform_admin(request.user):
            return Response({"detail": "Only a platform administrator can reject an announcement."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RejectAnnouncementSerializer(data=request.data, context={"announcement": announcement, "request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(AnnouncementSerializer(updated, context={"request": request}).data)


class NoticeBoardView(APIView):
    """The actual notice board — every community's approved announcements, platform-wide. Requires being logged in (any role, any community) — internal community content, not public marketing."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        announcements = services.list_public_notice_board()
        return Response(AnnouncementSerializer(announcements, many=True, context={"request": request}).data)


class HomepageFeaturedAnnouncementsView(APIView):
    """'When it needs it on the homepage he has to send a request to the platform admin.' The one genuinely public read here — no login, matching the homepage itself. Only announcements a Platform Admin specifically granted homepage placement to, on top of ordinary approval."""
    permission_classes = [AllowAny]

    def get(self, request):
        announcements = services.list_homepage_featured_announcements()
        return Response(AnnouncementSerializer(announcements, many=True, context={"request": request}).data)


class CommunityBackupExportView(APIView):
    """
    GET -> a JSON snapshot of this community's own member/family
    roster, as a downloadable file — the Community Admin then saves
    it to their own Google Drive (or anywhere else) themselves. This
    platform never authenticates to Google Drive on anyone's behalf.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        from django.http import HttpResponse

        community = get_object_or_404(Community, id=community_id)
        try:
            data = services.export_community_backup(community=community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        import json
        payload = json.dumps(data, indent=2)
        response = HttpResponse(payload, content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{community.slug}-backup.json"'
        return response


class CommunityBackupRestoreView(APIView):
    """POST {drive_link} -> fetches and restores a previously-exported backup from a Google Drive share link."""
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        if not services._is_own_communitys_admin(request.user, community):
            return Response({"detail": "Only this community's own Community Admin can restore its data."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RestoreCommunityBackupSerializer(data=request.data, context={"community": community, "request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)


class CommunityBackupHistoryView(APIView):
    """GET -> this community's own backup/restore history."""
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        try:
            records = services.list_backup_records(community=community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommunityBackupRecordSerializer(records, many=True).data)


class MyCommunityBackupExportView(APIView):
    """GET -> same as CommunityBackupExportView, but for the acting user's own community — matching the existing /tenants/my-community/branding/ self-service convention, so the frontend never needs to know its own community's id."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.http import HttpResponse

        if request.user.community_id is None:
            return Response({"detail": "Your account isn't linked to a community."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            data = services.export_community_backup(community=request.user.community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        import json
        payload = json.dumps(data, indent=2)
        response = HttpResponse(payload, content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{request.user.community.slug}-backup.json"'
        return response


class MyCommunityBackupRestoreView(APIView):
    """POST {drive_link} -> same as CommunityBackupRestoreView, for the acting user's own community."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.community_id is None:
            return Response({"detail": "Your account isn't linked to a community."}, status=status.HTTP_400_BAD_REQUEST)
        community = request.user.community
        if not services._is_own_communitys_admin(request.user, community):
            return Response({"detail": "Only this community's own Community Admin can restore its data."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RestoreCommunityBackupSerializer(data=request.data, context={"community": community, "request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)


class MyCommunityBackupUploadRestoreView(APIView):
    """POST {file} -> 'should also be able to upload from my computer to synchronize.' Same restore, from a file already on the Community Admin's own device rather than a Drive link."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.community_id is None:
            return Response({"detail": "Your account isn't linked to a community."}, status=status.HTTP_400_BAD_REQUEST)
        community = request.user.community
        if not services._is_own_communitys_admin(request.user, community):
            return Response({"detail": "Only this community's own Community Admin can restore its data."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RestoreCommunityBackupFromFileSerializer(data=request.data, context={"community": community, "request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)


class MyCommunityBackupHistoryView(APIView):
    """GET -> same as CommunityBackupHistoryView, for the acting user's own community."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.community_id is None:
            return Response([])
        try:
            records = services.list_backup_records(community=request.user.community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommunityBackupRecordSerializer(records, many=True).data)

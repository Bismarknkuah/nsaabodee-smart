from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from families.models import Family
from members.models import Member
from . import services
from .models import ContributionCampaign, ContributionCategory, WelfareObligation, WelfareRequest
from .serializers import (
    ContributionCampaignSerializer,
    ContributionCategorySerializer,
    CreateContributionCategorySerializer,
    DecideFamilyCampaignSerializer,
    DecideWelfareRequestSerializer,
    DisburseWelfareRequestSerializer,
    InitiateCommunityCampaignSerializer,
    InitiateFamilyCampaignSerializer,
    RecordVoluntaryContributionSerializer,
    RecordWelfarePaymentSerializer,
    SetCampaignTargetMembersSerializer,
    SubmitWelfareRequestSerializer,
    WelfareObligationSerializer,
    WelfareRequestSerializer,
)


class ContributionCategoryListCreateView(APIView):
    """GET -> every active category in this community. POST -> create one (Community Admin only, enforced in the service)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categories = ContributionCategory.objects.filter(community=request.user.community, is_active=True)
        return Response(ContributionCategorySerializer(categories, many=True).data)

    def post(self, request):
        serializer = CreateContributionCategorySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            category = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(ContributionCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class CommunityWideCampaignInitiateView(APIView):
    """'When the community creates it, it affects all the community.'"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiateCommunityCampaignSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            campaign = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(ContributionCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)


class FamilyCampaignInitiateView(APIView):
    """'Any family can also use it for welfare... it should only be within his jurisdiction.'"""
    permission_classes = [IsAuthenticated]

    def post(self, request, family_id):
        qs = Family.objects.all() if request.user.is_superuser else Family.objects.filter(community=request.user.community)
        family = get_object_or_404(qs, id=family_id)
        serializer = InitiateFamilyCampaignSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        try:
            campaign = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(ContributionCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)


class DecideFamilyCampaignView(APIView):
    """'It needs the approval of two other family executives before his family members get billed.'"""
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)
        serializer = DecideFamilyCampaignSerializer(data=request.data, context={"request": request, "campaign": campaign})
        serializer.is_valid(raise_exception=True)
        try:
            updated = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(ContributionCampaignSerializer(updated).data)


class PendingCommunityAdminWelfareApprovalsView(APIView):
    """
    'Each family head should have the welfare contribution features
    which has to be approved by the community admin before it works
    for his community members.' The Community (or Temporary) Admin's
    own final-approval queue.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_superuser or request.user.role == "community_admin"):
            return Response({"detail": "Only a Community Administrator has a welfare-campaign final-approval queue."}, status=403)
        pending = services.list_pending_community_admin_welfare_approvals(request.user.community)
        return Response(ContributionCampaignSerializer(pending, many=True).data)


class ApproveFamilyCampaignByCommunityAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)
        approve = request.data.get("approve", True)
        try:
            updated = services.approve_family_campaign_by_community_admin(campaign=campaign, actor=request.user, approve=approve)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(ContributionCampaignSerializer(updated).data)


class CampaignListView(APIView):
    """
    GET -> every community-wide campaign, plus (if the user has a
    linked member) their own family's campaigns. Never another
    family's campaign — matching the same jurisdiction boundary the
    obligations themselves respect.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        own_member = getattr(request.user, "member_profile", None)
        qs = ContributionCampaign.objects.filter(community=request.user.community)
        if request.user.is_superuser or request.user.role in {"community_admin", "chairman", "secretary"}:
            pass  # community-wide leadership sees every campaign, family-scoped or not
        elif own_member is not None:
            qs = qs.filter(Q(family__isnull=True) | Q(family_id=own_member.family_id))
        else:
            qs = qs.filter(family__isnull=True)
        return Response(ContributionCampaignSerializer(qs.order_by("-created_at"), many=True).data)


class CampaignObligationsView(APIView):
    """
    GET -> every member's obligation under one campaign — but only for
    community-wide leadership, or the owning family's own executives
    when the campaign is family-scoped. 'Family A members may access
    authorized Family A... they must not automatically access Family
    B financial information... unless their official role explicitly
    grants such access.' An ordinary member who isn't one of those
    still sees their OWN obligation (they need to know what they owe),
    never anyone else's.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)
        obligations = WelfareObligation.objects.filter(campaign=campaign).select_related("member")

        own_member = getattr(request.user, "member_profile", None)
        is_community_wide_leadership = request.user.is_superuser or request.user.role in {"community_admin", "chairman", "secretary"}
        is_owning_familys_executive = bool(
            campaign.family_id and own_member and own_member.family_id == campaign.family_id
            and request.user.role in {"family_head", "family_secretary", "family_treasurer"}
        )
        if not (is_community_wide_leadership or is_owning_familys_executive):
            obligations = obligations.filter(member=own_member) if own_member else obligations.none()

        return Response(WelfareObligationSerializer(obligations, many=True).data)


class RecordWelfarePaymentView(APIView):
    """
    'Only authorized Family A officials should be able to process the
    request' — extended to recording a payment itself: community-wide
    financial leadership for any campaign, the owning family's own
    executives for their own family-scoped campaign, or a member
    paying their own obligation. Previously had NO authorization check
    beyond same-community — any authenticated account could record a
    payment against any other family's obligation.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, obligation_id):
        qs = WelfareObligation.objects.all() if request.user.is_superuser else WelfareObligation.objects.filter(community=request.user.community)
        obligation = get_object_or_404(qs, id=obligation_id)
        campaign = obligation.campaign

        own_member = getattr(request.user, "member_profile", None)
        is_own_obligation = bool(own_member and own_member.id == obligation.member_id)
        is_community_wide_leadership = request.user.is_superuser or request.user.role in {"community_admin", "chairman", "secretary", "treasurer", "financial_secretary"}
        is_owning_familys_executive = bool(
            campaign.family_id and own_member and own_member.family_id == campaign.family_id
            and request.user.role in {"family_head", "family_secretary", "family_treasurer"}
        )
        if not (is_own_obligation or is_community_wide_leadership or is_owning_familys_executive):
            return Response({"detail": "You're not authorized to record a payment against this obligation."}, status=status.HTTP_403_FORBIDDEN)

        serializer = RecordWelfarePaymentSerializer(data=request.data, context={"request": request, "obligation": obligation})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        obligation.refresh_from_db()
        return Response(WelfareObligationSerializer(obligation).data, status=status.HTTP_201_CREATED)


class RecordVoluntaryContributionView(APIView):
    """
    'A voluntary campaign must NOT create a debt-like outstanding
    balance.' A member contributing to their own voluntary campaign,
    or community-wide/owning-family leadership recording a
    contribution on someone's behalf (e.g. cash handed over at a
    desk) — same authorization shape as RecordWelfarePaymentView.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)

        member_id = request.data.get("member_id")
        own_member = getattr(request.user, "member_profile", None)
        if member_id:
            member = get_object_or_404(Member, id=member_id, community=request.user.community)
        elif own_member is not None:
            member = own_member
        else:
            return Response({"detail": "No member to record this contribution for — provide 'member_id'."}, status=status.HTTP_400_BAD_REQUEST)

        is_own_contribution = bool(own_member and own_member.id == member.id)
        is_community_wide_leadership = request.user.is_superuser or request.user.role in {"community_admin", "chairman", "secretary", "treasurer", "financial_secretary"}
        is_owning_familys_executive = bool(
            campaign.family_id and own_member and own_member.family_id == campaign.family_id
            and request.user.role in {"family_head", "family_secretary", "family_treasurer"}
        )
        if not (is_own_contribution or is_community_wide_leadership or is_owning_familys_executive):
            return Response({"detail": "You're not authorized to record a contribution on this member's behalf."}, status=status.HTTP_403_FORBIDDEN)

        serializer = RecordVoluntaryContributionSerializer(data=request.data, context={"request": request, "campaign": campaign, "member": member})
        serializer.is_valid(raise_exception=True)
        try:
            payment = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        payment.obligation.refresh_from_db()
        return Response(WelfareObligationSerializer(payment.obligation).data, status=status.HTTP_201_CREATED)


class SubmitWelfareRequestView(APIView):
    """POST -> a member requesting support from a fund. member_id lets an executive submit on someone's behalf; otherwise the actor's own member record is used."""
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)

        member_id = request.data.get("member_id")
        own_member = getattr(request.user, "member_profile", None)
        if member_id:
            requester = get_object_or_404(Member, id=member_id, community=request.user.community)
        elif own_member is not None:
            requester = own_member
        else:
            return Response({"detail": "No member to submit this request for — provide 'member_id'."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SubmitWelfareRequestSerializer(data=request.data, context={"request": request, "campaign": campaign, "requester": requester})
        serializer.is_valid(raise_exception=True)
        try:
            welfare_request = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WelfareRequestSerializer(welfare_request).data, status=status.HTTP_201_CREATED)


class ListWelfareRequestsView(APIView):
    """GET -> every request an authorized fund administrator can see, or just the actor's own otherwise — see services.list_welfare_requests_for."""
    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)
        results = services.list_welfare_requests_for(campaign=campaign, actor=request.user)
        return Response(WelfareRequestSerializer(results.order_by("-created_at"), many=True).data)


class DecideWelfareRequestView(APIView):
    """POST {approve, amount_approved?, rejection_reason?} — authorization checked explicitly here (403) before calling the service, so a genuine state error ('already decided') still surfaces as 400 rather than being swallowed into the same 403."""
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        qs = WelfareRequest.objects.all() if request.user.is_superuser else WelfareRequest.objects.filter(community=request.user.community)
        welfare_request = get_object_or_404(qs, id=request_id)
        if not services._is_authorized_for_campaign_administration(request.user, welfare_request.campaign):
            return Response({"detail": f"'{request.user.username}' isn't authorized to decide this fund's welfare requests."}, status=status.HTTP_403_FORBIDDEN)
        input_serializer = DecideWelfareRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            updated = services.decide_welfare_request(request=welfare_request, actor=request.user, **input_serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WelfareRequestSerializer(updated).data)


class DisburseWelfareRequestView(APIView):
    """POST {amount?} — same authorization-before-service pattern as DecideWelfareRequestView, for the same reason."""
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        qs = WelfareRequest.objects.all() if request.user.is_superuser else WelfareRequest.objects.filter(community=request.user.community)
        welfare_request = get_object_or_404(qs, id=request_id)
        if not services._is_authorized_for_campaign_administration(request.user, welfare_request.campaign):
            return Response({"detail": f"'{request.user.username}' isn't authorized to disburse this fund's welfare requests."}, status=status.HTTP_403_FORBIDDEN)
        input_serializer = DisburseWelfareRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            updated = services.disburse_welfare_request(request=welfare_request, actor=request.user, **input_serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WelfareRequestSerializer(updated).data)


class AcknowledgeWelfareDisbursementView(APIView):
    """POST -> the requester confirming they actually received the money."""
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        qs = WelfareRequest.objects.all() if request.user.is_superuser else WelfareRequest.objects.filter(community=request.user.community)
        welfare_request = get_object_or_404(qs, id=request_id)
        try:
            updated = services.acknowledge_welfare_disbursement(request=welfare_request, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(WelfareRequestSerializer(updated).data)


class SetCampaignTargetMembersView(APIView):
    """POST {member_ids} — 'the campaign may apply only to... specific contributors.' Authorization checked explicitly (403) before calling the service, so 'already has obligations' still surfaces as 400."""
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)
        if not services._is_authorized_for_campaign_administration(request.user, campaign):
            return Response({"detail": f"'{request.user.username}' isn't authorized to set this campaign's targeted members."}, status=status.HTTP_403_FORBIDDEN)
        serializer = SetCampaignTargetMembersSerializer(data=request.data, context={"request": request, "campaign": campaign})
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

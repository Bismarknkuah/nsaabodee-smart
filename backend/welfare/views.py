from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from families.models import Family
from . import services
from .models import ContributionCampaign, ContributionCategory, WelfareObligation
from .serializers import (
    ContributionCampaignSerializer,
    ContributionCategorySerializer,
    CreateContributionCategorySerializer,
    DecideFamilyCampaignSerializer,
    InitiateCommunityCampaignSerializer,
    InitiateFamilyCampaignSerializer,
    RecordWelfarePaymentSerializer,
    WelfareObligationSerializer,
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
    """GET -> every member's obligation under one campaign."""
    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        qs = ContributionCampaign.objects.all() if request.user.is_superuser else ContributionCampaign.objects.filter(community=request.user.community)
        campaign = get_object_or_404(qs, id=campaign_id)
        obligations = WelfareObligation.objects.filter(campaign=campaign).select_related("member")
        return Response(WelfareObligationSerializer(obligations, many=True).data)


class RecordWelfarePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, obligation_id):
        qs = WelfareObligation.objects.all() if request.user.is_superuser else WelfareObligation.objects.filter(community=request.user.community)
        obligation = get_object_or_404(qs, id=obligation_id)
        serializer = RecordWelfarePaymentSerializer(data=request.data, context={"request": request, "obligation": obligation})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        obligation.refresh_from_db()
        return Response(WelfareObligationSerializer(obligation).data, status=status.HTTP_201_CREATED)

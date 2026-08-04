from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .permissions import CanManageContributionRules
from .serializers import (
    PreviewObligationsSerializer,
    SetStatusExemptionSerializer,
    UpdateDefaulterThresholdsSerializer,
    UpdateFamilyTierRatesSerializer,
    UpdateGeneralRatesSerializer,
)


class ContributionRulesView(APIView):
    """
    GET  /api/contribution-rules/   — the single-view dashboard: general
                                       rates, every family's own rate,
                                       member-status exemptions, defaulter
                                       thresholds, all in one response.
    """
    permission_classes = [IsAuthenticated, CanManageContributionRules]

    def get(self, request):
        return Response(services.list_rules(request.user.community))


class GeneralRatesView(APIView):
    permission_classes = [IsAuthenticated, CanManageContributionRules]

    def post(self, request):
        serializer = UpdateGeneralRatesSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class FamilyTierRatesView(APIView):
    """'Adjust or increase the minimum amount paid' for the tiered family rates (head/uncle/nephew/woman) and the town-leader rate."""
    permission_classes = [IsAuthenticated, CanManageContributionRules]

    def post(self, request):
        serializer = UpdateFamilyTierRatesSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class StatusExemptionView(APIView):
    permission_classes = [IsAuthenticated, CanManageContributionRules]

    def post(self, request):
        serializer = SetStatusExemptionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class DefaulterThresholdsView(APIView):
    permission_classes = [IsAuthenticated, CanManageContributionRules]

    def post(self, request):
        serializer = UpdateDefaulterThresholdsSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class PreviewObligationsView(APIView):
    permission_classes = [IsAuthenticated, CanManageContributionRules]

    def post(self, request):
        serializer = PreviewObligationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.to_preview(request.user.community))

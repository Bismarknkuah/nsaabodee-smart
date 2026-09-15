from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .permissions import CanManageContributionRules
from .serializers import (
    PreviewObligationsSerializer,
    SetFamilyPositionRateSerializer,
    SetStatusExemptionSerializer,
    UpdateDefaulterThresholdsSerializer,
    UpdateFamilyTierRatesSerializer,
    UpdateGeneralRatesSerializer,
    UpdateTownElderPerTitleRatesSerializer,
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


class TownElderRateView(APIView):
    """
    'It is being managed by the king and he set price for each for
    them, so the town leader/king is the head of the community's
    elders ledger.' Deliberately IsAuthenticated only, not
    CanManageContributionRules — that permission is Community
    Admin/Chairman/Secretary's shared authority over the ordinary
    family-tier rates; the Town Elders' own rate is the Traditional
    Leader's (the chief's) separate call, enforced inside
    services.set_town_elder_rate itself.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from decimal import Decimal, InvalidOperation
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            amount = Decimal(str(request.data.get("amount", "")))
        except InvalidOperation:
            return Response({"detail": "'amount' must be a number."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            community = services.set_town_elder_rate(community=request.user.community, amount=amount, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"default_town_leader_amount": str(community.default_town_leader_amount)})


class TownElderPerTitleRatesView(APIView):
    """
    POST {chief_amount?, queen_mother_amount?, linguist_amount?,
    other_amount?} — same Traditional-Leader-only authority as
    TownElderRateView above (enforced inside
    services.set_town_elder_per_title_rates itself), deliberately
    IsAuthenticated only rather than CanManageContributionRules for
    the same reason that view already is. The authorization failure
    is caught here directly (403), not delegated to the serializer's
    own exception handling (which DRF always turns into a 400) —
    matching TownElderRateView's own established convention for this
    exact kind of "wrong role, not bad input" error.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError

        input_serializer = UpdateTownElderPerTitleRatesSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            community = services.set_town_elder_per_title_rates(
                community=request.user.community,
                chief_amount=input_serializer.validated_data.get("chief_amount"),
                queen_mother_amount=input_serializer.validated_data.get("queen_mother_amount"),
                linguist_amount=input_serializer.validated_data.get("linguist_amount"),
                other_amount=input_serializer.validated_data.get("other_amount"),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            "default_town_leader_amount": str(community.default_town_leader_amount),
            "default_town_elder_chief_amount": str(community.default_town_elder_chief_amount) if community.default_town_elder_chief_amount is not None else None,
            "default_town_elder_queen_mother_amount": str(community.default_town_elder_queen_mother_amount) if community.default_town_elder_queen_mother_amount is not None else None,
            "default_town_elder_linguist_amount": str(community.default_town_elder_linguist_amount) if community.default_town_elder_linguist_amount is not None else None,
            "default_town_elder_other_amount": str(community.default_town_elder_other_amount) if community.default_town_elder_other_amount is not None else None,
        })


class FamilyPositionRatesView(APIView):
    """
    GET  -> every FamilyPosition rate this community has configured.
    POST {position, amount} -> set (or update) one position's rate —
    same Community Admin/Chairman/Secretary authority as the ordinary
    family-tier rates (FamilyTierRatesView above), since this is the
    same kind of "the deceased's own family's contribution rules"
    governance, just at a finer granularity.
    """
    permission_classes = [IsAuthenticated, CanManageContributionRules]

    def get(self, request):
        from .models import FamilyPositionRate
        rates = FamilyPositionRate.objects.filter(community=request.user.community)
        return Response({r.position: str(r.amount) for r in rates})

    def post(self, request):
        serializer = SetFamilyPositionRateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class MembersNeedingAgeReviewView(APIView):
    """
    'Once the community member gets to 20 years the system should
    fetch them out for each family executive to update their data.'
    Same authority as viewing the member roster itself — every
    community-tier and family-tier executive role already sees every
    member, so this report needs no separate permission of its own.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        members = services.members_needing_age_review(request.user.community)
        return Response([
            {
                "id": str(m.id), "full_name": m.full_name, "date_of_birth": m.date_of_birth.isoformat(),
                "occupation_status": m.occupation_status, "family_id": str(m.family_id) if m.family_id else None,
                "family_name": m.family.name if m.family_id else None,
            }
            for m in members.select_related("family")
        ])


class MembersMissingBirthDateView(APIView):
    """'Registration requires a lot of information' — every active member the age-eligibility rule can't evaluate yet because no birth date was ever recorded."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        members = services.members_missing_birth_date(request.user.community)
        return Response([
            {"id": str(m.id), "full_name": m.full_name, "family_id": str(m.family_id) if m.family_id else None, "family_name": m.family.name if m.family_id else None}
            for m in members.select_related("family")
        ])

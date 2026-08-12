from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import SuspiciousTransactionFlag
from .serializers import AskChatbotSerializer, ChatbotMessageSerializer, MeetingSummarySerializer, SuspiciousTransactionFlagSerializer


class PredictCollectionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        from funerals.models import FuneralEvent
        from django.shortcuts import get_object_or_404
        qs = FuneralEvent.objects.filter(community=request.user.community)
        funeral = get_object_or_404(qs, id=funeral_id)
        return Response(services.predict_expected_collections(funeral))


class DraftTributeView(APIView):
    """'Add AI features to make it greater' — drafts a starting-point tribute for the memorial page; never saves it automatically."""
    permission_classes = [IsAuthenticated]

    def post(self, request, funeral_id):
        from django.shortcuts import get_object_or_404
        from funerals.models import FuneralEvent
        from funerals.services import _can_manage_memorial_page_for

        qs = FuneralEvent.objects.all() if request.user.is_superuser else FuneralEvent.objects.filter(community=request.user.community)
        funeral = get_object_or_404(qs, id=funeral_id)
        if not _can_manage_memorial_page_for(request.user, funeral):
            return Response(
                {"detail": "Only this family's own head or secretary, or the community's Chairman/Secretary/Admin, can draft this funeral's tribute."},
                status=status.HTTP_403_FORBIDDEN,
            )

        key_details = request.data.get("key_details", "")
        try:
            draft = services.draft_tribute_message(funeral=funeral, key_details=key_details, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"draft": draft})


class InactiveMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("inactive_days", 180))
        return Response(services.find_inactive_members(community=request.user.community, inactive_days=days))


class FuzzySearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "")
        return Response(services.fuzzy_search(community=request.user.community, query=query))


class MeetingSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MeetingSummarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            summary = services.summarize_meeting(
                community=request.user.community,
                transcript=serializer.validated_data["transcript"],
                actor=request.user,
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(MeetingSummarySerializer(summary).data, status=status.HTTP_201_CREATED)


class SuspiciousTransactionFlagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SuspiciousTransactionFlagSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SuspiciousTransactionFlag.objects.filter(community=self.request.user.community)

    def partial_update(self, request, *args, **kwargs):
        flag = self.get_object()
        review_status = request.data.get("review_status")
        if review_status in (SuspiciousTransactionFlag.ReviewStatus.CONFIRMED, SuspiciousTransactionFlag.ReviewStatus.DISMISSED):
            flag.review_status = review_status
            flag.save(update_fields=["review_status"])
        return Response(SuspiciousTransactionFlagSerializer(flag).data)


class ChatbotHistoryView(APIView):
    """'Add chatbot to all user types.' Every role reaches this the same way — a person's own conversation history, nobody else's."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        history = services.list_chatbot_history(user=request.user)
        return Response(ChatbotMessageSerializer(history, many=True).data)


class AskChatbotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from tenants.services import is_feature_enabled
        if not is_feature_enabled("chatbot"):
            return Response({"detail": "The chatbot has been temporarily disabled by a platform administrator."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        serializer = AskChatbotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reply = services.ask_chatbot(user=request.user, message=serializer.validated_data["message"])
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(ChatbotMessageSerializer(reply).data, status=status.HTTP_201_CREATED)

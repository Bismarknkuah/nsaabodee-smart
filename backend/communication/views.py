from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.core.exceptions import ValidationError as DjangoValidationError

from accounts.models import Role
from . import services
from .models import CommunityMeeting, DeliveryAttempt
from .serializers import CommunityMeetingSerializer, DeliveryAttemptSerializer


class DeliveryAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/delivery-attempts/?notification={id} — the audit trail for
    a notification: which channels were tried, for whom, and whether
    each one actually sent, was skipped (no address / not configured),
    or failed. Community Admin+ only — this can reveal contact
    addresses, which is exactly the kind of thing that shouldn't be
    broadly visible.
    """
    serializer_class = DeliveryAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not (user.is_superuser or user.can_manage_families()):
            return DeliveryAttempt.objects.none()
        qs = DeliveryAttempt.objects.filter(notification__community=user.community) if not user.is_superuser else DeliveryAttempt.objects.all()
        notification_id = self.request.query_params.get("notification")
        if notification_id:
            qs = qs.filter(notification_id=notification_id)
        return qs


class MeetingViewSet(viewsets.ModelViewSet):
    """
    'View meeting schedules.' GET is open to everyone in the community
    (matching how announcements work) — the Traditional Leader's own
    oversight dashboard reads straight from this same data. Create/
    cancel is restricted to community leadership at the service layer.
    """
    serializer_class = CommunityMeetingSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return CommunityMeeting.objects.all()
        if user.community_id is None:
            return CommunityMeeting.objects.none()
        return CommunityMeeting.objects.filter(community=user.community, is_cancelled=False)

    def create(self, request, *args, **kwargs):
        serializer = CommunityMeetingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            meeting = services.schedule_meeting(community=request.user.community, actor=request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommunityMeetingSerializer(meeting).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        meeting = self.get_object()
        try:
            updated = services.cancel_meeting(meeting=meeting, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(CommunityMeetingSerializer(updated).data)

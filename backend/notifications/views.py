from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/notifications/?role=treasurer  — notifications scoped to the
    requesting user's own role within their community (a Treasurer sees
    Treasurer-scoped notices; a Family Head sees Family-Head-scoped ones).
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        qs = Notification.objects.filter(community=user.community)
        return qs.filter(recipient_role=user.role) | qs.filter(recipient_user=user)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, id=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

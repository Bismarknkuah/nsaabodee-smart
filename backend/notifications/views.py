from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/notifications/?role=treasurer — notifications scoped to the
    requesting user's own role within their community (a Treasurer sees
    Treasurer-scoped notices; a Family Head sees Family-Head-scoped ones).

    'Community members should have option where they can set or sort
    the notifications.' Three independent, optional query parameters,
    combinable:
      ?category=notice_board_post   — only this one category (see
                                       Notification.Category for the
                                       full set: defaulter_escalation,
                                       old_debt, birthday,
                                       welfare_campaign_launched,
                                       subscription_reminder,
                                       notice_board_post, etc.)
      ?is_read=true|false            — only read, or only unread
      ?ordering=oldest|newest         — oldest-first, or the default
                                       (newest-first, matching the
                                       model's own Meta.ordering)
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        qs = Notification.objects.filter(community=user.community)
        qs = qs.filter(recipient_role=user.role) | qs.filter(recipient_user=user)

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() in ("true", "1", "yes"))

        ordering = self.request.query_params.get("ordering")
        if ordering == "oldest":
            qs = qs.order_by("created_at")
        # else: leave the model's own Meta.ordering (-created_at, newest first) in place.

        return qs

    @action(detail=True, methods=["post"])
    def mark_read(self, request, id=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

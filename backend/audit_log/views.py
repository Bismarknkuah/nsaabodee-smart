from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import AuditLogEntrySerializer


class AuditLogView(APIView):
    """
    'View audit logs' — Platform Admin sees the whole platform
    (optionally filtered to one community via ?community_id=); a
    Community Admin sees only their own community's entries. Nobody
    else can reach this at all — enforced in services.list_audit_log,
    not just here.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from tenants.models import Community

        community = None
        community_id = request.query_params.get("community_id")
        if community_id:
            community = get_object_or_404(Community, id=community_id)
        category = request.query_params.get("category") or None

        try:
            entries = services.list_audit_log(actor=request.user, community=community, category=category)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(AuditLogEntrySerializer(entries, many=True).data)

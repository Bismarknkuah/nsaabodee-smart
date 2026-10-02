from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class DashboardView(APIView):
    """GET /api/dashboard/ — one endpoint, role-appropriate content. See dashboard/services.py for the per-role mapping."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.build_dashboard(request.user))

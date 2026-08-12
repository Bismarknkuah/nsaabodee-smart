from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import BereavedRepAssignment, Family, FamilyAuditLog, FamilyOfficerPosition
from .permissions import CanAssignFamilyOfficer, CanManageFamilies, CanRecommendFamilyRate, CanTransferMembers, IsSameCommunity
from .serializers import (
    ApproveFamilyRateSerializer,
    AppointFamilyOfficerPositionSerializer,
    AssignFamilyHeadSerializer,
    AssignFamilyOfficerSerializer,
    FamilyAuditLogSerializer,
    FamilyCreateSerializer,
    FamilyDeleteSerializer,
    FamilyMergeSerializer,
    FamilyOfficerPositionSerializer,
    FamilyRenameSerializer,
    FamilySerializer,
    RecommendFamilyRateSerializer,
    RegisterFamilyWithHeadSerializer,
    RejectFamilyRateSerializer,
    TransferMembersSerializer,
)


class FamilyViewSet(viewsets.ModelViewSet):
    """
    /api/families/                       GET  list   (all roles, own community)
    /api/families/                       POST create (Community Admin+)
    /api/families/{id}/                  GET  retrieve
    /api/families/{id}/rename/           POST rename
    /api/families/{id}/merge/            POST merge another family into this one's target
    /api/families/{id}/deactivate/       POST deactivate
    /api/families/{id}/reactivate/       POST reactivate
    /api/families/{id}/                  DELETE soft-delete
    /api/families/{id}/transfer_members/ POST transfer members into this family
    /api/families/{id}/assign_head/      POST assign family head
    /api/families/{id}/audit_logs/       GET  history for this family
    """

    serializer_class = FamilySerializer
    permission_classes = [IsAuthenticated, CanManageFamilies, IsSameCommunity]
    lookup_field = "id"

    def get_queryset(self):
        # HARD tenant boundary: every query is filtered by the requester's
        # community. This line is what makes "no community can access
        # another community's data" true at the database-query level.
        user = self.request.user
        qs = Family.objects.select_related("family_head", "community")
        if user.is_superuser:
            return qs
        qs = qs.filter(community=user.community)
        if self.request.query_params.get("include_inactive") != "true":
            qs = qs.exclude(status=Family.Status.DELETED)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = FamilyCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        family = serializer.save()
        return Response(FamilySerializer(family).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="register-with-head")
    def register_with_head(self, request):
        """'The system must require the registration of the Family Head as part of the process.' The recommended way to create a family from now on — POST here instead of the plain create() above."""
        serializer = RegisterFamilyWithHeadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                "family": FamilySerializer(result["family"]).data,
                "head_member_id": str(result["head_member"].id),
                "head_username": result["head_user"].username,
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        family = self.get_object()
        serializer = FamilyDeleteSerializer(
            data=request.data or {}, context={"request": request, "family": family}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def rename(self, request, id=None):
        family = self.get_object()
        serializer = FamilyRenameSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(FamilySerializer(updated).data)

    @action(detail=True, methods=["post"])
    def merge(self, request, id=None):
        source = self.get_object()
        serializer = FamilyMergeSerializer(data=request.data, context={"request": request, "family": source})
        serializer.is_valid(raise_exception=True)
        target = serializer.save()
        return Response(FamilySerializer(target).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, id=None):
        from . import services
        family = self.get_object()
        try:
            services.deactivate_family(family=family, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FamilySerializer(family).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, id=None):
        from . import services
        family = self.get_object()
        try:
            services.reactivate_family(family=family, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FamilySerializer(family).data)

    @action(detail=True, methods=["post"], url_path="transfer-members",
            permission_classes=[IsAuthenticated, CanTransferMembers, IsSameCommunity])
    def transfer_members(self, request, id=None):
        family = self.get_object()
        serializer = TransferMembersSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FamilySerializer(family).data)

    @action(detail=True, methods=["post"], url_path="assign-head")
    def assign_head(self, request, id=None):
        family = self.get_object()
        serializer = AssignFamilyHeadSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(FamilySerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="assign-officer",
            permission_classes=[IsAuthenticated, CanAssignFamilyOfficer, IsSameCommunity])
    def assign_officer(self, request, id=None):
        family = self.get_object()
        serializer = AssignFamilyOfficerSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(FamilySerializer(updated).data)

    @action(detail=True, methods=["get", "post"], url_path="officer-positions",
            permission_classes=[IsAuthenticated, IsSameCommunity])
    def officer_positions(self, request, id=None):
        """GET -> every executive position this family has recorded, visible to the whole community. POST -> appoint one (the family's own Head, or Community Admin+, only — see CanAssignFamilyOfficer)."""
        from . import services
        family = self.get_object()
        if request.method == "GET":
            positions = services.list_family_officer_positions(family=family)
            return Response(FamilyOfficerPositionSerializer(positions, many=True).data)

        if not CanAssignFamilyOfficer().has_object_permission(request, self, family):
            return Response({"detail": "Only the family's own head, or a Community Admin, can appoint an executive position."}, status=status.HTTP_403_FORBIDDEN)
        serializer = AppointFamilyOfficerPositionSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        position = serializer.save()
        return Response(FamilyOfficerPositionSerializer(position).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"officer-positions/(?P<position_id>[^/.]+)",
            permission_classes=[IsAuthenticated, IsSameCommunity])
    def remove_officer_position(self, request, id=None, position_id=None):
        from . import services
        family = self.get_object()
        if not CanAssignFamilyOfficer().has_object_permission(request, self, family):
            return Response({"detail": "Only the family's own head, or a Community Admin, can remove an executive position."}, status=status.HTTP_403_FORBIDDEN)
        position = get_object_or_404(FamilyOfficerPosition, id=position_id, family=family)
        services.remove_family_officer_position(position=position, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="audit-logs")
    def audit_logs(self, request, id=None):
        family = self.get_object()
        logs = family.audit_logs.all()
        from nsaabodeeq.pagination import paginate_response
        return paginate_response(request, logs, FamilyAuditLogSerializer)

    @action(detail=True, methods=["post"], url_path="recommend-rate",
            permission_classes=[IsAuthenticated, CanRecommendFamilyRate, IsSameCommunity])
    def recommend_rate(self, request, id=None):
        family = self.get_object()
        serializer = RecommendFamilyRateSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(FamilySerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="approve-rate")
    def approve_rate(self, request, id=None):
        family = self.get_object()
        serializer = ApproveFamilyRateSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(FamilySerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="reject-rate")
    def reject_rate(self, request, id=None):
        family = self.get_object()
        serializer = RejectFamilyRateSerializer(data=request.data, context={"request": request, "family": family})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(FamilySerializer(updated).data)


class CreateBereavedRepView(APIView):
    """'That account should be created by the community admin, secretary or chair but when one create she need other one to approved.'"""
    permission_classes = [IsAuthenticated]

    def post(self, request, family_id):
        qs = Family.objects.all() if request.user.is_superuser else Family.objects.filter(community=request.user.community)
        family = get_object_or_404(qs, id=family_id)
        member = None
        if request.data.get("member_id"):
            from members.models import Member
            member = get_object_or_404(Member.objects.filter(community=family.community), id=request.data["member_id"])
        try:
            assignment = services.create_bereaved_rep(
                family=family, actor=request.user, member=member,
                new_username=request.data.get("new_username"), new_password=request.data.get("new_password"),
                new_email=request.data.get("new_email", ""),
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_bereaved_rep_payload(assignment), status=status.HTTP_201_CREATED)


class PendingBereavedRepAssignmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_superuser or request.user.role in ("community_admin", "secretary", "chairman")):
            return Response({"detail": "Only the Community Admin, Secretary, or Chairman has a Bereaved Rep approval queue."}, status=403)
        pending = services.list_pending_bereaved_rep_assignments(request.user.community)
        return Response([_bereaved_rep_payload(a) for a in pending])


class ApproveBereavedRepView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        qs = BereavedRepAssignment.objects.all() if request.user.is_superuser else BereavedRepAssignment.objects.filter(family__community=request.user.community)
        assignment = get_object_or_404(qs, id=assignment_id)
        try:
            updated = services.approve_bereaved_rep(assignment=assignment, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_bereaved_rep_payload(updated))


class DeactivateBereavedRepView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        qs = BereavedRepAssignment.objects.all() if request.user.is_superuser else BereavedRepAssignment.objects.filter(family__community=request.user.community)
        assignment = get_object_or_404(qs, id=assignment_id)
        try:
            updated = services.deactivate_bereaved_rep(assignment=assignment, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_bereaved_rep_payload(updated))


def _bereaved_rep_payload(assignment) -> dict:
    return {
        "id": str(assignment.id), "family_id": str(assignment.family_id), "family_name": assignment.family.name,
        "member_name": assignment.member.full_name, "username": assignment.user.username,
        "is_active": assignment.is_active, "created_by_username": assignment.created_by.username if assignment.created_by_id else None,
        "approved_by_username": assignment.approved_by.username if assignment.approved_by_id else None,
        "deactivated_at": assignment.deactivated_at.isoformat() if assignment.deactivated_at else None,
    }

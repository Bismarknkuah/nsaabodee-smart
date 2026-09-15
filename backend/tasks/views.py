from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequiresExecutiveContextForTaskCreation
from . import services
from .models import MemberTask
from .permissions import CanAssignTasks
from .serializers import AssignTaskSerializer, DecideTaskCompletionSerializer, MemberTaskSerializer, ReassignTaskSerializer


class MemberTaskViewSet(viewsets.ModelViewSet):
    """
    GET  /api/tasks/                       -> my own assigned tasks (or, for assigner roles, everything they can see)
    POST /api/tasks/                       -> assign a task (Family Head: own family only; Chairman/Secretary/Admin: anyone)
    PATCH /api/tasks/{id}/                 -> update status (self-service; never reaches DONE directly — see decide_completion)
    GET  /api/tasks/mine/                  -> explicitly "my tasks" regardless of role
    POST /api/tasks/{id}/decide_completion/ -> approve or reject a Pending Approval task
    POST /api/tasks/{id}/reassign/         -> hand the task to someone else
    POST /api/tasks/{id}/archive/          -> hide from active views without deleting
    POST /api/tasks/{id}/unarchive/
    """
    serializer_class = MemberTaskSerializer
    permission_classes = [IsAuthenticated, CanAssignTasks, RequiresExecutiveContextForTaskCreation]
    lookup_field = "id"
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        from accounts.models import Role
        user = self.request.user
        qs = MemberTask.objects.filter(community=user.community).select_related("assigned_to", "assigned_by", "funeral_event")
        include_archived = self.request.query_params.get("include_archived") == "true"
        if not include_archived:
            qs = qs.filter(is_archived=False)
        own_member = getattr(user, "member_profile", None)
        from .permissions import COMMUNITY_WIDE_TASK_ROLES
        if user.is_superuser or user.role in COMMUNITY_WIDE_TASK_ROLES:
            return qs
        if user.role == Role.FAMILY_HEAD and own_member and own_member.family_id:
            return qs.filter(family_id=own_member.family_id)
        # Everyone else only ever sees tasks assigned to themselves.
        return qs.filter(assigned_to=own_member) if own_member else qs.none()

    def create(self, request, *args, **kwargs):
        serializer = AssignTaskSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        return Response(MemberTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        task = self.get_object()
        new_status = request.data.get("status")
        if new_status:
            try:
                services.update_task_status(task=task, status=new_status, actor=request.user)
            except DjangoValidationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MemberTaskSerializer(task).data)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            return Response([])
        return Response(MemberTaskSerializer(services.tasks_for_member(member), many=True).data)

    @action(detail=True, methods=["post"])
    def decide_completion(self, request, id=None):
        task = get_object_or_404(MemberTask, id=id, community=request.user.community)
        serializer = DecideTaskCompletionSerializer(data=request.data, context={"request": request, "task": task})
        serializer.is_valid(raise_exception=True)
        try:
            updated = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MemberTaskSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def reassign(self, request, id=None):
        task = get_object_or_404(MemberTask, id=id, community=request.user.community)
        serializer = ReassignTaskSerializer(data=request.data, context={"request": request, "task": task})
        serializer.is_valid(raise_exception=True)
        try:
            updated = serializer.save()
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MemberTaskSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, id=None):
        task = get_object_or_404(MemberTask, id=id, community=request.user.community)
        try:
            updated = services.archive_task(task=task, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MemberTaskSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def unarchive(self, request, id=None):
        task = get_object_or_404(MemberTask, id=id, community=request.user.community)
        try:
            updated = services.unarchive_task(task=task, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MemberTaskSerializer(updated).data)

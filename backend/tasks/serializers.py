from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from members.models import Member
from . import services
from .models import MemberTask
from .permissions import COMMUNITY_WIDE_TASK_ROLES


class MemberTaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True)
    assigned_by_name = serializers.CharField(source="assigned_by.get_full_name", read_only=True, default=None)
    funeral_deceased_name = serializers.CharField(source="funeral_event.deceased_name", read_only=True, default=None)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True, default=None)

    class Meta:
        model = MemberTask
        fields = [
            "id", "assigned_to", "assigned_to_name", "assigned_by_name", "family",
            "funeral_event", "funeral_deceased_name", "title", "description",
            "status", "priority", "due_date", "attachment", "is_archived",
            "approved_by_username", "approved_at", "rejection_note",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "assigned_to_name", "assigned_by_name", "family",
                            "funeral_deceased_name", "approved_by_username", "approved_at",
                            "created_at", "updated_at"]


def _check_family_head_scope(user, assignee):
    """Shared by AssignTaskSerializer and ReassignTaskSerializer — a Family Head can only act within their own family, the same scoping rule as member registration."""
    if user.is_superuser or user.role in COMMUNITY_WIDE_TASK_ROLES:
        return
    own_member = getattr(user, "member_profile", None)
    own_family_id = own_member.family_id if own_member else None
    if own_family_id is None or assignee.family_id != own_family_id:
        raise serializers.ValidationError("You can only act on members of your own family.")


class AssignTaskSerializer(serializers.Serializer):
    assigned_to_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(choices=MemberTask.Priority.choices, required=False, default=MemberTask.Priority.MEDIUM)
    due_date = serializers.DateField(required=False, allow_null=True)
    attachment = serializers.FileField(required=False, allow_null=True, default=None)
    funeral_event_id = serializers.UUIDField(required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        user = request.user
        data = self.validated_data

        try:
            assignee = Member.objects.get(id=data["assigned_to_id"], community=user.community)
        except Member.DoesNotExist:
            raise serializers.ValidationError({"assigned_to_id": "Member not found in this community."})

        _check_family_head_scope(user, assignee)

        funeral_event = None
        if data.get("funeral_event_id"):
            from funerals.models import FuneralEvent
            try:
                funeral_event = FuneralEvent.objects.get(id=data["funeral_event_id"], community=user.community)
            except FuneralEvent.DoesNotExist:
                raise serializers.ValidationError({"funeral_event_id": "Funeral not found in this community."})

        try:
            return services.assign_task(
                community=user.community, assigned_to=assignee, title=data["title"],
                description=data.get("description", ""), due_date=data.get("due_date"),
                priority=data.get("priority", MemberTask.Priority.MEDIUM), attachment=data.get("attachment"),
                assigned_by=user, funeral_event=funeral_event,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class DecideTaskCompletionSerializer(serializers.Serializer):
    """'Completion approval.'"""
    approved = serializers.BooleanField()
    rejection_note = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        request = self.context["request"]
        task = self.context["task"]
        try:
            return services.decide_task_completion(
                task=task, approved=self.validated_data["approved"],
                rejection_note=self.validated_data.get("rejection_note", ""), actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class ReassignTaskSerializer(serializers.Serializer):
    """'Reassignment.'"""
    new_assignee_id = serializers.UUIDField()

    def save(self, **kwargs):
        request = self.context["request"]
        task = self.context["task"]
        try:
            new_assignee = Member.objects.get(id=self.validated_data["new_assignee_id"], community=request.user.community)
        except Member.DoesNotExist:
            raise serializers.ValidationError({"new_assignee_id": "Member not found in this community."})
        _check_family_head_scope(request.user, new_assignee)
        try:
            return services.reassign_task(task=task, new_assignee=new_assignee, actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))

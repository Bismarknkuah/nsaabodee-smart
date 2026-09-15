import uuid

from django.conf import settings
from django.db import models


class MemberTask(models.Model):
    """
    "Head of each family should be able to register their members and
    assign them a task; same community chair or secretary should be
    able to add all members and assign task" — one task, one assignee,
    scoped exactly the same way member management itself is scoped: a
    Family Head can only assign within their own family (enforced in
    tasks/serializers.py, mirroring members/serializers.py's
    MemberRegisterSerializer), while Chairman/Secretary/Community Admin
    can assign to anyone in the community.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        # "Completion approval" — an assignee submits their own work as
        # done, but DONE itself is only ever reached through
        # services.decide_task_completion, never a direct status
        # update — see update_task_status's own guard against this.
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="+")
    assigned_to = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="tasks")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Denormalized rather than derived solely from assigned_to.family —
    # a task should stay associated with the family that assigned it
    # even if the member is later transferred elsewhere (families.services.transfer_members).
    family = models.ForeignKey("families.Family", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    funeral_event = models.ForeignKey(
        "funerals.FuneralEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks",
        help_text="Optional — many tasks ('welcome guests', 'arrange chairs') are tied to a specific funeral.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    attachment = models.FileField(upload_to="task_attachments/", null=True, blank=True)

    is_archived = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["community", "assigned_to"])]

    def __str__(self):
        return f"{self.title} -> {self.assigned_to.full_name} ({self.status})"

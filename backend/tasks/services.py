from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import MemberTask


def _can_act_on_assignee(actor, assignee) -> bool:
    """
    Shared by assign_task and reassign_task — a Family Head's authority
    stops at their own family's members, exactly the boundary already
    drawn everywhere else a Family Head acts. Community-wide roles
    (Community Admin, Chairman, Secretary) reach anyone in the
    community.
    """
    if actor is None or actor.is_superuser:
        return True
    if actor.role != "family_head":
        return True  # community-wide roles checked at the view/permission layer already
    own_family = getattr(getattr(actor, "member_profile", None), "family_id", None)
    return bool(own_family is not None and assignee.family_id == own_family)


def assign_task(*, community, assigned_to, title, description="", due_date=None,
                 priority=MemberTask.Priority.MEDIUM, attachment=None,
                 assigned_by=None, funeral_event=None):
    if assigned_to.community_id != community.id:
        raise ValidationError("The assignee must belong to this community.")
    if funeral_event is not None and funeral_event.community_id != community.id:
        raise ValidationError("The funeral must belong to this community.")
    if not _can_act_on_assignee(assigned_by, assigned_to):
        raise ValidationError("A Family Head can only assign tasks to members of their own family.")

    return MemberTask.objects.create(
        community=community,
        assigned_to=assigned_to,
        assigned_by=assigned_by,
        family=assigned_to.family,
        funeral_event=funeral_event,
        title=title.strip(),
        description=description.strip(),
        due_date=due_date,
        priority=priority,
        attachment=attachment,
    )


def update_task_status(*, task: MemberTask, status: str, actor=None):
    """
    Self-service — the assignee moves their own task through Pending,
    In Progress, and Pending Approval freely. DONE itself is
    deliberately unreachable here: "completion approval" means an
    assignee submits their work (Pending Approval) but never marks it
    DONE themselves — see decide_task_completion, which is the only
    path to DONE and requires the assigner's own authority, not the
    assignee's.
    """
    if status not in MemberTask.Status.values:
        raise ValidationError(f"'{status}' is not a valid task status.")
    if status == MemberTask.Status.DONE:
        raise ValidationError("A task can't be marked done directly — submit it as Pending Approval, then have it approved.")
    task.status = status
    task.save(update_fields=["status", "updated_at"])
    return task


def decide_task_completion(*, task: MemberTask, approved: bool, rejection_note: str = "", actor):
    """
    'Completion approval' — the assigner (or community-wide leadership,
    or the family's own Head if this is a family task) reviews a task
    submitted as Pending Approval. Approved -> DONE, with who approved
    it and when recorded. Rejected -> back to In Progress with a note
    explaining why, so the assignee knows what to fix — never a dead
    end, always actionable.
    """
    if task.status != MemberTask.Status.PENDING_APPROVAL:
        raise ValidationError("Only a task that's been submitted as Pending Approval can be approved or rejected.")
    if not _can_act_on_assignee(actor, task.assigned_to):
        raise ValidationError("You don't have authority to decide this task's completion.")

    if approved:
        task.status = MemberTask.Status.DONE
        task.approved_by = actor
        task.approved_at = timezone.now()
        task.rejection_note = ""
        task.save(update_fields=["status", "approved_by", "approved_at", "rejection_note", "updated_at"])
    else:
        if not rejection_note.strip():
            raise ValidationError("A rejection needs a note explaining what still needs work.")
        task.status = MemberTask.Status.IN_PROGRESS
        task.rejection_note = rejection_note.strip()
        task.save(update_fields=["status", "rejection_note", "updated_at"])
    return task


def reassign_task(*, task: MemberTask, new_assignee, actor):
    """'Reassignment' — same authority as the original assignment: the actor must be allowed to assign TO the new person, not just to have assigned the task originally."""
    if new_assignee.community_id != task.community_id:
        raise ValidationError("The new assignee must belong to this community.")
    if not _can_act_on_assignee(actor, new_assignee):
        raise ValidationError("You don't have authority to assign a task to this member.")
    task.assigned_to = new_assignee
    task.family = new_assignee.family
    task.status = MemberTask.Status.PENDING
    task.approved_by = None
    task.approved_at = None
    task.rejection_note = ""
    task.save(update_fields=["assigned_to", "family", "status", "approved_by", "approved_at", "rejection_note", "updated_at"])
    return task


def archive_task(*, task: MemberTask, actor):
    """'Archive' — same authority as assignment; hides a task from the active views without deleting its history."""
    if not _can_act_on_assignee(actor, task.assigned_to):
        raise ValidationError("You don't have authority to archive this task.")
    task.is_archived = True
    task.save(update_fields=["is_archived", "updated_at"])
    return task


def unarchive_task(*, task: MemberTask, actor):
    if not _can_act_on_assignee(actor, task.assigned_to):
        raise ValidationError("You don't have authority to unarchive this task.")
    task.is_archived = False
    task.save(update_fields=["is_archived", "updated_at"])
    return task


def tasks_for_member(member):
    return MemberTask.objects.filter(assigned_to=member).select_related("assigned_by", "funeral_event")


def tasks_assigned_by_family_head(family):
    """Every task assigned to a member of this family — a Family Head's own oversight view."""
    return MemberTask.objects.filter(family=family).select_related("assigned_to", "assigned_by")

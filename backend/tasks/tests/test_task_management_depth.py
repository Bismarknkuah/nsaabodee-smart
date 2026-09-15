from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tasks import services as task_services
from tasks.models import MemberTask
from tenants.models import Community


class TaskManagementDepthTests(TestCase):
    """'Priorities, Deadlines, Attachments, Notes, Progress tracking, Completion approval, Reassignment, Archive.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-task-depth")
        self.admin = User.objects.create_user(username="task_depth_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Task Depth Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="task_depth_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.worker = member_services.register_member(community=self.bodi, full_name="Task Worker", gender="male", family=self.asona)
        self.other_worker = member_services.register_member(community=self.bodi, full_name="Other Worker", gender="female", family=self.asona)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Person", gender="male", family=self.bretuo)

    def test_a_task_can_be_assigned_with_a_priority(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Urgent errand",
                                          priority=MemberTask.Priority.URGENT, assigned_by=self.admin)
        self.assertEqual(task.priority, MemberTask.Priority.URGENT)

    def test_priority_defaults_to_medium(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Ordinary errand", assigned_by=self.admin)
        self.assertEqual(task.priority, MemberTask.Priority.MEDIUM)

    def test_a_task_cannot_be_marked_done_directly(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.admin)
        with self.assertRaises(ValidationError):
            task_services.update_task_status(task=task, status=MemberTask.Status.DONE, actor=self.admin)

    def test_submitting_for_approval_then_approving_reaches_done(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.admin)
        task_services.update_task_status(task=task, status=MemberTask.Status.PENDING_APPROVAL, actor=self.admin)
        updated = task_services.decide_task_completion(task=task, approved=True, actor=self.admin)
        self.assertEqual(updated.status, MemberTask.Status.DONE)
        self.assertEqual(updated.approved_by_id, self.admin.id)

    def test_rejecting_sends_it_back_to_in_progress_with_a_note(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.admin)
        task_services.update_task_status(task=task, status=MemberTask.Status.PENDING_APPROVAL, actor=self.admin)
        updated = task_services.decide_task_completion(task=task, approved=False, rejection_note="The yard still has leaves.", actor=self.admin)
        self.assertEqual(updated.status, MemberTask.Status.IN_PROGRESS)
        self.assertIn("leaves", updated.rejection_note)

    def test_a_rejection_without_a_note_is_rejected(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.admin)
        task_services.update_task_status(task=task, status=MemberTask.Status.PENDING_APPROVAL, actor=self.admin)
        with self.assertRaises(ValidationError):
            task_services.decide_task_completion(task=task, approved=False, actor=self.admin)

    def test_cannot_decide_completion_on_a_task_thats_not_pending_approval(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.admin)
        with self.assertRaises(ValidationError):
            task_services.decide_task_completion(task=task, approved=True, actor=self.admin)

    def test_a_family_head_can_approve_their_own_familys_tasks(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.head_user)
        task_services.update_task_status(task=task, status=MemberTask.Status.PENDING_APPROVAL, actor=self.head_user)
        updated = task_services.decide_task_completion(task=task, approved=True, actor=self.head_user)
        self.assertEqual(updated.status, MemberTask.Status.DONE)

    def test_reassigning_moves_the_task_to_a_new_member_and_resets_its_status(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.admin)
        task_services.update_task_status(task=task, status=MemberTask.Status.IN_PROGRESS, actor=self.admin)
        updated = task_services.reassign_task(task=task, new_assignee=self.other_worker, actor=self.admin)
        self.assertEqual(updated.assigned_to_id, self.other_worker.id)
        self.assertEqual(updated.status, MemberTask.Status.PENDING)

    def test_a_family_head_cannot_reassign_outside_their_own_family(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.head_user)
        with self.assertRaises(ValidationError):
            task_services.reassign_task(task=task, new_assignee=self.bretuo_member, actor=self.head_user)

    def test_archiving_and_unarchiving_a_task(self):
        task = task_services.assign_task(community=self.bodi, assigned_to=self.worker, title="Task", assigned_by=self.admin)
        archived = task_services.archive_task(task=task, actor=self.admin)
        self.assertTrue(archived.is_archived)
        unarchived = task_services.unarchive_task(task=task, actor=self.admin)
        self.assertFalse(unarchived.is_archived)


class TaskManagementDepthHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-task-depth-http")
        self.admin = User.objects.create_user(username="task_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.worker = member_services.register_member(community=self.bodi, full_name="HTTP Worker", gender="male", family=self.asona)
        self.other_worker = member_services.register_member(community=self.bodi, full_name="HTTP Other Worker", gender="female", family=self.asona)
        self.worker_user = User.objects.create_user(username="task_http_worker", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.worker, user=self.worker_user, actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_round_trip_assign_submit_approve_reassign_archive(self):
        admin_client = self._login("task_http_admin")
        assign_res = admin_client.post("/api/tasks/", {"assigned_to_id": str(self.worker.id), "title": "Sweep", "priority": "high"})
        self.assertEqual(assign_res.status_code, 201)
        self.assertEqual(assign_res.data["priority"], "high")
        task_id = assign_res.data["id"]

        worker_client = self._login("task_http_worker")
        submit_res = worker_client.patch(f"/api/tasks/{task_id}/", {"status": "pending_approval"}, format="json")
        self.assertEqual(submit_res.status_code, 200)

        approve_res = admin_client.post(f"/api/tasks/{task_id}/decide_completion/", {"approved": True})
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.data["status"], "done")

        reassign_res = admin_client.post(f"/api/tasks/{task_id}/reassign/", {"new_assignee_id": str(self.other_worker.id)})
        self.assertEqual(reassign_res.status_code, 200)
        self.assertEqual(reassign_res.data["status"], "pending")

        archive_res = admin_client.post(f"/api/tasks/{task_id}/archive/")
        self.assertEqual(archive_res.status_code, 200)
        self.assertTrue(archive_res.data["is_archived"])

        list_res = admin_client.get("/api/tasks/")
        self.assertEqual(len(list_res.data["results"]), 0)
        include_archived_res = admin_client.get("/api/tasks/?include_archived=true")
        self.assertEqual(len(include_archived_res.data["results"]), 1)

    def test_an_ordinary_member_cannot_approve_their_own_completion(self):
        admin_client = self._login("task_http_admin")
        assign_res = admin_client.post("/api/tasks/", {"assigned_to_id": str(self.worker.id), "title": "Sweep"})
        task_id = assign_res.data["id"]

        worker_client = self._login("task_http_worker")
        worker_client.patch(f"/api/tasks/{task_id}/", {"status": "pending_approval"}, format="json")
        res = worker_client.post(f"/api/tasks/{task_id}/decide_completion/", {"approved": True})
        self.assertEqual(res.status_code, 403)

    def test_an_ordinary_member_cannot_reassign_or_archive(self):
        admin_client = self._login("task_http_admin")
        assign_res = admin_client.post("/api/tasks/", {"assigned_to_id": str(self.worker.id), "title": "Sweep"})
        task_id = assign_res.data["id"]

        worker_client = self._login("task_http_worker")
        res1 = worker_client.post(f"/api/tasks/{task_id}/reassign/", {"new_assignee_id": str(self.other_worker.id)})
        self.assertIn(res1.status_code, (400, 403))
        res2 = worker_client.post(f"/api/tasks/{task_id}/archive/")
        self.assertIn(res2.status_code, (400, 403))

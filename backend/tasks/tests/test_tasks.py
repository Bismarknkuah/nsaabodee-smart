from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tasks.models import MemberTask
from tenants.models import Community


class TaskAssignmentTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.asona_member = member_services.register_member(community=self.bodi, full_name="Asona Kid", gender="male", family=self.asona)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Kid", gender="male", family=self.bretuo)

        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_family_head_can_assign_task_to_own_family_member(self):
        client = self._login("abusuapanin")
        res = client.post("/api/tasks/", {"assigned_to_id": str(self.asona_member.id), "title": "Arrange chairs"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["title"], "Arrange chairs")

    def test_family_head_cannot_assign_task_outside_own_family(self):
        client = self._login("abusuapanin")
        res = client.post("/api/tasks/", {"assigned_to_id": str(self.bretuo_member.id), "title": "Sneaky task"})
        self.assertEqual(res.status_code, 400)

    def test_secretary_can_assign_task_to_anyone(self):
        client = self._login("secretary")
        res = client.post("/api/tasks/", {"assigned_to_id": str(self.bretuo_member.id), "title": "Welcome guests"})
        self.assertEqual(res.status_code, 201)

    def test_ordinary_member_cannot_assign_tasks(self):
        rando = User.objects.create_user(username="rando", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        client = self._login("rando")
        res = client.post("/api/tasks/", {"assigned_to_id": str(self.asona_member.id), "title": "Nope"})
        self.assertEqual(res.status_code, 403)

    def test_assignee_submits_for_approval_then_the_assigner_approves_it_done(self):
        """'Completion approval' — an assignee can never mark their own task DONE directly; they submit it, and the assigner decides."""
        member_user = User.objects.create_user(username="asona_kid_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.asona_member, user=member_user, actor=self.admin)

        from tasks import services as task_services
        task = task_services.assign_task(community=self.bodi, assigned_to=self.asona_member, title="Sweep the yard", assigned_by=self.admin)

        client = self._login("asona_kid_login")
        direct_done_res = client.patch(f"/api/tasks/{task.id}/", {"status": "done"}, format="json")
        self.assertEqual(direct_done_res.status_code, 400)

        submit_res = client.patch(f"/api/tasks/{task.id}/", {"status": "pending_approval"}, format="json")
        self.assertEqual(submit_res.status_code, 200)
        self.assertEqual(submit_res.data["status"], "pending_approval")

        admin_client = self._login("admin")
        approve_res = admin_client.post(f"/api/tasks/{task.id}/decide_completion/", {"approved": True})
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.data["status"], "done")
        task.refresh_from_db()
        self.assertEqual(task.status, MemberTask.Status.DONE)
        self.assertIsNotNone(task.approved_at)

    def test_member_only_sees_their_own_tasks_not_everyone_elses(self):
        member_user = User.objects.create_user(username="asona_kid_login2", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.asona_member, user=member_user, actor=self.admin)

        from tasks import services as task_services
        task_services.assign_task(community=self.bodi, assigned_to=self.asona_member, title="My task", assigned_by=self.admin)
        task_services.assign_task(community=self.bodi, assigned_to=self.bretuo_member, title="Someone else's task", assigned_by=self.admin)

        client = self._login("asona_kid_login2")
        res = client.get("/api/tasks/")
        titles = [t["title"] for t in res.data["results"]]
        self.assertIn("My task", titles)
        self.assertNotIn("Someone else's task", titles)

    def test_family_head_sees_all_tasks_within_his_family(self):
        from tasks import services as task_services
        task_services.assign_task(community=self.bodi, assigned_to=self.asona_member, title="Family task", assigned_by=self.admin)

        client = self._login("abusuapanin")
        res = client.get("/api/tasks/")
        titles = [t["title"] for t in res.data["results"]]
        self.assertIn("Family task", titles)

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import PlanInterestSubmission


class PlanInterestServiceTests(TestCase):
    """'Make sure all coming soon are completely designed' — turning a dead disabled button into real, actionable lead capture."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="plan_interest_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="plan_interest_community_admin", password="x", role=Role.COMMUNITY_ADMIN)

    def test_submitting_interest_with_an_email(self):
        submission = services.submit_plan_interest(plan_type="single_funeral", name="Kwame", email="kwame@example.com")
        self.assertEqual(submission.plan_type, "single_funeral")

    def test_submitting_interest_with_a_phone_number_instead_of_email(self):
        submission = services.submit_plan_interest(plan_type="community", name="Ama", phone="0244000000")
        self.assertEqual(submission.phone, "0244000000")

    def test_a_name_is_required(self):
        with self.assertRaises(ValidationError):
            services.submit_plan_interest(plan_type="community", name="", email="x@example.com")

    def test_at_least_one_way_to_reach_the_person_is_required(self):
        with self.assertRaises(ValidationError):
            services.submit_plan_interest(plan_type="community", name="No Contact Info")

    def test_only_a_platform_admin_can_view_submissions(self):
        services.submit_plan_interest(plan_type="community", name="Kwame", email="kwame@example.com")
        with self.assertRaises(ValidationError):
            services.list_plan_interest_submissions(actor=self.community_admin)
        submissions = services.list_plan_interest_submissions(actor=self.platform_admin)
        self.assertEqual(len(submissions), 1)

    def test_marking_a_submission_contacted(self):
        submission = services.submit_plan_interest(plan_type="multi_community", name="Kwame", email="kwame@example.com")
        updated = services.mark_plan_interest_contacted(submission=submission, actor=self.platform_admin)
        self.assertTrue(updated.contacted)


class PlanInterestHttpTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="plan_interest_http_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def test_submitting_interest_requires_no_login_at_all(self):
        client = APIClient()  # deliberately no credentials
        res = client.post("/api/tenants/plan-interest/", {"plan_type": "single_funeral", "name": "Kwame", "email": "kwame@example.com"})
        self.assertEqual(res.status_code, 201)

    def test_viewing_submissions_requires_login_and_platform_admin_permission(self):
        client = APIClient()
        res = client.get("/api/tenants/plan-interest/manage/")
        self.assertEqual(res.status_code, 401)

    def test_full_submit_then_view_then_mark_contacted_flow(self):
        public_client = APIClient()
        public_client.post("/api/tenants/plan-interest/", {"plan_type": "community", "name": "Ama", "phone": "0244000000"})

        admin_client = APIClient()
        login = admin_client.post("/api/auth/login/", {"username": "plan_interest_http_admin", "password": "a-real-password-123"})
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        list_res = admin_client.get("/api/tenants/plan-interest/manage/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.data), 1)
        submission_id = list_res.data[0]["id"]

        contacted_res = admin_client.post(f"/api/tenants/plan-interest/{submission_id}/mark-contacted/")
        self.assertEqual(contacted_res.status_code, 200)
        self.assertTrue(contacted_res.data["contacted"])

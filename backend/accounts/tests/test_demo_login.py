from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role


class DemoLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo_data")

    def test_demo_login_works_for_every_role(self):
        client = APIClient()
        for role in Role.values:
            res = client.post("/api/auth/demo-login/", {"role": role})
            self.assertEqual(res.status_code, 200, f"demo login failed for role {role}: {res.data}")
            self.assertIn("access", res.data)

    def test_demo_login_disabled_returns_404(self):
        with override_settings(DEMO_MODE_ENABLED=False):
            client = APIClient()
            res = client.post("/api/auth/demo-login/", {"role": Role.CHAIRMAN})
            self.assertEqual(res.status_code, 404)

    def test_unknown_role_returns_404(self):
        client = APIClient()
        res = client.post("/api/auth/demo-login/", {"role": "not_a_real_role"})
        self.assertEqual(res.status_code, 404)

    def test_every_role_gets_a_dashboard_with_at_least_one_section(self):
        """The whole point of the demo — every role's dashboard actually shows something, not an empty shell."""
        client = APIClient()
        for role in Role.values:
            login = client.post("/api/auth/demo-login/", {"role": role})
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
            res = client.get("/api/dashboard/")
            self.assertEqual(res.status_code, 200, f"dashboard failed for role {role}")
            self.assertTrue(len(res.data["sections"]) > 0, f"role {role} got an empty dashboard")

    def test_seeding_twice_does_not_duplicate_or_error(self):
        call_command("seed_demo_data")
        call_command("seed_demo_data")  # ran a third time overall (once in setUpTestData) — must stay idempotent

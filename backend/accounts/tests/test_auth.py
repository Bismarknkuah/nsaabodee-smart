from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants.models import Community


class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.user = User.objects.create_user(
            username="collector1", password="correct-horse-battery-staple",
            community=self.bodi, role=Role.COLLECTOR,
        )

    def test_login_with_correct_credentials_returns_tokens(self):
        res = self.client.post("/api/auth/login/", {"username": "collector1", "password": "correct-horse-battery-staple"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_login_embeds_role_and_community_claims(self):
        import jwt
        res = self.client.post("/api/auth/login/", {"username": "collector1", "password": "correct-horse-battery-staple"})
        payload = jwt.decode(res.data["access"], options={"verify_signature": False})
        self.assertEqual(payload["role"], Role.COLLECTOR)
        self.assertEqual(payload["community_id"], str(self.bodi.id))

    def test_login_with_wrong_password_rejected(self):
        res = self.client.post("/api/auth/login/", {"username": "collector1", "password": "wrong"})
        self.assertEqual(res.status_code, 401)

    def test_protected_endpoint_requires_a_token(self):
        res = self.client.get("/api/members/")
        self.assertEqual(res.status_code, 401)

    def test_protected_endpoint_works_with_a_valid_token(self):
        login = self.client.post("/api/auth/login/", {"username": "collector1", "password": "correct-horse-battery-staple"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = self.client.get("/api/members/")
        self.assertEqual(res.status_code, 200)

    def test_me_endpoint_returns_own_identity(self):
        login = self.client.post("/api/auth/login/", {"username": "collector1", "password": "correct-horse-battery-staple"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["username"], "collector1")
        self.assertEqual(res.data["role"], Role.COLLECTOR)
        self.assertEqual(res.data["community_name"], "Bodi Anidasoɔ")
        self.assertIsNone(res.data["linked_member_id"])

    def test_refresh_token_issues_a_new_access_token(self):
        login = self.client.post("/api/auth/login/", {"username": "collector1", "password": "correct-horse-battery-staple"})
        res = self.client.post("/api/auth/refresh/", {"refresh": login.data["refresh"]})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)

    def test_logout_blacklists_the_refresh_token(self):
        login = self.client.post("/api/auth/login/", {"username": "collector1", "password": "correct-horse-battery-staple"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        logout_res = self.client.post("/api/auth/logout/", {"refresh": login.data["refresh"]})
        self.assertEqual(logout_res.status_code, 205)

        # The same refresh token must now be rejected, not silently accepted.
        reuse_res = self.client.post("/api/auth/refresh/", {"refresh": login.data["refresh"]})
        self.assertEqual(reuse_res.status_code, 401)

    def test_a_users_own_community_is_never_chosen_at_login_time(self):
        """
        Login is just username+password; which community a user belongs
        to is a property of their account (User.community), never a
        parameter the client can pass at sign-in — otherwise anyone could
        try to log into a different community's data by supplying a
        different community id.
        """
        login = self.client.post(
            "/api/auth/login/",
            {"username": "collector1", "password": "correct-horse-battery-staple", "community": "some-other-id"},
        )
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        me = self.client.get("/api/auth/me/")
        self.assertEqual(str(me.data["community"]), str(self.bodi.id))

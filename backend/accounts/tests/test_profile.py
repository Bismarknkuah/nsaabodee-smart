import io

from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Role, User


def _fake_image_upload(name="photo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    buf.seek(0)
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


class ProfileTests(TestCase):
    """'Should be able to change their profile and upload dp.'"""

    def setUp(self):
        self.user = User.objects.create_user(username="profiletest", password="a-real-password-123", role=Role.COMMUNITY_MEMBER)

    def _login(self):
        client = APIClient()
        res = client.post("/api/auth/login/", {"username": "profiletest", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return client

    def test_me_endpoint_includes_profile_photo_url_field(self):
        client = self._login()
        res = client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("profile_photo_url", res.data)
        self.assertIsNone(res.data["profile_photo_url"])

    def test_uploading_a_profile_photo(self):
        client = self._login()
        res = client.patch("/api/auth/me/", {"profile_photo": _fake_image_upload()}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.data["profile_photo_url"])
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile_photo))

    def test_updating_email(self):
        client = self._login()
        res = client.patch("/api/auth/me/", {"email": "new@example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], "new@example.com")

    def test_cannot_change_role_or_username_through_this_endpoint(self):
        """These are administrative decisions, not self-service ones — the serializer doesn't expose them at all, so sending them is silently ignored, not a security bypass."""
        client = self._login()
        res = client.patch("/api/auth/me/", {"username": "hacked", "role": "platform_admin"})
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "profiletest")
        self.assertEqual(self.user.role, Role.COMMUNITY_MEMBER)

    def test_changing_password_with_correct_current_password(self):
        client = self._login()
        res = client.post("/api/auth/change-password/", {
            "current_password": "a-real-password-123", "new_password": "a-new-real-password-456",
        })
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-new-real-password-456"))

    def test_changing_password_with_wrong_current_password_is_rejected(self):
        client = self._login()
        res = client.post("/api/auth/change-password/", {
            "current_password": "totally-wrong", "new_password": "a-new-real-password-456",
        })
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-real-password-123"))

    def test_a_new_password_can_immediately_log_in(self):
        client = self._login()
        client.post("/api/auth/change-password/", {
            "current_password": "a-real-password-123", "new_password": "a-new-real-password-456",
        })
        fresh_client = APIClient()
        res = fresh_client.post("/api/auth/login/", {"username": "profiletest", "password": "a-new-real-password-456"})
        self.assertEqual(res.status_code, 200)

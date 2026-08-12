import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import HomepageImage


def _fake_image(name="hero.png"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="green").save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


class HomepageImageServiceTests(TestCase):
    """'The homepage live pictures which will be changing should be uploaded by the super admin.'"""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="homepage_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="homepage_community_admin", password="x", role=Role.COMMUNITY_ADMIN)

    def test_platform_admin_can_upload_a_homepage_image(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin, caption="Supporting Families")
        self.assertEqual(image.caption, "Supporting Families")

    def test_a_community_admin_cannot_upload_a_homepage_image(self):
        """This is the public homepage's own content, not any single community's."""
        with self.assertRaises(ValidationError):
            services.upload_homepage_image(image=_fake_image(), actor=self.community_admin)

    def test_public_listing_only_ever_returns_active_images(self):
        active = services.upload_homepage_image(image=_fake_image("a.png"), actor=self.platform_admin, caption="Active")
        inactive = services.upload_homepage_image(image=_fake_image("b.png"), actor=self.platform_admin, caption="Inactive")
        services.deactivate_homepage_image(homepage_image=inactive, actor=self.platform_admin)

        public_list = services.list_public_homepage_images()
        self.assertEqual(len(public_list), 1)
        self.assertEqual(public_list[0].caption, "Active")

    def test_a_community_admin_cannot_deactivate_a_homepage_image(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin)
        with self.assertRaises(ValidationError):
            services.deactivate_homepage_image(homepage_image=image, actor=self.community_admin)

    def test_management_listing_shows_both_active_and_inactive(self):
        services.upload_homepage_image(image=_fake_image("a.png"), actor=self.platform_admin)
        inactive = services.upload_homepage_image(image=_fake_image("b.png"), actor=self.platform_admin)
        services.deactivate_homepage_image(homepage_image=inactive, actor=self.platform_admin)
        self.assertEqual(len(services.list_all_homepage_images(actor=self.platform_admin)), 2)


class HomepageImageHttpTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="homepage_http_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "homepage_http_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_viewing_the_public_list_requires_no_login_at_all(self):
        self._login().post("/api/tenants/homepage-images/manage/", {"image": _fake_image(), "caption": "Test"}, format="multipart")
        client = APIClient()  # deliberately no credentials
        res = client.get("/api/tenants/homepage-images/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertIsNotNone(res.data[0]["image_url"])

    def test_uploading_requires_login_and_platform_admin_permission(self):
        client = APIClient()
        res = client.post("/api/tenants/homepage-images/manage/", {"image": _fake_image()}, format="multipart")
        self.assertEqual(res.status_code, 401)

    def test_full_upload_then_deactivate_flow_via_http(self):
        client = self._login()
        upload_res = client.post("/api/tenants/homepage-images/manage/", {"image": _fake_image(), "caption": "Hero shot"}, format="multipart")
        self.assertEqual(upload_res.status_code, 201)
        image_id = upload_res.data["id"]

        deactivate_res = client.post(f"/api/tenants/homepage-images/{image_id}/deactivate/")
        self.assertEqual(deactivate_res.status_code, 204)

        public_res = APIClient().get("/api/tenants/homepage-images/")
        self.assertEqual(len(public_res.data), 0)

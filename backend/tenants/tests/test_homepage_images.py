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


class HomepageImageEditReactivateDeleteTests(TestCase):
    """'The platform admin should have option to edit, add, upload, or delete some of the photos.' Closing the gap: only upload and deactivate existed before."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="hierd_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="hierd_community_admin", password="x", role=Role.COMMUNITY_ADMIN)

    def test_platform_admin_can_edit_caption_subcaption_and_order(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin, caption="Old")
        updated = services.update_homepage_image(homepage_image=image, actor=self.platform_admin, caption="New Caption", subcaption="New Subcaption", display_order=5)
        self.assertEqual(updated.caption, "New Caption")
        self.assertEqual(updated.subcaption, "New Subcaption")
        self.assertEqual(updated.display_order, 5)

    def test_editing_only_one_field_leaves_the_others_untouched(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin, caption="Keep This", subcaption="Also Keep This")
        updated = services.update_homepage_image(homepage_image=image, actor=self.platform_admin, display_order=2)
        self.assertEqual(updated.caption, "Keep This")
        self.assertEqual(updated.subcaption, "Also Keep This")

    def test_a_community_admin_cannot_edit_a_homepage_image(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin)
        with self.assertRaises(ValidationError):
            services.update_homepage_image(homepage_image=image, actor=self.community_admin, caption="Hacked")

    def test_reactivating_a_deactivated_image_brings_it_back_to_the_public_list(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin, caption="Toggle Me")
        services.deactivate_homepage_image(homepage_image=image, actor=self.platform_admin)
        self.assertEqual(len(services.list_public_homepage_images()), 0)
        services.reactivate_homepage_image(homepage_image=image, actor=self.platform_admin)
        self.assertEqual(len(services.list_public_homepage_images()), 1)

    def test_a_community_admin_cannot_reactivate_a_homepage_image(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin)
        services.deactivate_homepage_image(homepage_image=image, actor=self.platform_admin)
        with self.assertRaises(ValidationError):
            services.reactivate_homepage_image(homepage_image=image, actor=self.community_admin)

    def test_deleting_an_image_permanently_removes_it_unlike_deactivate(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin)
        image_id = image.id
        services.delete_homepage_image(homepage_image=image, actor=self.platform_admin)
        self.assertFalse(HomepageImage.objects.filter(id=image_id).exists())

    def test_a_community_admin_cannot_delete_a_homepage_image(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin)
        with self.assertRaises(ValidationError):
            services.delete_homepage_image(homepage_image=image, actor=self.community_admin)


class HomepageImageEditReactivateDeleteHttpTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="hierdh_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "hierdh_platform_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_edit_reactivate_delete_round_trip_over_http(self):
        client = self._login()
        upload_res = client.post("/api/tenants/homepage-images/manage/", {"image": _fake_image(), "caption": "Original"}, format="multipart")
        image_id = upload_res.data["id"]

        patch_res = client.patch(f"/api/tenants/homepage-images/{image_id}/", {"caption": "Edited"}, format="json")
        self.assertEqual(patch_res.status_code, 200, patch_res.data)
        self.assertEqual(patch_res.data["caption"], "Edited")

        deactivate_res = client.post(f"/api/tenants/homepage-images/{image_id}/deactivate/")
        self.assertEqual(deactivate_res.status_code, 204)

        reactivate_res = client.post(f"/api/tenants/homepage-images/{image_id}/reactivate/")
        self.assertEqual(reactivate_res.status_code, 200, reactivate_res.data)
        self.assertTrue(reactivate_res.data["is_active"])

        delete_res = client.delete(f"/api/tenants/homepage-images/{image_id}/")
        self.assertEqual(delete_res.status_code, 204)
        self.assertEqual(HomepageImage.objects.filter(id=image_id).count(), 0)

    def test_editing_without_login_is_rejected(self):
        image = services.upload_homepage_image(image=_fake_image(), actor=self.platform_admin)
        client = APIClient()
        res = client.patch(f"/api/tenants/homepage-images/{image.id}/", {"caption": "Hacked"}, format="json")
        self.assertEqual(res.status_code, 401)


def _fake_video(name="clip.mp4"):
    return SimpleUploadedFile(name, b"fake video bytes for testing", content_type="video/mp4")


class HomepageVideoUploadTests(TestCase):
    """'The platform admin should be able to upload videos as well.'"""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="hvu_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def test_uploading_a_video_only_slide_succeeds(self):
        homepage_image = services.upload_homepage_image(video=_fake_video(), actor=self.platform_admin, caption="Our Story")
        self.assertIsNone(homepage_image.image.name if homepage_image.image else None)
        self.assertTrue(homepage_image.video.name)

    def test_a_slide_needs_at_least_one_of_image_or_video(self):
        with self.assertRaises(ValidationError):
            services.upload_homepage_image(actor=self.platform_admin, caption="Nothing attached")

    def test_a_slide_cannot_have_both_image_and_video(self):
        with self.assertRaises(ValidationError):
            services.upload_homepage_image(image=_fake_image(), video=_fake_video(), actor=self.platform_admin)

    def test_the_public_list_serializes_video_url_for_a_video_slide(self):
        services.upload_homepage_image(video=_fake_video(), actor=self.platform_admin, caption="Video Slide")
        public_list = services.list_public_homepage_images()
        self.assertIsNotNone(public_list[0].video.url)

    def test_full_http_video_upload_round_trip(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "hvu_platform_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/tenants/homepage-images/manage/", {"video": _fake_video(), "caption": "Video Test"}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNotNone(res.data["video_url"])
        self.assertIsNone(res.data["image_url"])

    def test_http_upload_with_neither_image_nor_video_is_rejected_cleanly(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "hvu_platform_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/tenants/homepage-images/manage/", {"caption": "Nothing"}, format="multipart")
        self.assertEqual(res.status_code, 400)

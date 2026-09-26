from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from tenants.models import Community


@override_settings(FRONTEND_BASE_URL="https://app.nsaabodeesmart.com")
class FuneralQrCodeTests(TestCase):
    """
    'The community admin should be able to generate a barcode so that
    it can be printed and pasted for guests to use to donate their
    gift or contribute. Same as members or anyone once you scan it
    should take you to what the barcode was meant for.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-qr",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="qr_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_the_qr_payload_is_a_real_scannable_url_not_a_custom_app_scheme(self):
        """The actual bug this fixed — the old nsaabodee:// scheme couldn't be opened by an ordinary phone camera."""
        self.assertTrue(self.funeral.qr_payload.startswith("https://"))
        self.assertIn(f"/memorial/{self.funeral.id}", self.funeral.qr_payload)

    def test_the_qr_payload_points_to_the_actual_public_memorial_page(self):
        """Not just a plausible-looking URL — one that a guest scanning it would land on a real, working page."""
        expected_url = f"https://app.nsaabodeesmart.com/memorial/{self.funeral.id}"
        self.assertEqual(self.funeral.qr_payload, expected_url)

    def test_generating_the_qr_code_produces_a_real_image(self):
        qr_base64 = funeral_services.generate_funeral_qr_code_base64(self.funeral)
        self.assertGreater(len(qr_base64), 100)

    def test_the_http_endpoint_returns_both_the_image_and_the_url(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "qr_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/funerals/{self.funeral.id}/qr-code/")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.data["qr_code_base64"]), 100)
        self.assertEqual(res.data["url"], self.funeral.qr_payload)

    def test_a_different_communitys_admin_cannot_generate_this_funerals_qr_code(self):
        other_community = Community.objects.create(name="Other Town", slug="other-qr")
        other_admin = User.objects.create_user(username="qr_other_admin", password="a-real-password-123", community=other_community, role=Role.COMMUNITY_ADMIN)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "qr_other_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/funerals/{self.funeral.id}/qr-code/")
        self.assertEqual(res.status_code, 404)

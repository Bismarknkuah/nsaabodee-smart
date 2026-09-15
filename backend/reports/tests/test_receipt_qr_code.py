import base64
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


@override_settings(FRONTEND_BASE_URL="https://app.nsaabodeesmart.com")
class ContributionReceiptQrCodeTests(TestCase):
    """'The receipt should have a bar scan code so that they can scan to confirm their payment.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="crqc-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="crqc_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        self.payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector_name="Test Collector")

    def test_the_verify_url_matches_the_payments_own_qr_payload(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "crqc_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/receipts/contribution-payments/{self.payment.id}/qr-code/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["verify_url"], self.payment.qr_payload)
        self.assertIn(f"/verify-receipt/{self.payment.id}", res.data["verify_url"])

    def test_the_qr_code_is_a_real_decodable_png(self):
        """Not just a plausible-looking base64 string — an actual image a printer or browser could render."""
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "crqc_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/receipts/contribution-payments/{self.payment.id}/qr-code/")
        png_bytes = base64.b64decode(res.data["qr_code_base64"])
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")  # the real PNG magic number, not a guess

    def test_an_unauthenticated_request_is_rejected(self):
        client = APIClient()
        res = client.get(f"/api/receipts/contribution-payments/{self.payment.id}/qr-code/")
        self.assertEqual(res.status_code, 401)

    def test_a_different_communitys_user_cannot_reach_this_payments_qr_code(self):
        other_community = Community.objects.create(name="Other Town", slug="crqc-other")
        other_admin = User.objects.create_user(username="crqc_other_admin", password="a-real-password-123", community=other_community, role=Role.COMMUNITY_ADMIN)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "crqc_other_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/receipts/contribution-payments/{self.payment.id}/qr-code/")
        self.assertEqual(res.status_code, 404)

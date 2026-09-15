from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants.models import Community
from contribution_rules import services


class FamilyTierRatesTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.random_member = User.objects.create_user(username="rando", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_service_updates_all_five_tiers(self):
        services.update_family_tier_rates(
            community=self.bodi, head_amount=Decimal("300"), senior_amount=Decimal("150"),
            junior_amount=Decimal("75"), woman_amount=Decimal("60"), town_leader_amount=Decimal("120"),
        )
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.default_family_head_amount, Decimal("300"))
        self.assertEqual(self.bodi.default_town_leader_amount, Decimal("120"))

    def test_zero_or_negative_amount_rejected(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            services.update_family_tier_rates(
                community=self.bodi, head_amount=Decimal("0"), senior_amount=Decimal("100"),
                junior_amount=Decimal("50"), woman_amount=Decimal("40"), town_leader_amount=Decimal("100"),
            )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_secretary_can_adjust_family_tier_rates(self):
        client = self._login("secretary")
        res = client.post("/api/contribution-rules/family-tier-rates/", {
            "head_amount": "250", "senior_amount": "120", "junior_amount": "60", "woman_amount": "45", "town_leader_amount": "110",
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["family_tier_rates"]["head_amount"], "250.00")

    def test_ordinary_member_cannot_adjust_family_tier_rates(self):
        client = self._login("rando")
        res = client.post("/api/contribution-rules/family-tier-rates/", {
            "head_amount": "250", "senior_amount": "120", "junior_amount": "60", "woman_amount": "45", "town_leader_amount": "110",
        })
        self.assertEqual(res.status_code, 403)

    def test_list_rules_includes_family_tier_rates(self):
        client = self._login("admin")
        res = client.get("/api/contribution-rules/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("family_tier_rates", res.data)
        self.assertEqual(res.data["family_tier_rates"]["head_amount"], "200.00")


class ChairmanRatePermissionTests(TestCase):
    """'The community chairman and secretary set an amount' — Chairman needs the same rate-setting authority as Secretary."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_chairman_can_adjust_general_rates(self):
        client = self._login("chairman")
        res = client.post("/api/contribution-rules/general-rates/", {"male_amount": "8", "female_amount": "5"})
        self.assertEqual(res.status_code, 200)

    def test_chairman_can_adjust_family_tier_rates(self):
        client = self._login("chairman")
        res = client.post("/api/contribution-rules/family-tier-rates/", {
            "head_amount": "250", "senior_amount": "120", "junior_amount": "60", "woman_amount": "45", "town_leader_amount": "110",
        })
        self.assertEqual(res.status_code, 200)

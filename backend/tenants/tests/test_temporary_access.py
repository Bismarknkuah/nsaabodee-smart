from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import Community


class TemporaryAccessModelTests(TestCase):
    """'Some people can also decide to rent or use the service temporarily.'"""

    def test_a_community_with_no_expiration_is_never_expired(self):
        community = Community.objects.create(name="Permanent Town", slug="permanent-town")
        self.assertFalse(community.is_access_expired)
        self.assertIsNone(community.access_days_remaining)

    def test_a_community_with_a_future_expiration_is_not_yet_expired(self):
        community = Community.objects.create(
            name="Rented Town", slug="rented-town", access_expires_at=timezone.now() + timedelta(days=5),
        )
        self.assertFalse(community.is_access_expired)
        self.assertEqual(community.access_days_remaining, 4)  # partial day rounds down, matches "4 full days left"

    def test_a_community_with_a_past_expiration_is_expired(self):
        community = Community.objects.create(
            name="Lapsed Town", slug="lapsed-town", access_expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(community.is_access_expired)


class TemporaryAccessServiceTests(TestCase):
    def setUp(self):
        self.community = Community.objects.create(name="Test Town", slug="test-town")

    def test_setting_access_expiration(self):
        services.set_community_access_expiration(community=self.community, days_from_now=7)
        self.community.refresh_from_db()
        self.assertFalse(self.community.is_access_expired)
        self.assertEqual(self.community.access_plan, Community.AccessPlan.TIME_LIMITED)

    def test_cannot_set_a_non_positive_expiration(self):
        with self.assertRaises(ValidationError):
            services.set_community_access_expiration(community=self.community, days_from_now=0)

    def test_extending_access_that_is_still_running_adds_onto_the_existing_deadline(self):
        services.set_community_access_expiration(community=self.community, days_from_now=5)
        original_deadline = self.community.access_expires_at
        services.extend_community_access(community=self.community, additional_days=3)
        self.community.refresh_from_db()
        self.assertAlmostEqual(
            (self.community.access_expires_at - original_deadline).total_seconds(), timedelta(days=3).total_seconds(), delta=5,
        )

    def test_extending_access_that_already_lapsed_starts_fresh_from_now(self):
        services.set_community_access_expiration(community=self.community, days_from_now=1)
        self.community.access_expires_at = timezone.now() - timedelta(days=10)  # force it into the past
        self.community.save()
        services.extend_community_access(community=self.community, additional_days=5)
        self.community.refresh_from_db()
        self.assertFalse(self.community.is_access_expired)

    def test_make_permanent_clears_the_deadline_entirely(self):
        services.set_community_access_expiration(community=self.community, days_from_now=5)
        services.make_community_permanent(self.community)
        self.community.refresh_from_db()
        self.assertIsNone(self.community.access_expires_at)
        self.assertEqual(self.community.access_plan, Community.AccessPlan.ONGOING)


class TemporaryAccessEnforcementTests(TestCase):
    """The real enforcement — a login and an already-issued token both have to respect this, not just one of them."""

    def setUp(self):
        self.community = Community.objects.create(name="Rental Town", slug="rental-town")
        self.user = User.objects.create_user(username="rentaluser", password="a-real-password-123", community=self.community, role=Role.COMMUNITY_ADMIN)
        self.super_admin = User.objects.create_superuser(username="superadmin_temp", password="a-real-password-123")

    def _login(self, username="rentaluser"):
        client = APIClient()
        res = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        return client, res

    def test_login_succeeds_normally_before_expiration(self):
        services.set_community_access_expiration(community=self.community, days_from_now=5)
        client, res = self._login()
        self.assertEqual(res.status_code, 200)

    def test_login_is_rejected_once_access_has_expired(self):
        self.community.access_expires_at = timezone.now() - timedelta(days=1)
        self.community.save()
        client, res = self._login()
        self.assertEqual(res.status_code, 401)

    def test_an_already_issued_token_stops_working_the_moment_access_expires(self):
        """The core of the enforcement: a token obtained BEFORE expiration must stop working the instant the deadline passes, not just at its own natural expiry."""
        services.set_community_access_expiration(community=self.community, days_from_now=5)
        client, res = self._login()
        self.assertEqual(res.status_code, 200)
        access_token = res.data["access"]

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        still_working = client.get("/api/auth/me/")
        self.assertEqual(still_working.status_code, 200)

        # Now the community's access lapses — the SAME token must stop working immediately.
        self.community.access_expires_at = timezone.now() - timedelta(seconds=1)
        self.community.save()

        blocked = client.get("/api/auth/me/")
        self.assertEqual(blocked.status_code, 401)

    def test_super_admin_is_never_affected_by_any_communitys_expiration(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "superadmin_temp", "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 200)

    def test_a_permanent_community_never_blocks_login(self):
        client, res = self._login()
        self.assertEqual(res.status_code, 200)


class TemporaryAccessHttpManagementTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_superuser(username="root_temp", password="a-real-password-123")

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "root_temp", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_creating_a_community_with_a_temporary_access_period(self):
        client = self._login()
        res = client.post("/api/tenants/communities/", {
            "community_name": "Single Funeral Test", "admin_username": "single_funeral_admin",
            "admin_password": "a-real-password-123", "access_days": 5, "access_plan": "single_funeral",
            "payout_account_type": "mobile_money", "payout_provider_name": "MTN Mobile Money",
            "payout_account_number": "0244000001", "payout_account_holder_name": "Single Funeral Family",
        })
        self.assertEqual(res.status_code, 201)
        self.assertIsNotNone(res.data["community"]["access_expires_at"])
        self.assertEqual(res.data["community"]["access_plan"], "single_funeral")

    def test_extending_access_via_http(self):
        create_res = self._login().post("/api/tenants/communities/", {
            "community_name": "Extend Test Town", "admin_username": "extend_test_admin",
            "admin_password": "a-real-password-123", "access_days": 2,
            "payout_account_type": "mobile_money", "payout_provider_name": "MTN Mobile Money",
            "payout_account_number": "0244000002", "payout_account_holder_name": "Extend Test Family",
        })
        community_id = create_res.data["community"]["id"]
        client = self._login()
        res = client.post(f"/api/tenants/communities/{community_id}/extend-access/", {"additional_days": 30})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["access_days_remaining"], 31)

    def test_making_a_community_permanent_via_http(self):
        create_res = self._login().post("/api/tenants/communities/", {
            "community_name": "Upgrade Test Town", "admin_username": "upgrade_test_admin",
            "admin_password": "a-real-password-123", "access_days": 5,
            "payout_account_type": "mobile_money", "payout_provider_name": "MTN Mobile Money",
            "payout_account_number": "0244000003", "payout_account_holder_name": "Upgrade Test Family",
        })
        community_id = create_res.data["community"]["id"]
        client = self._login()
        res = client.post(f"/api/tenants/communities/{community_id}/make-permanent/")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["access_expires_at"])

    def test_a_non_platform_admin_cannot_extend_access(self):
        community = Community.objects.create(name="Guarded Town", slug="guarded-town")
        User.objects.create_user(username="ordinary_admin_temp", password="a-real-password-123", community=community, role=Role.COMMUNITY_ADMIN)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "ordinary_admin_temp", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(f"/api/tenants/communities/{community.id}/extend-access/", {"additional_days": 30})
        self.assertEqual(res.status_code, 403)

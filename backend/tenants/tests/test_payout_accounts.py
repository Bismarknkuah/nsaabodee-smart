from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import Community, CommunityPayoutAccount


class PayoutAccountServiceTests(TestCase):
    """'Each registered community should have its own dedicated payment account(s)... configured by the Community Administrator.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.bretuo = Community.objects.create(name="Bretuo Town", slug="bretuo")
        self.bodi_admin = User.objects.create_user(username="bodi_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.bretuo_admin = User.objects.create_user(username="bretuo_admin", password="x", community=self.bretuo, role=Role.COMMUNITY_ADMIN)
        self.bodi_chairman = User.objects.create_user(username="bodi_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

    def test_community_admin_can_add_their_own_communitys_payout_account(self):
        account = services.add_payout_account(
            community=self.bodi, actor=self.bodi_admin, account_type="mobile_money",
            provider_name="MTN Mobile Money", account_number="0244000000", account_holder_name="Bodi Anidasoɔ Welfare",
        )
        self.assertEqual(account.community, self.bodi)

    def test_a_different_communitys_admin_cannot_add_this_communitys_payout_account(self):
        """The whole point: 'the platform must never mix funds between different communities' starts with who can even configure where funds go."""
        with self.assertRaises(ValidationError):
            services.add_payout_account(
                community=self.bodi, actor=self.bretuo_admin, account_type="mobile_money",
                provider_name="MTN", account_number="0244000000", account_holder_name="Wrong Admin",
            )

    def test_chairman_cannot_configure_payout_accounts_even_though_they_can_adjust_contribution_rates(self):
        """Deliberately narrower authority than contribution-rule management — this is 'where does the money go.'"""
        with self.assertRaises(ValidationError):
            services.add_payout_account(
                community=self.bodi, actor=self.bodi_chairman, account_type="bank",
                provider_name="GCB Bank", account_number="123456", account_holder_name="Bodi Anidasoɔ",
            )

    def test_deactivating_a_payout_account(self):
        account = services.add_payout_account(
            community=self.bodi, actor=self.bodi_admin, account_type="bank",
            provider_name="GCB Bank", account_number="123456", account_holder_name="Bodi Anidasoɔ",
        )
        services.deactivate_payout_account(account=account, actor=self.bodi_admin)
        account.refresh_from_db()
        self.assertFalse(account.is_active)

    def test_two_communities_payout_accounts_are_entirely_separate_lists(self):
        services.add_payout_account(community=self.bodi, actor=self.bodi_admin, account_type="mobile_money", provider_name="MTN", account_number="1", account_holder_name="Bodi")
        services.add_payout_account(community=self.bretuo, actor=self.bretuo_admin, account_type="mobile_money", provider_name="MTN", account_number="2", account_holder_name="Bretuo")
        self.assertEqual(len(services.list_payout_accounts(self.bodi)), 1)
        self.assertEqual(len(services.list_payout_accounts(self.bretuo)), 1)
        self.assertNotEqual(services.list_payout_accounts(self.bodi)[0].account_number, services.list_payout_accounts(self.bretuo)[0].account_number)


class TemporaryClientPayoutAccountRequirementTests(TestCase):
    """'During registration, they must provide their preferred payout account... All donations intended for the bereaved family should be transferred directly to the account they provide.'"""

    def setUp(self):
        self.platform_admin = User.objects.create_superuser(username="root_payout", password="x")

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "root_payout", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_a_temporary_registration_without_a_payout_account_is_rejected(self):
        client = self._login()
        res = client.post("/api/tenants/communities/", {
            "community_name": "No Payout Test", "admin_username": "no_payout_admin",
            "admin_password": "a-real-password-123", "access_days": 5,
        })
        self.assertEqual(res.status_code, 400)

    def test_a_temporary_registration_with_a_payout_account_succeeds_and_creates_it(self):
        client = self._login()
        res = client.post("/api/tenants/communities/", {
            "community_name": "Has Payout Test", "admin_username": "has_payout_admin",
            "admin_password": "a-real-password-123", "access_days": 5,
            "payout_account_type": "mobile_money", "payout_provider_name": "MTN Mobile Money",
            "payout_account_number": "0244123456", "payout_account_holder_name": "The Bereaved Family",
        })
        self.assertEqual(res.status_code, 201)
        community_id = res.data["community"]["id"]
        self.assertEqual(CommunityPayoutAccount.objects.filter(community_id=community_id).count(), 1)

    def test_a_permanent_community_does_not_require_a_payout_account_at_registration(self):
        """Configured afterward from its own admin console instead — it isn't tied to one single event."""
        client = self._login()
        res = client.post("/api/tenants/communities/", {
            "community_name": "Permanent No Payout Yet", "admin_username": "permanent_admin_np",
            "admin_password": "a-real-password-123",
        })
        self.assertEqual(res.status_code, 201)

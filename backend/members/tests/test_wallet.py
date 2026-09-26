from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import MemberWallet, WalletTransaction
from tenants.models import Community


class WalletServiceTests(TestCase):
    """'If he doesn't get change, money balance should be credited to the member's wallet.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-wallet",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="wallet_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona)

    def test_credit_wallet_creates_the_wallet_on_first_use(self):
        self.assertFalse(MemberWallet.objects.filter(member=self.member).exists())
        wallet = member_services.credit_wallet(member=self.member, amount=Decimal("50"), actor=self.admin)
        self.assertEqual(wallet.balance, Decimal("50"))
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet, kind="credit").count(), 1)

    def test_credit_accumulates_across_multiple_deposits(self):
        member_services.credit_wallet(member=self.member, amount=Decimal("30"), actor=self.admin)
        wallet = member_services.credit_wallet(member=self.member, amount=Decimal("20"), actor=self.admin)
        self.assertEqual(wallet.balance, Decimal("50"))

    def test_debit_reduces_the_balance(self):
        member_services.credit_wallet(member=self.member, amount=Decimal("50"), actor=self.admin)
        wallet = member_services.debit_wallet(member=self.member, amount=Decimal("20"), actor=self.admin)
        self.assertEqual(wallet.balance, Decimal("30"))

    def test_cannot_debit_more_than_the_balance(self):
        member_services.credit_wallet(member=self.member, amount=Decimal("20"), actor=self.admin)
        with self.assertRaises(ValidationError):
            member_services.debit_wallet(member=self.member, amount=Decimal("50"), actor=self.admin)

    def test_cannot_debit_a_member_with_no_wallet_at_all(self):
        other_member = member_services.register_member(community=self.bodi, full_name="No Wallet", gender="male", family=self.asona)
        with self.assertRaises(ValidationError):
            member_services.debit_wallet(member=other_member, amount=Decimal("10"), actor=self.admin)

    def test_zero_or_negative_amounts_are_rejected(self):
        with self.assertRaises(ValidationError):
            member_services.credit_wallet(member=self.member, amount=Decimal("0"), actor=self.admin)


class OverpaymentWalletIntegrationTests(TestCase):
    """The other half — the actual, real-world moment this credit gets created and spent."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-wallet-integration",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="wallet_int_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Ama Serwaa", gender="female", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            own_family_amount=Decimal("5"),
        )
        from funerals.models import ContributionObligation
        self.owed = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member).expected_amount

    def test_overpayment_with_credit_flag_caps_the_obligation_and_credits_the_wallet(self):
        """Member owes 5, pays with a 50 note, collector has no change — 5 applied, 45 credited."""
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(
            obligation=obligation, amount=Decimal("50"), method="cash",
            collector_name="Collector Kofi", credit_overpayment_to_wallet=True,
        )
        obligation.refresh_from_db()
        self.assertEqual(payment.amount, self.owed)
        self.assertEqual(obligation.amount_paid, self.owed)
        self.assertEqual(obligation.payment_status, "paid")
        self.assertEqual(obligation.overpaid_amount, Decimal("0"))
        self.assertEqual(member_services.get_wallet_balance(self.member), Decimal("50") - self.owed)

    def test_without_the_flag_overpayment_behaves_exactly_as_before(self):
        """Confirms this is opt-in — nothing changes for the existing, already-correct overpaid_amount behavior."""
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(
            obligation=obligation, amount=Decimal("50"), method="cash", collector_name="Collector Kofi",
        )
        obligation.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("50"))
        self.assertEqual(obligation.overpaid_amount, Decimal("50") - self.owed)
        self.assertEqual(member_services.get_wallet_balance(self.member), Decimal("0"))

    def test_exact_payment_with_the_flag_credits_nothing(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(
            obligation=obligation, amount=self.owed, method="cash",
            collector_name="Collector Kofi", credit_overpayment_to_wallet=True,
        )
        self.assertEqual(member_services.get_wallet_balance(self.member), Decimal("0"))

    def test_applying_wallet_credit_settles_a_different_future_obligation(self):
        """The real point of a wallet — usable on a genuinely different obligation, not just this one."""
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(
            obligation=obligation, amount=Decimal("50"), method="cash",
            collector_name="Collector Kofi", credit_overpayment_to_wallet=True,
        )
        wallet_balance = Decimal("50") - self.owed
        self.assertEqual(member_services.get_wallet_balance(self.member), wallet_balance)

        second_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Second Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-08-01", collection_start_date="2026-08-01",
            own_family_amount=Decimal("5"),
        )
        second_obligation = ContributionObligation.objects.get(funeral_event=second_funeral, member=self.member)
        amount_to_apply = min(wallet_balance, second_obligation.expected_amount)
        payment = funeral_services.apply_wallet_to_obligation(obligation=second_obligation, amount=amount_to_apply, actor=self.admin)
        second_obligation.refresh_from_db()
        self.assertEqual(payment.method, "wallet")
        self.assertEqual(member_services.get_wallet_balance(self.member), wallet_balance - amount_to_apply)

    def test_cannot_apply_more_wallet_credit_than_is_owed(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(
            obligation=obligation, amount=Decimal("50"), method="cash",
            collector_name="Collector Kofi", credit_overpayment_to_wallet=True,
        )
        second_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Third Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-08-01", collection_start_date="2026-08-01",
            own_family_amount=Decimal("5"),
        )
        second_obligation = ContributionObligation.objects.get(funeral_event=second_funeral, member=self.member)
        with self.assertRaises(ValidationError):
            funeral_services.apply_wallet_to_obligation(obligation=second_obligation, amount=Decimal("1000"), actor=self.admin)

    def test_wallet_method_cannot_be_selected_directly_via_record_payment(self):
        """'wallet' is reserved for the dedicated apply_wallet_to_obligation flow, not a regular collector-selectable method."""
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        with self.assertRaises(ValidationError):
            funeral_services.record_payment(obligation=obligation, amount=self.owed, method="wallet", collector_name="Someone")

    def test_full_http_round_trip(self):
        User.objects.create_user(username="wallet_http_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "wallet_http_collector", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)

        res = client.post(
            f"/api/funerals/{self.funeral.id}/obligations/{obligation.id}/record-payment/",
            {"amount": "50", "method": "cash", "collector_name": "Test Collector", "credit_overpayment_to_wallet": True},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(res.data["amount"]), self.owed)

        wallet_res = client.get(f"/api/members/{self.member.id}/wallet/")
        self.assertEqual(wallet_res.status_code, 200)
        wallet_balance = Decimal("50") - self.owed
        self.assertEqual(Decimal(wallet_res.data["balance"]), wallet_balance)
        self.assertEqual(len(wallet_res.data["transactions"]), 1)

        second_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="HTTP Second Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-08-01", collection_start_date="2026-08-01",
            own_family_amount=Decimal("5"),
        )
        second_obligation = ContributionObligation.objects.get(funeral_event=second_funeral, member=self.member)
        amount_to_apply = min(wallet_balance, second_obligation.expected_amount)
        apply_res = client.post(
            f"/api/funerals/{second_funeral.id}/obligations/{second_obligation.id}/apply-wallet/",
            {"amount": str(amount_to_apply)},
        )
        self.assertEqual(apply_res.status_code, 201)

        wallet_res_2 = client.get(f"/api/members/{self.member.id}/wallet/")
        self.assertEqual(Decimal(wallet_res_2.data["balance"]), wallet_balance - amount_to_apply)

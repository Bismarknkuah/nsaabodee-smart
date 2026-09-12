from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation, LedgerWallet, LedgerWalletTransaction
from members import services as member_services
from tenants.models import Community


class LedgerWalletRoutingTests(TestCase):
    """
    'Each family should have their wallet being managed by the family
    treasurer... the town elder should also have their wallet as
    well... when a member pays for family contribution the money
    should go to family wallet, when town elder pays for contribution
    it should go to the town elders ledger, and when a member or guest
    pays to community ledger it should go to the community ledger.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="lwr-bodi",
            default_general_male_amount=Decimal("5"), default_town_leader_amount=Decimal("100"),
        )
        self.admin = User.objects.create_user(username="lwr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.outsider = member_services.register_member(community=self.bodi, full_name="Outsider Member", gender="male", family=self.bretuo)
        self.asona_own_member = member_services.register_member(community=self.bodi, full_name="Asona Own Member", gender="male", family=self.asona)
        self.elder = member_services.register_member(community=self.bodi, full_name="Town Elder", gender="male", family=self.bretuo)
        member_services.transfer_to_town_elder(member=self.elder, title="chief", actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _obligation(self, member):
        return ContributionObligation.objects.get(funeral_event=self.funeral, member=member)

    def test_a_general_rate_payment_credits_the_community_wallet(self):
        funeral_services.record_payment(obligation=self._obligation(self.outsider), amount=Decimal("5"), method="cash", collector_name="Collector")
        wallet = LedgerWallet.objects.get(community=self.bodi, scope="general")
        self.assertEqual(wallet.balance, Decimal("5"))

    def test_an_own_family_rate_payment_credits_the_deceaseds_family_wallet(self):
        funeral_services.record_payment(obligation=self._obligation(self.asona_own_member), amount=Decimal("50"), method="cash", collector_name="Collector")
        wallet = LedgerWallet.objects.get(community=self.bodi, scope="own_family", family=self.asona)
        self.assertEqual(wallet.balance, Decimal("50"))

    def test_a_town_elder_rate_payment_credits_the_town_elders_wallet(self):
        funeral_services.record_payment(obligation=self._obligation(self.elder), amount=Decimal("100"), method="cash", collector_name="Collector")
        wallet = LedgerWallet.objects.get(community=self.bodi, scope="town_elder")
        self.assertEqual(wallet.balance, Decimal("100"))
        # Deliberately never tied to a family, even though this elder happens to belong to Bretuo.
        self.assertIsNone(wallet.family_id)

    def test_wallets_for_different_families_are_genuinely_isolated(self):
        """The core cross-family boundary — must never leak, the same principle enforced everywhere else on this platform."""
        bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Own Member", gender="male", family=self.bretuo)
        bretuo_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Bretuo", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("60"),
        )
        funeral_services.record_payment(obligation=self._obligation(self.asona_own_member), amount=Decimal("50"), method="cash", collector_name="Collector")
        bretuo_obligation = ContributionObligation.objects.get(funeral_event=bretuo_funeral, member=bretuo_member)
        funeral_services.record_payment(obligation=bretuo_obligation, amount=Decimal("60"), method="cash", collector_name="Collector")

        asona_wallet = LedgerWallet.objects.get(community=self.bodi, scope="own_family", family=self.asona)
        bretuo_wallet = LedgerWallet.objects.get(community=self.bodi, scope="own_family", family=self.bretuo)
        self.assertEqual(asona_wallet.balance, Decimal("50"))
        self.assertEqual(bretuo_wallet.balance, Decimal("60"))

    def test_multiple_payments_accumulate_correctly_in_the_same_wallet(self):
        second_outsider = member_services.register_member(community=self.bodi, full_name="Second Outsider", gender="male", family=self.bretuo)
        funeral_services.record_payment(obligation=self._obligation(self.outsider), amount=Decimal("5"), method="cash", collector_name="Collector")
        funeral_services.record_payment(obligation=self._obligation(second_outsider), amount=Decimal("5"), method="cash", collector_name="Collector")
        wallet = LedgerWallet.objects.get(community=self.bodi, scope="general")
        self.assertEqual(wallet.balance, Decimal("10"))

    def test_a_credit_transaction_is_traceable_back_to_its_source_payment(self):
        payment = funeral_services.record_payment(obligation=self._obligation(self.outsider), amount=Decimal("5"), method="cash", collector_name="Collector")
        transaction = LedgerWalletTransaction.objects.get(source_payment=payment)
        self.assertEqual(transaction.kind, "credit")
        self.assertEqual(transaction.amount, Decimal("5"))

    def test_the_unique_constraint_means_a_second_call_reuses_the_same_wallet_not_a_duplicate(self):
        wallet1 = funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="general")
        wallet2 = funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="general")
        self.assertEqual(wallet1.id, wallet2.id)
        self.assertEqual(LedgerWallet.objects.filter(community=self.bodi, scope="general").count(), 1)

    def test_overpayment_credited_to_the_members_personal_wallet_is_never_double_counted_in_the_ledger_wallet(self):
        """The excess a member overpays goes to THEIR wallet, not this ledger — the ledger wallet only ever holds what actually settled the obligation."""
        funeral_services.record_payment(
            obligation=self._obligation(self.outsider), amount=Decimal("20"), method="cash",
            collector_name="Collector", credit_overpayment_to_wallet=True,
        )
        community_wallet = LedgerWallet.objects.get(community=self.bodi, scope="general")
        # Only the 5 actually owed settled into the community wallet — the other 15 went to the member's own wallet.
        self.assertEqual(community_wallet.balance, Decimal("5"))


class LedgerWalletWithdrawalTests(TestCase):
    """'Each family should have their wallet being managed by the family treasurer... the town leader should also have their wallet as well.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="lww-bodi", default_general_male_amount=Decimal("5"))
        self.admin = User.objects.create_user(username="lww_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="lww_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.auditor = User.objects.create_user(username="lww_auditor", password="x", community=self.bodi, role=Role.AUDITOR)
        self.chief = User.objects.create_user(username="lww_chief", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.family_treasurer_user = User.objects.create_user(username="lww_ftreasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        from members.models import Member
        self.family_treasurer_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Family Treasurer", gender="male", linked_user=self.family_treasurer_user)

        self.other_family_treasurer_user = User.objects.create_user(username="lww_other_ftreasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Other Family Treasurer", gender="male", linked_user=self.other_family_treasurer_user)

        self.community_wallet = funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="general")
        self.community_wallet.balance = Decimal("100")
        self.community_wallet.save()

        self.family_wallet = funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="own_family", family=self.asona)
        self.family_wallet.balance = Decimal("200")
        self.family_wallet.save()

        self.town_elder_wallet = funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="town_elder")
        self.town_elder_wallet.balance = Decimal("300")
        self.town_elder_wallet.save()

    def test_treasurer_can_withdraw_from_the_community_wallet(self):
        funeral_services.withdraw_from_ledger_wallet(wallet=self.community_wallet, amount=Decimal("30"), note="Printing costs", actor=self.treasurer)
        self.community_wallet.refresh_from_db()
        self.assertEqual(self.community_wallet.balance, Decimal("70"))

    def test_auditor_cannot_withdraw_from_the_community_wallet(self):
        """Review-only, never action-taking — the same principle already established for this role everywhere else."""
        with self.assertRaises(ValidationError):
            funeral_services.withdraw_from_ledger_wallet(wallet=self.community_wallet, amount=Decimal("30"), note="Test", actor=self.auditor)

    def test_family_treasurer_can_withdraw_from_their_own_familys_wallet(self):
        funeral_services.withdraw_from_ledger_wallet(wallet=self.family_wallet, amount=Decimal("50"), note="Family expense", actor=self.family_treasurer_user)
        self.family_wallet.refresh_from_db()
        self.assertEqual(self.family_wallet.balance, Decimal("150"))

    def test_a_different_familys_treasurer_cannot_withdraw(self):
        """The core cross-family boundary — must never leak."""
        with self.assertRaises(ValidationError):
            funeral_services.withdraw_from_ledger_wallet(wallet=self.family_wallet, amount=Decimal("50"), note="Test", actor=self.other_family_treasurer_user)

    def test_the_chief_can_withdraw_from_the_town_elders_wallet(self):
        funeral_services.withdraw_from_ledger_wallet(wallet=self.town_elder_wallet, amount=Decimal("100"), note="Elders' expense", actor=self.chief)
        self.town_elder_wallet.refresh_from_db()
        self.assertEqual(self.town_elder_wallet.balance, Decimal("200"))

    def test_a_withdrawal_can_never_exceed_the_real_balance(self):
        with self.assertRaises(ValidationError):
            funeral_services.withdraw_from_ledger_wallet(wallet=self.community_wallet, amount=Decimal("500"), note="Too much", actor=self.treasurer)

    def test_a_withdrawal_without_a_note_is_rejected(self):
        """'Transparent since it's a transaction aspect' — no silent withdrawals."""
        with self.assertRaises(ValidationError):
            funeral_services.withdraw_from_ledger_wallet(wallet=self.community_wallet, amount=Decimal("10"), note="", actor=self.treasurer)

    def test_a_withdrawal_creates_its_own_auditable_debit_transaction(self):
        funeral_services.withdraw_from_ledger_wallet(wallet=self.community_wallet, amount=Decimal("30"), note="Printing costs", actor=self.treasurer)
        debit = LedgerWalletTransaction.objects.get(wallet=self.community_wallet, kind="debit")
        self.assertEqual(debit.amount, Decimal("30"))
        self.assertEqual(debit.note, "Printing costs")
        self.assertEqual(debit.actor, self.treasurer)


class LedgerWalletAccessScopingTests(TestCase):
    """Viewing and withdrawing are governed by the exact same rule — must never disagree."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="lwa-bodi")
        self.admin = User.objects.create_user(username="lwa_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="lwa_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.chief = User.objects.create_user(username="lwa_chief", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.family_treasurer_user = User.objects.create_user(username="lwa_ftreasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        from members.models import Member
        Member.objects.create(community=self.bodi, family=self.asona, full_name="Family Treasurer", gender="male", linked_user=self.family_treasurer_user)

        funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="general")
        funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="town_elder")
        funeral_services.get_or_create_ledger_wallet(community=self.bodi, scope="own_family", family=self.asona)

    def test_treasurer_sees_only_the_community_wallet(self):
        wallets = funeral_services.ledger_wallets_for(actor=self.treasurer)
        self.assertEqual(list(wallets.values_list("scope", flat=True)), ["general"])

    def test_chief_sees_only_the_town_elders_wallet(self):
        wallets = funeral_services.ledger_wallets_for(actor=self.chief)
        self.assertEqual(list(wallets.values_list("scope", flat=True)), ["town_elder"])

    def test_family_treasurer_sees_only_their_own_familys_wallet(self):
        wallets = funeral_services.ledger_wallets_for(actor=self.family_treasurer_user)
        self.assertEqual(wallets.count(), 1)
        self.assertEqual(wallets.first().family_id, self.asona.id)

    def test_a_plain_community_member_sees_no_wallets_at_all(self):
        plain_user = User.objects.create_user(username="lwa_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        wallets = funeral_services.ledger_wallets_for(actor=plain_user)
        self.assertEqual(wallets.count(), 0)


class LedgerWalletHttpEndpointTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="lwh-bodi", default_general_male_amount=Decimal("5"))
        self.admin = User.objects.create_user(username="lwh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="lwh_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.outsider = member_services.register_member(community=self.bodi, full_name="Outsider", gender="male", family=self.bretuo)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.outsider)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash", collector_name="Collector")

    def _login(self, username):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_list_wallets(self):
        client = self._login("lwh_treasurer")
        res = client.get("/api/ledger-wallets/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["balance"], "5.00")

    def test_full_http_list_transactions(self):
        client = self._login("lwh_treasurer")
        wallet_id = LedgerWallet.objects.get(community=self.bodi, scope="general").id
        res = client.get(f"/api/ledger-wallets/{wallet_id}/transactions/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["kind"], "credit")

    def test_full_http_withdraw(self):
        client = self._login("lwh_treasurer")
        wallet_id = LedgerWallet.objects.get(community=self.bodi, scope="general").id
        res = client.post(f"/api/ledger-wallets/{wallet_id}/withdraw/", {"amount": "2", "note": "Test withdrawal"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["balance"], "3.00")

    def test_a_plain_member_cannot_reach_a_wallet_they_have_no_access_to(self):
        plain_user = User.objects.create_user(username="lwh_plain", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        client = self._login("lwh_plain")
        wallet_id = LedgerWallet.objects.get(community=self.bodi, scope="general").id
        res = client.get(f"/api/ledger-wallets/{wallet_id}/transactions/")
        self.assertEqual(res.status_code, 404)

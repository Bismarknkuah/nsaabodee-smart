from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import AsupedeObligation, AsupedePayment, ContributionObligation, LedgerWallet
from members import services as member_services
from tenants.models import Community


class AsupedeActivationTests(TestCase):
    """
    'Asupedeɛ is different from Family Contribution. Do NOT simply add
    Asupedeɛ to the normal Family Ledger... a family member could have
    Family Contribution = GHS 500 and separately Asupedeɛ = GHS 20.
    Both must be recorded independently.' (funeral-contribution-rules §16)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="aa-bodi", default_general_male_amount=Decimal("5"))
        self.admin = User.objects.create_user(username="aa_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_activating_asupede_creates_a_separate_obligation_alongside_the_ordinary_one(self):
        funeral_services.activate_asupede(funeral=self.funeral, amount=Decimal("20"), actor=self.admin)

        ordinary = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        asupede = AsupedeObligation.objects.get(funeral_event=self.funeral, member=self.member)
        self.assertEqual(ordinary.expected_amount, Decimal("50"))
        self.assertEqual(asupede.expected_amount, Decimal("20"))
        # Genuinely independent records — paying one never touches the other.
        self.assertNotEqual(ordinary.id, asupede.id)

    def test_a_zero_or_negative_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            funeral_services.activate_asupede(funeral=self.funeral, amount=Decimal("0"), actor=self.admin)

    def test_an_invalid_collection_window_is_rejected(self):
        now = timezone.now()
        with self.assertRaises(ValidationError):
            funeral_services.activate_asupede(
                funeral=self.funeral, amount=Decimal("20"),
                collection_start=now, collection_end=now - timedelta(hours=1), actor=self.admin,
            )

    def test_reactivating_never_duplicates_an_existing_members_obligation(self):
        funeral_services.activate_asupede(funeral=self.funeral, amount=Decimal("20"), actor=self.admin)
        funeral_services.activate_asupede(funeral=self.funeral, amount=Decimal("25"), actor=self.admin)
        self.assertEqual(AsupedeObligation.objects.filter(funeral_event=self.funeral, member=self.member).count(), 1)

    def test_a_funeral_that_never_activates_asupede_has_no_obligations_at_all(self):
        self.assertEqual(AsupedeObligation.objects.filter(funeral_event=self.funeral).count(), 0)


class AsupedePaymentTests(TestCase):
    """Minimum-not-cap, no double-payment, and collection-window enforcement — the same rules as the mandatory ledger, plus the one genuinely new one."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ap-bodi")
        self.admin = User.objects.create_user(username="ap_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        funeral_services.activate_asupede(funeral=self.funeral, amount=Decimal("20"), actor=self.admin)
        self.obligation = AsupedeObligation.objects.get(funeral_event=self.funeral, member=self.member)

    def test_paying_the_exact_amount_settles_it(self):
        payment = funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.payment_status, "paid")
        self.assertTrue(payment.receipt_number)

    def test_paying_more_than_required_is_allowed_and_tracked_as_additional_support(self):
        """'Where the community treats the Asupedeɛ amount as a minimum, the contributor may give more.' (§20)"""
        funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("50"), method="cash", collector_name="Collector")
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.overpaid_amount, Decimal("30"))

    def test_a_second_payment_after_already_fully_paid_is_rejected(self):
        funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        with self.assertRaises(ValidationError):
            funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("5"), method="cash", collector_name="Collector")

    def test_a_missing_collector_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="")

    def test_paying_asupede_never_affects_the_members_ordinary_family_obligation(self):
        """The core independence guarantee — the whole reason this is a separate model."""
        funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        ordinary = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        self.assertEqual(ordinary.amount_paid, Decimal("0"))
        self.assertEqual(ordinary.payment_status, "unpaid")

    def test_a_payment_before_the_collection_window_opens_is_rejected(self):
        self.funeral.asupede_collection_start = timezone.now() + timedelta(hours=1)
        self.funeral.asupede_collection_end = timezone.now() + timedelta(hours=5)
        self.funeral.save(update_fields=["asupede_collection_start", "asupede_collection_end"])
        with self.assertRaises(ValidationError):
            funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")

    def test_a_payment_after_the_collection_window_closes_is_rejected(self):
        self.funeral.asupede_collection_start = timezone.now() - timedelta(hours=5)
        self.funeral.asupede_collection_end = timezone.now() - timedelta(hours=1)
        self.funeral.save(update_fields=["asupede_collection_start", "asupede_collection_end"])
        with self.assertRaises(ValidationError):
            funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")

    def test_a_payment_inside_the_collection_window_succeeds(self):
        self.funeral.asupede_collection_start = timezone.now() - timedelta(hours=1)
        self.funeral.asupede_collection_end = timezone.now() + timedelta(hours=1)
        self.funeral.save(update_fields=["asupede_collection_start", "asupede_collection_end"])
        payment = funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        self.assertIsNotNone(payment)

    def test_no_collection_window_configured_means_payable_any_time(self):
        """Leaving both blank means no window restriction at all — never an invented default."""
        self.assertIsNone(self.funeral.asupede_collection_start)
        self.assertIsNone(self.funeral.asupede_collection_end)
        payment = funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        self.assertIsNotNone(payment)

    def test_a_genuine_idempotent_retry_still_succeeds(self):
        import uuid
        op_id = uuid.uuid4()
        p1 = funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector", client_op_id=op_id)
        p2 = funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector", client_op_id=op_id)
        self.assertEqual(p1.id, p2.id)


class AsupedeLedgerWalletRoutingTests(TestCase):
    """A payment credits its own, distinct Asupedeɛ wallet — never folded into the family's ordinary mandatory-contribution wallet."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="alw-bodi")
        self.admin = User.objects.create_user(username="alw_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        funeral_services.activate_asupede(funeral=self.funeral, amount=Decimal("20"), actor=self.admin)
        self.obligation = AsupedeObligation.objects.get(funeral_event=self.funeral, member=self.member)

    def test_an_asupede_payment_credits_its_own_distinct_wallet(self):
        funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        asupede_wallet = LedgerWallet.objects.get(community=self.bodi, scope="asupede", family=self.asona)
        self.assertEqual(asupede_wallet.balance, Decimal("20"))

    def test_the_ordinary_family_wallet_is_never_touched_by_an_asupede_payment(self):
        funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        self.assertFalse(LedgerWallet.objects.filter(community=self.bodi, scope="own_family", family=self.asona).exists())

    def test_a_family_treasurer_can_see_both_their_family_wallet_and_their_asupede_wallet(self):
        treasurer_user = User.objects.create_user(username="alw_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        from members.models import Member
        Member.objects.create(community=self.bodi, family=self.asona, full_name="The Treasurer", gender="male", linked_user=treasurer_user)
        funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        # Also settle the ordinary obligation so both wallet types genuinely exist to compare.
        ordinary = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=ordinary, amount=Decimal("50"), method="cash", collector_name="Collector")

        wallets = funeral_services.ledger_wallets_for(actor=treasurer_user)
        scopes = {w.scope for w in wallets}
        self.assertEqual(scopes, {"own_family", "asupede"})

    def test_a_different_familys_treasurer_cannot_withdraw_from_this_asupede_wallet(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        outside_treasurer = User.objects.create_user(username="alw_outside", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        from members.models import Member
        Member.objects.create(community=self.bodi, family=bretuo, full_name="Outside Treasurer", gender="male", linked_user=outside_treasurer)

        funeral_services.record_asupede_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector_name="Collector")
        asupede_wallet = LedgerWallet.objects.get(community=self.bodi, scope="asupede", family=self.asona)
        with self.assertRaises(ValidationError):
            funeral_services.withdraw_from_ledger_wallet(wallet=asupede_wallet, amount=Decimal("10"), note="Test", actor=outside_treasurer)


class AsupedeHttpEndpointTests(TestCase):
    """The full HTTP round trip — nothing here was reachable outside a Django shell before this."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ahe-bodi")
        self.admin = User.objects.create_user(username="ahe_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member_user = User.objects.create_user(username="ahe_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        from members.models import Member
        self.member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Test Member", gender="male", linked_user=self.member_user)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _login(self, username):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_activation_and_payment_round_trip(self):
        admin_client = self._login("ahe_admin")
        activate_res = admin_client.post(f"/api/funerals/{self.funeral.id}/asupede/activate/", {"amount": "20"}, format="json")
        self.assertEqual(activate_res.status_code, 201, activate_res.data)

        obligations_res = admin_client.get(f"/api/funerals/{self.funeral.id}/asupede/obligations/")
        self.assertEqual(obligations_res.status_code, 200)
        member_obligation = next(o for o in obligations_res.data if str(o["member"]) == str(self.member.id))
        self.assertEqual(member_obligation["expected_amount"], "20.00")

        # 'Payment_collecting_roles' is genuinely just Collector — not
        # Community Admin — matching this platform's own, existing
        # authorization model for recording any payment.
        User.objects.create_user(username="ahe_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        collector_client = self._login("ahe_collector")
        pay_res = collector_client.post(
            f"/api/funerals/{self.funeral.id}/asupede-obligations/{member_obligation['id']}/record-payment/",
            {"amount": "20", "method": "cash", "collector_name": "Collector"}, format="json",
        )
        self.assertEqual(pay_res.status_code, 201, pay_res.data)

        summary_res = admin_client.get(f"/api/funerals/{self.funeral.id}/asupede/summary/")
        self.assertEqual(summary_res.status_code, 200)
        self.assertEqual(summary_res.data["collected_total"], "20")

    def test_a_member_can_pay_their_own_asupede_obligation(self):
        admin_client = self._login("ahe_admin")
        admin_client.post(f"/api/funerals/{self.funeral.id}/asupede/activate/", {"amount": "20"}, format="json")
        obligations_res = admin_client.get(f"/api/funerals/{self.funeral.id}/asupede/obligations/")
        member_obligation = next(o for o in obligations_res.data if str(o["member"]) == str(self.member.id))

        member_client = self._login("ahe_member")
        pay_res = member_client.post(
            f"/api/funerals/{self.funeral.id}/asupede-obligations/{member_obligation['id']}/record-payment/",
            {"amount": "20", "method": "cash", "collector_name": "Self"}, format="json",
        )
        self.assertEqual(pay_res.status_code, 201, pay_res.data)

    def test_a_non_executive_non_owner_cannot_pay_someone_elses_asupede_obligation(self):
        outsider_user = User.objects.create_user(username="ahe_outsider", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        from members.models import Member
        Member.objects.create(community=self.bodi, family=self.asona, full_name="Outsider", gender="male", linked_user=outsider_user)

        admin_client = self._login("ahe_admin")
        admin_client.post(f"/api/funerals/{self.funeral.id}/asupede/activate/", {"amount": "20"}, format="json")
        obligations_res = admin_client.get(f"/api/funerals/{self.funeral.id}/asupede/obligations/")
        member_obligation = next(o for o in obligations_res.data if str(o["member"]) == str(self.member.id))

        outsider_client = self._login("ahe_outsider")
        pay_res = outsider_client.post(
            f"/api/funerals/{self.funeral.id}/asupede-obligations/{member_obligation['id']}/record-payment/",
            {"amount": "20", "method": "cash", "collector_name": "Outsider"}, format="json",
        )
        self.assertEqual(pay_res.status_code, 403)

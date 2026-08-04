from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services
from funerals.models import ContributionObligation, ContributionPayment, PaymentReversal
from tenants.models import Community


class PaymentReversalServiceTests(TestCase):
    """
    'If a payment is mistakenly recorded against the wrong member, wrong
    funeral event, wrong family, or incorrect amount, an authorized
    administrator should be able to initiate a reversal or correction...
    Every reversal must be logged with the reason, the user who
    performed it, the original transaction reference, the date, and the
    approval history.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.other_community = Community.objects.create(name="Other Town", slug="other-town")

        self.admin = User.objects.create_user(username="reversal_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="reversal_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.treasurer = User.objects.create_user(username="reversal_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.collector = User.objects.create_user(username="reversal_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.other_admin = User.objects.create_user(username="other_town_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        from members.models import Member
        self.member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Kojo", gender="male")

        self.funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        self.payment = services.record_payment(obligation=self.obligation, amount=Decimal("20"), method="cash", collector=self.collector)

    def test_treasurer_can_request_a_reversal(self):
        reversal = services.request_payment_reversal(payment=self.payment, reason="Wrong amount — should have been GHS 15", actor=self.treasurer)
        self.assertEqual(reversal.status, PaymentReversal.Status.PENDING)
        self.assertEqual(reversal.requested_by, self.treasurer)

    def test_a_collector_cannot_request_a_reversal(self):
        """Recording payments and reversing them are different authorities on purpose."""
        with self.assertRaises(ValidationError):
            services.request_payment_reversal(payment=self.payment, reason="Mistake", actor=self.collector)

    def test_a_reason_is_required(self):
        with self.assertRaises(ValidationError):
            services.request_payment_reversal(payment=self.payment, reason="   ", actor=self.treasurer)

    def test_cannot_request_a_second_pending_reversal_for_the_same_payment(self):
        services.request_payment_reversal(payment=self.payment, reason="First request", actor=self.treasurer)
        with self.assertRaises(ValidationError):
            services.request_payment_reversal(payment=self.payment, reason="Second request", actor=self.secretary)

    def test_approving_a_reversal_actually_corrects_the_obligations_running_total(self):
        self.obligation.refresh_from_db()
        before = self.obligation.amount_paid
        reversal = services.request_payment_reversal(payment=self.payment, reason="Wrong member", actor=self.treasurer)
        services.approve_payment_reversal(reversal=reversal, actor=self.secretary)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.amount_paid, before - self.payment.amount)

    def test_approving_a_reversal_never_deletes_or_mutates_the_original_payment(self):
        """The audit trail stays whole — the original row is untouched, only the obligation's running total changes."""
        original_amount = self.payment.amount
        original_receipt = self.payment.receipt_number
        reversal = services.request_payment_reversal(payment=self.payment, reason="Wrong amount", actor=self.treasurer)
        services.approve_payment_reversal(reversal=reversal, actor=self.secretary)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.amount, original_amount)
        self.assertEqual(self.payment.receipt_number, original_receipt)
        self.assertTrue(ContributionPayment.objects.filter(id=self.payment.id).exists())

    def test_the_same_person_cannot_request_and_approve_their_own_reversal(self):
        reversal = services.request_payment_reversal(payment=self.payment, reason="Mistake", actor=self.secretary)
        with self.assertRaises(ValidationError):
            services.approve_payment_reversal(reversal=reversal, actor=self.secretary)

    def test_a_collector_cannot_approve_a_reversal_even_though_they_could_have_requested_nothing(self):
        reversal = services.request_payment_reversal(payment=self.payment, reason="Mistake", actor=self.treasurer)
        with self.assertRaises(ValidationError):
            services.approve_payment_reversal(reversal=reversal, actor=self.collector)

    def test_rejecting_a_reversal_leaves_the_obligation_untouched(self):
        self.obligation.refresh_from_db()
        before = self.obligation.amount_paid
        reversal = services.request_payment_reversal(payment=self.payment, reason="Mistake", actor=self.treasurer)
        services.reject_payment_reversal(reversal=reversal, actor=self.secretary, notes="Payment was actually correct")
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.amount_paid, before)
        reversal.refresh_from_db()
        self.assertEqual(reversal.status, PaymentReversal.Status.REJECTED)

    def test_an_already_decided_reversal_cannot_be_decided_again(self):
        reversal = services.request_payment_reversal(payment=self.payment, reason="Mistake", actor=self.treasurer)
        services.approve_payment_reversal(reversal=reversal, actor=self.secretary)
        with self.assertRaises(ValidationError):
            services.approve_payment_reversal(reversal=reversal, actor=self.admin)

    def test_cannot_reverse_a_payment_that_was_already_successfully_reversed(self):
        reversal = services.request_payment_reversal(payment=self.payment, reason="First", actor=self.treasurer)
        services.approve_payment_reversal(reversal=reversal, actor=self.secretary)
        with self.assertRaises(ValidationError):
            services.request_payment_reversal(payment=self.payment, reason="Second attempt", actor=self.treasurer)

    def test_listing_reversal_requests_is_scoped_to_ones_own_community(self):
        services.request_payment_reversal(payment=self.payment, reason="Mistake", actor=self.treasurer)
        bodi_list = services.list_reversal_requests(community=self.bodi, actor=self.admin)
        self.assertEqual(len(bodi_list), 1)
        other_list = services.list_reversal_requests(community=self.other_community, actor=self.other_admin)
        self.assertEqual(len(other_list), 0)

    def test_only_authorized_roles_can_list_reversal_requests(self):
        collector_only = User.objects.create_user(username="pure_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        with self.assertRaises(ValidationError):
            services.list_reversal_requests(community=self.bodi, actor=collector_only)


class PaymentReversalHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-http",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="http_reversal_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="http_reversal_secretary", password="a-real-password-123", community=self.bodi, role=Role.SECRETARY)
        self.treasurer = User.objects.create_user(username="http_reversal_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        from members.models import Member
        self.member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Kojo", gender="male")
        self.funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        self.payment = services.record_payment(obligation=obligation, amount=Decimal("20"), method="cash")

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_request_then_approve_flow_via_http(self):
        treasurer_client = self._login("http_reversal_treasurer")
        request_res = treasurer_client.post(f"/api/payments/{self.payment.id}/request-reversal/", {"reason": "Wrong member entirely"})
        self.assertEqual(request_res.status_code, 201)
        reversal_id = request_res.data["id"]

        secretary_client = self._login("http_reversal_secretary")
        approve_res = secretary_client.post(f"/api/payment-reversals/{reversal_id}/approve/", {"notes": "Confirmed with the family"})
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.data["status"], "approved")

    def test_listing_reversals_via_http(self):
        treasurer_client = self._login("http_reversal_treasurer")
        treasurer_client.post(f"/api/payments/{self.payment.id}/request-reversal/", {"reason": "Mistake"})
        admin_client = self._login("http_reversal_admin")
        res = admin_client.get("/api/payment-reversals/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["payment_receipt_number"], self.payment.receipt_number)

    def test_a_different_communitys_admin_cannot_reach_this_payment_at_all(self):
        other_community = Community.objects.create(name="Far Away Town", slug="far-away")
        outsider = User.objects.create_user(username="far_away_admin", password="a-real-password-123", community=other_community, role=Role.TREASURER)
        client = self._login("far_away_admin")
        res = client.post(f"/api/payments/{self.payment.id}/request-reversal/", {"reason": "Trying to reach across communities"})
        self.assertEqual(res.status_code, 404)

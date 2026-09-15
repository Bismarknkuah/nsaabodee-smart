from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import InLawContributionRequest, InLawObligation
from members import services as member_services
from tenants.models import Community


class InLawContributionRequestTests(TestCase):
    """
    'Do NOT automatically create a financial obligation solely
    because a relationship exists... only after approval should the
    system generate the actual financial obligation.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ilc-bodi")
        self.admin = User.objects.create_user(username="ilc_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_user = User.objects.create_user(username="ilc_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        self.head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        self.head_member.linked_user = self.head_user
        self.head_member.save(update_fields=["linked_user"])
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_the_deceased_familys_head_can_request_an_in_law_contribution(self):
        request = funeral_services.request_in_law_contribution(
            funeral=self.funeral, in_law_family=self.bretuo, relationship="Kwame's wife's family",
            requested_amount=Decimal("300"), reason="Close in-law connection", actor=self.head_user,
        )
        self.assertEqual(request.status, "pending")
        self.assertEqual(request.in_law_family, self.bretuo)

    def test_requesting_from_the_deceaseds_own_family_is_rejected(self):
        with self.assertRaises(ValidationError):
            funeral_services.request_in_law_contribution(
                funeral=self.funeral, in_law_family=self.asona, relationship="Self",
                requested_amount=Decimal("300"), actor=self.head_user,
            )

    def test_a_plain_community_member_cannot_request_an_in_law_contribution(self):
        plain_user = User.objects.create_user(username="ilc_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            funeral_services.request_in_law_contribution(
                funeral=self.funeral, in_law_family=self.bretuo, relationship="Some relation",
                requested_amount=Decimal("300"), actor=plain_user,
            )

    def test_a_different_familys_head_cannot_request_on_behalf_of_a_funeral_not_their_own(self):
        other_head_user = User.objects.create_user(username="ilc_other_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        other_member = member_services.register_member(community=self.bodi, full_name="Other Head", gender="male", family=self.bretuo)
        other_member.linked_user = other_head_user
        other_member.save(update_fields=["linked_user"])
        family_services.assign_family_head(family=self.bretuo, member=other_member, actor=self.admin)

        with self.assertRaises(ValidationError):
            funeral_services.request_in_law_contribution(
                funeral=self.funeral, in_law_family=self.bretuo, relationship="Some relation",
                requested_amount=Decimal("300"), actor=other_head_user,
            )

    def test_a_zero_amount_request_is_rejected(self):
        with self.assertRaises(ValidationError):
            funeral_services.request_in_law_contribution(
                funeral=self.funeral, in_law_family=self.bretuo, relationship="Some relation",
                requested_amount=Decimal("0"), actor=self.head_user,
            )

    def test_no_obligation_exists_until_the_request_is_actually_approved(self):
        request = funeral_services.request_in_law_contribution(
            funeral=self.funeral, in_law_family=self.bretuo, relationship="Some relation",
            requested_amount=Decimal("300"), actor=self.head_user,
        )
        self.assertFalse(InLawObligation.objects.filter(request=request).exists())


class InLawContributionApprovalTests(TestCase):
    """'The request should go through the configured approval process.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ilca-bodi")
        self.admin = User.objects.create_user(username="ilca_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="ilca_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.request = funeral_services.request_in_law_contribution(
            funeral=self.funeral, in_law_family=self.bretuo, relationship="Kwame's wife's family",
            requested_amount=Decimal("300"), actor=self.admin,
        )

    def test_approving_creates_the_actual_obligation_with_the_requested_amount(self):
        funeral_services.decide_in_law_contribution_request(request=self.request, actor=self.chairman, decision="approve")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "approved")
        obligation = InLawObligation.objects.get(request=self.request)
        self.assertEqual(obligation.expected_amount, Decimal("300"))
        self.assertEqual(obligation.in_law_family, self.bretuo)

    def test_rejecting_creates_no_obligation_at_all(self):
        funeral_services.decide_in_law_contribution_request(request=self.request, actor=self.chairman, decision="reject")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "rejected")
        self.assertFalse(InLawObligation.objects.filter(request=self.request).exists())

    def test_a_family_head_cannot_approve_their_own_requests(self):
        """'Approving your own request would defeat the point of a separate approval step entirely.'"""
        head_user = User.objects.create_user(username="ilca_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        with self.assertRaises(ValidationError):
            funeral_services.decide_in_law_contribution_request(request=self.request, actor=head_user, decision="approve")

    def test_deciding_an_already_decided_request_is_rejected(self):
        funeral_services.decide_in_law_contribution_request(request=self.request, actor=self.chairman, decision="approve")
        with self.assertRaises(ValidationError):
            funeral_services.decide_in_law_contribution_request(request=self.request, actor=self.chairman, decision="reject")


class InLawPaymentTests(TestCase):
    """Same minimum-not-cap, required-collector-name, no-double-payment rules as every other ledger."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ilp-bodi")
        self.admin = User.objects.create_user(username="ilp_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="ilp_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)
        self.asona_member = member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        request = funeral_services.request_in_law_contribution(
            funeral=self.funeral, in_law_family=self.bretuo, relationship="Kwame's wife's family",
            requested_amount=Decimal("300"), actor=self.admin,
        )
        funeral_services.decide_in_law_contribution_request(request=request, actor=self.chairman, decision="approve")
        self.obligation = InLawObligation.objects.get(request=request)

    def test_a_member_of_the_in_law_family_can_pay_on_their_familys_behalf(self):
        payment = funeral_services.record_in_law_payment(
            obligation=self.obligation, amount=Decimal("300"), method="cash",
            collector_name="Collector", paid_by_member=self.bretuo_member,
        )
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.payment_status, "paid")
        self.assertTrue(payment.receipt_number)

    def test_a_member_of_a_different_family_cannot_be_recorded_as_the_payer(self):
        """The in-law obligation belongs to a specific family — paid_by_member must actually be one of them."""
        with self.assertRaises(ValidationError):
            funeral_services.record_in_law_payment(
                obligation=self.obligation, amount=Decimal("300"), method="cash",
                collector_name="Collector", paid_by_member=self.asona_member,
            )

    def test_paying_more_than_requested_is_allowed(self):
        funeral_services.record_in_law_payment(obligation=self.obligation, amount=Decimal("400"), method="cash", collector_name="Collector")
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.overpaid_amount, Decimal("100"))

    def test_a_second_payment_after_already_fully_paid_is_rejected(self):
        funeral_services.record_in_law_payment(obligation=self.obligation, amount=Decimal("300"), method="cash", collector_name="Collector")
        with self.assertRaises(ValidationError):
            funeral_services.record_in_law_payment(obligation=self.obligation, amount=Decimal("50"), method="cash", collector_name="Collector")

    def test_a_missing_collector_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            funeral_services.record_in_law_payment(obligation=self.obligation, amount=Decimal("300"), method="cash", collector_name="")


class InLawContributionHttpEndpointTests(TestCase):
    """The full HTTP round trip — nothing here was reachable outside a Django shell before this."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ilhe-bodi")
        self.admin = User.objects.create_user(username="ilhe_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="ilhe_chairman", password="a-real-password-123", community=self.bodi, role=Role.CHAIRMAN)
        self.collector = User.objects.create_user(username="ilhe_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        self.plain_member = User.objects.create_user(username="ilhe_plain", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
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

    def test_full_http_request_approve_and_pay_round_trip(self):
        admin_client = self._login("ilhe_admin")
        request_res = admin_client.post(
            f"/api/funerals/{self.funeral.id}/in-law-requests/",
            {"in_law_family_id": str(self.bretuo.id), "relationship": "Kwame's wife's family", "requested_amount": "300"}, format="json",
        )
        self.assertEqual(request_res.status_code, 201, request_res.data)

        list_res = admin_client.get(f"/api/funerals/{self.funeral.id}/in-law-requests/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.data), 1)

        chairman_client = self._login("ilhe_chairman")
        decide_res = chairman_client.post(
            f"/api/funerals/{self.funeral.id}/in-law-requests/{request_res.data['id']}/decide/", {"decision": "approve"}, format="json",
        )
        self.assertEqual(decide_res.status_code, 200, decide_res.data)
        self.assertEqual(decide_res.data["status"], "approved")

        from funerals.models import InLawObligation
        obligation = InLawObligation.objects.get(request_id=request_res.data["id"])

        collector_client = self._login("ilhe_collector")
        pay_res = collector_client.post(
            f"/api/funerals/{self.funeral.id}/in-law-obligations/{obligation.id}/record-payment/",
            {"amount": "300", "method": "cash", "collector_name": "Collector"}, format="json",
        )
        self.assertEqual(pay_res.status_code, 201, pay_res.data)

    def test_a_plain_member_cannot_request_an_in_law_contribution_over_http(self):
        res = self._login("ilhe_plain").post(
            f"/api/funerals/{self.funeral.id}/in-law-requests/",
            {"in_law_family_id": str(self.bretuo.id), "relationship": "test", "requested_amount": "300"}, format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_a_non_collector_cannot_record_the_in_law_payment_over_http(self):
        admin_client = self._login("ilhe_admin")
        request_res = admin_client.post(
            f"/api/funerals/{self.funeral.id}/in-law-requests/",
            {"in_law_family_id": str(self.bretuo.id), "relationship": "test", "requested_amount": "300"}, format="json",
        )
        chairman_client = self._login("ilhe_chairman")
        chairman_client.post(f"/api/funerals/{self.funeral.id}/in-law-requests/{request_res.data['id']}/decide/", {"decision": "approve"}, format="json")

        from funerals.models import InLawObligation
        obligation = InLawObligation.objects.get(request_id=request_res.data["id"])

        plain_client = self._login("ilhe_plain")
        pay_res = plain_client.post(
            f"/api/funerals/{self.funeral.id}/in-law-obligations/{obligation.id}/record-payment/",
            {"amount": "300", "method": "cash", "collector_name": "Plain"}, format="json",
        )
        self.assertEqual(pay_res.status_code, 403)


class InLawRequestSerializerObligationFieldTests(TestCase):
    """The nested `obligation` field on the request serializer, added so the frontend can discover the obligation to pay against without a separate lookup endpoint."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="irsof-bodi")
        self.admin = User.objects.create_user(username="irsof_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="irsof_chairman", password="a-real-password-123", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_a_pending_requests_obligation_field_is_null_over_http(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "irsof_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/funerals/{self.funeral.id}/in-law-requests/",
            {"in_law_family_id": str(self.bretuo.id), "relationship": "test", "requested_amount": "300"}, format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data["obligation"])

    def test_an_approved_requests_obligation_field_is_populated_with_its_own_id_over_http(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "irsof_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        request_res = client.post(
            f"/api/funerals/{self.funeral.id}/in-law-requests/",
            {"in_law_family_id": str(self.bretuo.id), "relationship": "test", "requested_amount": "300"}, format="json",
        )
        chairman_client = APIClient()
        chairman_login = chairman_client.post("/api/auth/login/", {"username": "irsof_chairman", "password": "a-real-password-123"})
        chairman_client.credentials(HTTP_AUTHORIZATION=f"Bearer {chairman_login.data['access']}")
        decide_res = chairman_client.post(f"/api/funerals/{self.funeral.id}/in-law-requests/{request_res.data['id']}/decide/", {"decision": "approve"}, format="json")

        self.assertIsNotNone(decide_res.data["obligation"])
        self.assertIn("id", decide_res.data["obligation"])
        self.assertEqual(decide_res.data["obligation"]["expected_amount"], "300.00")

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services
from welfare.models import ContributionCategory, WelfareRequest


class WelfareRequestSubmissionTests(TestCase):
    """
    'The system should support welfare requests separately from
    contributions... the request can be linked to Family Welfare
    Fund or Community Welfare Fund depending on the scope.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="wrs-bodi")
        self.admin = User.objects.create_user(username="wrs_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.member_a = member_services.register_member(community=self.bodi, full_name="Member A", gender="male", family=self.asona)
        self.member_b = member_services.register_member(community=self.bodi, full_name="Member B", gender="male", family=self.bretuo)

        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Medical Welfare", fixed_amount=Decimal("100"), actor=self.admin)
        # Use a community-wide campaign for most tests — simpler setup, same request/decide/disburse logic.
        self.community_fund = welfare_services.initiate_community_campaign(category=self.category, title="Community Medical Fund", amount=Decimal("100"), actor=self.admin)

    def test_a_member_can_submit_a_request_against_a_community_fund(self):
        request = welfare_services.submit_welfare_request(
            campaign=self.community_fund, requester=self.member_a, amount_requested=Decimal("300"), reason="Medical emergency",
        )
        self.assertEqual(request.status, "pending")

    def test_a_request_needs_a_real_reason(self):
        with self.assertRaises(ValidationError):
            welfare_services.submit_welfare_request(campaign=self.community_fund, requester=self.member_a, amount_requested=Decimal("300"), reason="")

    def test_a_zero_amount_request_is_rejected(self):
        with self.assertRaises(ValidationError):
            welfare_services.submit_welfare_request(campaign=self.community_fund, requester=self.member_a, amount_requested=Decimal("0"), reason="test")

    def test_a_family_scoped_funds_request_rejects_a_requester_from_a_different_family(self):
        family_a_only_category = welfare_services.create_contribution_category(community=self.bodi, name="Family Only", fixed_amount=Decimal("100"), actor=self.admin)
        head_a_user = User.objects.create_user(username="wrs_head_a", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.member_a, user=head_a_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.member_a, actor=self.admin)
        family_campaign = welfare_services.initiate_family_campaign(category=family_a_only_category, family=self.asona, title="Family A Welfare", amount=Decimal("100"), actor=head_a_user)
        with self.assertRaises(ValidationError):
            welfare_services.submit_welfare_request(campaign=family_campaign, requester=self.member_b, amount_requested=Decimal("50"), reason="test")

    def test_the_existence_of_a_request_never_implies_money_was_disbursed(self):
        """'The existence of the request does not automatically mean money has been disbursed.'"""
        request = welfare_services.submit_welfare_request(campaign=self.community_fund, requester=self.member_a, amount_requested=Decimal("300"), reason="Medical emergency")
        self.assertIsNone(request.amount_disbursed)
        self.assertIsNone(request.disbursed_at)


class WelfareRequestApprovalAndDisbursementTests(TestCase):
    """'Collection -> Verification -> Approval -> Disbursement -> Recipient acknowledgement -> Audit.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="wrad-bodi")
        self.admin = User.objects.create_user(username="wrad_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Member A", gender="male", family=self.asona)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Medical Welfare", fixed_amount=Decimal("100"), actor=self.admin)
        self.fund = welfare_services.initiate_community_campaign(category=self.category, title="Community Medical Fund", amount=Decimal("100"), actor=self.admin)
        self.request = welfare_services.submit_welfare_request(campaign=self.fund, requester=self.member, amount_requested=Decimal("300"), reason="Medical emergency")

    def test_approving_sets_status_and_approved_amount(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "approved")
        self.assertEqual(self.request.amount_approved, Decimal("300"))

    def test_approving_a_lower_amount_than_requested_is_allowed(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True, amount_approved=Decimal("200"))
        self.request.refresh_from_db()
        self.assertEqual(self.request.amount_approved, Decimal("200"))

    def test_approving_more_than_requested_is_rejected(self):
        with self.assertRaises(ValidationError):
            welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True, amount_approved=Decimal("500"))

    def test_rejecting_requires_a_reason(self):
        with self.assertRaises(ValidationError):
            welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=False, rejection_reason="")

    def test_rejecting_never_creates_a_disbursement(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=False, rejection_reason="Insufficient funds")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "rejected")
        self.assertIsNone(self.request.amount_disbursed)

    def test_deciding_an_already_decided_request_is_rejected(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True)
        with self.assertRaises(ValidationError):
            welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True)

    def test_a_plain_member_cannot_approve_a_request(self):
        plain_user = User.objects.create_user(username="wrad_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            welfare_services.decide_welfare_request(request=self.request, actor=plain_user, approve=True)

    def test_disbursement_requires_prior_approval(self):
        with self.assertRaises(ValidationError):
            welfare_services.disburse_welfare_request(request=self.request, actor=self.admin)

    def test_disbursement_after_approval_succeeds(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True, amount_approved=Decimal("250"))
        welfare_services.disburse_welfare_request(request=self.request, actor=self.admin)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "disbursed")
        self.assertEqual(self.request.amount_disbursed, Decimal("250"))

    def test_disbursing_more_than_approved_is_rejected(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True, amount_approved=Decimal("250"))
        with self.assertRaises(ValidationError):
            welfare_services.disburse_welfare_request(request=self.request, actor=self.admin, amount=Decimal("300"))

    def test_recipient_can_acknowledge_after_disbursement(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True)
        welfare_services.disburse_welfare_request(request=self.request, actor=self.admin)
        member_user = User.objects.create_user(username="wrad_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=member_user, actor=self.admin)
        welfare_services.acknowledge_welfare_disbursement(request=self.request, actor=member_user)
        self.request.refresh_from_db()
        self.assertIsNotNone(self.request.acknowledged_at)

    def test_acknowledging_before_disbursement_is_rejected(self):
        member_user = User.objects.create_user(username="wrad_member2", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=member_user, actor=self.admin)
        with self.assertRaises(ValidationError):
            welfare_services.acknowledge_welfare_disbursement(request=self.request, actor=member_user)

    def test_someone_other_than_the_requester_cannot_acknowledge_on_their_behalf(self):
        welfare_services.decide_welfare_request(request=self.request, actor=self.admin, approve=True)
        welfare_services.disburse_welfare_request(request=self.request, actor=self.admin)
        other_user = User.objects.create_user(username="wrad_other", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        other_member = member_services.register_member(community=self.bodi, full_name="Other", gender="male", family=self.asona)
        member_services.link_member_to_user(member=other_member, user=other_user, actor=self.admin)
        with self.assertRaises(ValidationError):
            welfare_services.acknowledge_welfare_disbursement(request=self.request, actor=other_user)


class WelfareRequestVisibilityTests(TestCase):
    """Same isolation principle as obligations — a request is only visible to its own requester or authorized fund administrators."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="wrv-bodi")
        self.admin = User.objects.create_user(username="wrv_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member_a = member_services.register_member(community=self.bodi, full_name="Member A", gender="male", family=self.asona)
        self.member_c = member_services.register_member(community=self.bodi, full_name="Member C", gender="male", family=self.asona)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Medical Welfare", fixed_amount=Decimal("100"), actor=self.admin)
        self.fund = welfare_services.initiate_community_campaign(category=self.category, title="Community Medical Fund", amount=Decimal("100"), actor=self.admin)
        self.request_a = welfare_services.submit_welfare_request(campaign=self.fund, requester=self.member_a, amount_requested=Decimal("100"), reason="test")

    def test_community_admin_sees_every_request(self):
        results = welfare_services.list_welfare_requests_for(campaign=self.fund, actor=self.admin)
        self.assertEqual(results.count(), 1)

    def test_an_unrelated_member_does_not_see_someone_elses_request(self):
        member_c_user = User.objects.create_user(username="wrv_member_c", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member_c, user=member_c_user, actor=self.admin)
        results = welfare_services.list_welfare_requests_for(campaign=self.fund, actor=member_c_user)
        self.assertEqual(results.count(), 0)

    def test_the_requester_themselves_sees_their_own_request(self):
        member_a_user = User.objects.create_user(username="wrv_member_a", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member_a, user=member_a_user, actor=self.admin)
        results = welfare_services.list_welfare_requests_for(campaign=self.fund, actor=member_a_user)
        self.assertEqual(results.count(), 1)


class WelfareRequestHttpEndpointTests(TestCase):
    """The full HTTP round trip — nothing here was reachable outside a Django shell before this."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="wrhe-bodi")
        self.admin = User.objects.create_user(username="wrhe_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(username="wrhe_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Medical Welfare", fixed_amount=Decimal("100"), actor=self.admin)
        self.fund = welfare_services.initiate_community_campaign(category=self.category, title="Community Medical Fund", amount=Decimal("100"), actor=self.admin)

    def _login(self, username):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_submit_approve_disburse_acknowledge_round_trip(self):
        member_client = self._login("wrhe_member")
        submit_res = member_client.post(
            f"/api/welfare/campaigns/{self.fund.id}/requests/", {"amount_requested": "300", "reason": "Medical emergency"}, format="json",
        )
        self.assertEqual(submit_res.status_code, 201, submit_res.data)

        admin_client = self._login("wrhe_admin")
        list_res = admin_client.get(f"/api/welfare/campaigns/{self.fund.id}/requests/list/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.data), 1)

        decide_res = admin_client.post(f"/api/welfare/requests/{submit_res.data['id']}/decide/", {"approve": True, "amount_approved": "250"}, format="json")
        self.assertEqual(decide_res.status_code, 200, decide_res.data)
        self.assertEqual(decide_res.data["status"], "approved")

        disburse_res = admin_client.post(f"/api/welfare/requests/{submit_res.data['id']}/disburse/", {}, format="json")
        self.assertEqual(disburse_res.status_code, 200, disburse_res.data)
        self.assertEqual(disburse_res.data["status"], "disbursed")

        ack_res = member_client.post(f"/api/welfare/requests/{submit_res.data['id']}/acknowledge/", {}, format="json")
        self.assertEqual(ack_res.status_code, 200, ack_res.data)
        self.assertIsNotNone(ack_res.data["acknowledged_at"])

    def test_a_plain_member_cannot_decide_a_request_over_http(self):
        member_client = self._login("wrhe_member")
        submit_res = member_client.post(
            f"/api/welfare/campaigns/{self.fund.id}/requests/", {"amount_requested": "300", "reason": "Medical emergency"}, format="json",
        )
        res = member_client.post(f"/api/welfare/requests/{submit_res.data['id']}/decide/", {"approve": True}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_deciding_an_already_decided_request_returns_400_not_403(self):
        """The genuine state-error case must stay distinct from an authorization failure."""
        member_client = self._login("wrhe_member")
        submit_res = member_client.post(
            f"/api/welfare/campaigns/{self.fund.id}/requests/", {"amount_requested": "300", "reason": "Medical emergency"}, format="json",
        )
        admin_client = self._login("wrhe_admin")
        admin_client.post(f"/api/welfare/requests/{submit_res.data['id']}/decide/", {"approve": True}, format="json")
        second_res = admin_client.post(f"/api/welfare/requests/{submit_res.data['id']}/decide/", {"approve": True}, format="json")
        self.assertEqual(second_res.status_code, 400)

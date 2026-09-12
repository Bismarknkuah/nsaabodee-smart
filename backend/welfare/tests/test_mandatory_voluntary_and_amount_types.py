from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services
from welfare.models import ContributionCategory, WelfareObligation


class VoluntaryCampaignTests(TestCase):
    """
    'A voluntary campaign must NOT create a debt-like outstanding
    balance unless the business rules explicitly say so. This
    distinction is important.' (contribution-scope rules §13, §15)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="vol-bodi")
        self.admin = User.objects.create_user(username="vol_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.category = welfare_services.create_contribution_category(
            community=self.bodi, name="Community Emergency Support Fund", is_mandatory=False,
            amount_type=ContributionCategory.AmountType.FLEXIBLE, actor=self.admin,
        )

    def test_activating_a_voluntary_campaign_generates_no_obligations_at_all(self):
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Emergency Fund", amount=Decimal("50"), actor=self.admin)
        self.assertEqual(campaign.status, "active")
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 0)

    def test_a_member_who_never_contributes_has_no_obligation_and_no_outstanding_balance(self):
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Emergency Fund", amount=Decimal("50"), actor=self.admin)
        self.assertFalse(WelfareObligation.objects.filter(campaign=campaign, member=self.member).exists())

    def test_a_member_who_contributes_voluntarily_creates_their_own_obligation_with_zero_balance(self):
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Emergency Fund", amount=Decimal("50"), actor=self.admin)
        welfare_services.record_voluntary_contribution(campaign=campaign, member=self.member, amount=Decimal("20"), method="cash")
        obligation = WelfareObligation.objects.get(campaign=campaign, member=self.member)
        self.assertEqual(obligation.balance, Decimal("0"))
        self.assertEqual(obligation.payment_status, "paid")

    def test_contributing_any_amount_is_allowed_not_just_the_suggested_figure(self):
        """'Members may contribute: GHS 20, GHS 50, GHS 100, GHS 500, GHS 1,000.'"""
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Emergency Fund", amount=Decimal("50"), actor=self.admin)
        payment = welfare_services.record_voluntary_contribution(campaign=campaign, member=self.member, amount=Decimal("1000"), method="cash")
        self.assertEqual(payment.amount, Decimal("1000"))

    def test_contributing_twice_never_shows_a_balance_owed(self):
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Emergency Fund", amount=Decimal("50"), actor=self.admin)
        welfare_services.record_voluntary_contribution(campaign=campaign, member=self.member, amount=Decimal("20"), method="cash")
        welfare_services.record_voluntary_contribution(campaign=campaign, member=self.member, amount=Decimal("30"), method="cash")
        obligation = WelfareObligation.objects.get(campaign=campaign, member=self.member)
        self.assertEqual(obligation.amount_paid, Decimal("50"))
        self.assertEqual(obligation.balance, Decimal("0"))

    def test_using_the_mandatory_payment_path_on_a_voluntary_campaign_is_rejected(self):
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Emergency Fund", amount=Decimal("50"), actor=self.admin)
        with self.assertRaises(ValidationError):
            welfare_services.record_voluntary_contribution(campaign=campaign, member=self.member, amount=Decimal("0"), method="cash")


class MandatoryCampaignStillGeneratesObligationsTests(TestCase):
    """Confirms the fix didn't overcorrect — a genuinely mandatory campaign still pre-generates obligations for everyone eligible."""

    def test_a_mandatory_campaign_still_generates_an_obligation_per_eligible_member(self):
        bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="mand-bodi")
        admin = User.objects.create_user(username="mand_admin", password="x", community=bodi, role=Role.COMMUNITY_ADMIN)
        asona = family_services.create_family(community=bodi, name="Asona", actor=admin)
        member_services.register_member(community=bodi, full_name="Test Member", gender="male", family=asona)
        category = welfare_services.create_contribution_category(community=bodi, name="Development Levy", is_mandatory=True, fixed_amount=Decimal("100"), actor=admin)
        campaign = welfare_services.initiate_community_campaign(category=category, title="Development Levy 2026", actor=admin)
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 1)


class FixedVsFlexibleOverpaymentTests(TestCase):
    """
    'Campaigns should support Fixed contribution (every eligible
    contributor contributes the defined amount) OR Minimum
    contribution (the defined amount is the minimum)... member can
    contribute GHS 50, GHS 100, GHS 500.' (§12)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ffo-bodi")
        self.admin = User.objects.create_user(username="ffo_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)

    def test_a_fixed_category_rejects_overpayment(self):
        category = welfare_services.create_contribution_category(community=self.bodi, name="Fixed Levy", is_mandatory=True, fixed_amount=Decimal("100"), actor=self.admin)
        campaign = welfare_services.initiate_community_campaign(category=category, title="Fixed Levy 2026", actor=self.admin)
        obligation = WelfareObligation.objects.get(campaign=campaign, member=self.member)
        with self.assertRaises(ValidationError):
            welfare_services.record_welfare_payment(obligation=obligation, amount=Decimal("150"), method="cash")

    def test_a_flexible_category_allows_paying_more_than_the_minimum(self):
        category = welfare_services.create_contribution_category(
            community=self.bodi, name="Minimum-Based Support", is_mandatory=True,
            amount_type=ContributionCategory.AmountType.FLEXIBLE, actor=self.admin,
        )
        campaign = welfare_services.initiate_community_campaign(category=category, title="Support Drive", amount=Decimal("50"), actor=self.admin)
        obligation = WelfareObligation.objects.get(campaign=campaign, member=self.member)
        payment = welfare_services.record_welfare_payment(obligation=obligation, amount=Decimal("500"), method="cash")
        self.assertEqual(payment.amount, Decimal("500"))
        obligation.refresh_from_db()
        self.assertEqual(obligation.amount_paid, Decimal("500"))

    def test_a_flexible_category_still_allows_a_second_payment_after_the_minimum_is_met(self):
        """Paying the exact minimum first, then more later — never blocked as 'already fully paid' the way fixed obligations are."""
        category = welfare_services.create_contribution_category(
            community=self.bodi, name="Minimum-Based Support", is_mandatory=True,
            amount_type=ContributionCategory.AmountType.FLEXIBLE, actor=self.admin,
        )
        campaign = welfare_services.initiate_community_campaign(category=category, title="Support Drive", amount=Decimal("50"), actor=self.admin)
        obligation = WelfareObligation.objects.get(campaign=campaign, member=self.member)
        welfare_services.record_welfare_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        obligation.refresh_from_db()
        welfare_services.record_welfare_payment(obligation=obligation, amount=Decimal("100"), method="cash")
        obligation.refresh_from_db()
        self.assertEqual(obligation.amount_paid, Decimal("150"))


class RecordVoluntaryContributionHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="rvch-bodi")
        self.admin = User.objects.create_user(username="rvch_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(username="rvch_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)
        self.category = welfare_services.create_contribution_category(
            community=self.bodi, name="Emergency Fund", is_mandatory=False,
            amount_type=ContributionCategory.AmountType.FLEXIBLE, actor=self.admin,
        )
        self.campaign = welfare_services.initiate_community_campaign(category=self.category, title="Emergency Fund 2026", amount=Decimal("50"), actor=self.admin)

    def _login(self, username):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_a_member_can_contribute_to_their_own_voluntary_campaign_over_http(self):
        res = self._login("rvch_member").post(
            f"/api/welfare/campaigns/{self.campaign.id}/contribute/", {"amount": "75", "method": "cash"}, format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["balance"], "0.00")

    def test_community_admin_can_record_a_contribution_on_a_members_behalf(self):
        res = self._login("rvch_admin").post(
            f"/api/welfare/campaigns/{self.campaign.id}/contribute/",
            {"amount": "20", "method": "cash", "member_id": str(self.member.id)}, format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_an_unrelated_member_cannot_record_a_contribution_on_someone_elses_behalf(self):
        other_user = User.objects.create_user(username="rvch_other", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        other_member = member_services.register_member(community=self.bodi, full_name="Other", gender="male", family=self.asona)
        member_services.link_member_to_user(member=other_member, user=other_user, actor=self.admin)

        res = self._login("rvch_other").post(
            f"/api/welfare/campaigns/{self.campaign.id}/contribute/",
            {"amount": "20", "method": "cash", "member_id": str(self.member.id)}, format="json",
        )
        self.assertEqual(res.status_code, 403)

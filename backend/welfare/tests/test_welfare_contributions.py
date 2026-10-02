from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from ._helpers import wm_for
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services
from welfare.models import WelfareObligation, ContributionCampaign, ContributionCategory


class ContributionCategoryTests(TestCase):
    """'The Community Administrator should be able to create unlimited contribution categories.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-welfare-categories")
        self.admin = User.objects.create_user(username="welfare_cat_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.non_admin = User.objects.create_user(username="welfare_cat_nonadmin", password="x", community=self.bodi, role=Role.CHAIRMAN)

    def test_community_admin_can_create_a_fixed_amount_category(self):
        category = welfare_services.create_contribution_category(
            community=self.bodi, name="Monthly Welfare Contribution", amount_type=ContributionCategory.AmountType.FIXED,
            fixed_amount=Decimal("10"), frequency=ContributionCategory.Frequency.MONTHLY, actor=self.admin,
        )
        self.assertEqual(category.fixed_amount, Decimal("10"))

    def test_a_fixed_category_without_an_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            welfare_services.create_contribution_category(
                community=self.bodi, name="Should Fail", amount_type=ContributionCategory.AmountType.FIXED, actor=self.admin,
            )

    def test_a_non_admin_cannot_create_a_category(self):
        with self.assertRaises(ValidationError):
            welfare_services.create_contribution_category(community=self.bodi, name="Should Fail", fixed_amount=Decimal("10"), actor=self.non_admin)

    def test_flexible_category_needs_no_fixed_amount(self):
        category = welfare_services.create_contribution_category(
            community=self.bodi, name="Emergency Fundraising", amount_type=ContributionCategory.AmountType.FLEXIBLE, actor=self.admin,
        )
        self.assertIsNone(category.fixed_amount)


class CommunityWideCampaignTests(TestCase):
    """'When the community creates it, it affects all the community.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-welfare-community-wide")
        self.admin = User.objects.create_user(username="welfare_cw_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)
        member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)

        self.category = welfare_services.create_contribution_category(
            community=self.bodi, name="Annual Dues", fixed_amount=Decimal("20"), actor=self.admin,
        )

    def test_a_community_wide_campaign_is_active_immediately_no_approval_needed(self):
        campaign = welfare_services.initiate_community_campaign(
            category=self.category, title="2026 Annual Dues", actor=wm_for(self.admin),
        )
        self.assertEqual(campaign.status, ContributionCampaign.Status.ACTIVE)

    def test_a_community_wide_campaign_bills_every_family(self):
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="2026 Annual Dues", actor=wm_for(self.admin))
        from welfare.models import WelfareObligation
        member_names = set(WelfareObligation.objects.filter(campaign=campaign).values_list("member__full_name", flat=True))
        self.assertIn("Asona Member", member_names)
        self.assertIn("Bretuo Member", member_names)

    def test_an_ordinary_member_cannot_start_a_community_wide_campaign(self):
        member_user = User.objects.create_user(username="welfare_cw_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            welfare_services.initiate_community_campaign(category=self.category, title="Should Fail", actor=member_user)


class FamilyCampaignApprovalTests(TestCase):
    """
    The Community Welfare Manager starts a family's welfare contribution; that family's Head AND Secretary approve;
    only then are the family's members billed. (Replaces the earlier flow — Head/Treasurer initiating, any two
    family executives approving, the Community Admin finalising — which is covered no more.)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fca-bodi")
        self.other = Community.objects.create(name="Other", slug="fca-other")
        self.admin = User.objects.create_user(username="fca_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.wm = User.objects.create_user(username="fca_wm", password="x", community=self.bodi, role=Role.WELFARE_MANAGER)
        self.other_wm = User.objects.create_user(username="fca_other_wm", password="x", community=self.other, role=Role.WELFARE_MANAGER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Family Drive", fixed_amount=Decimal("15"), actor=self.admin)
        def officer(username, role, family):
            user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
            m = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
            member_services.link_member_to_user(member=m, user=user, actor=self.admin)
            return user
        self.head, self.secretary, self.treasurer = officer("fca_head", Role.FAMILY_HEAD, self.asona), officer("fca_sec", Role.FAMILY_SECRETARY, self.asona), officer("fca_tre", Role.FAMILY_TREASURER, self.asona)
        member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)

    def _start(self):
        return welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona drive", actor=self.wm)

    def test_the_welfare_manager_of_another_community_cannot_start_it(self):
        with self.assertRaises(ValidationError):
            welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Nope", actor=self.other_wm)

    def test_head_then_secretary_activates_and_bills_only_that_family(self):
        campaign = self._start()
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.head, approve=True)
        campaign.refresh_from_db(); self.assertEqual(campaign.status, ContributionCampaign.Status.PENDING_APPROVAL)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary, approve=True)
        campaign.refresh_from_db(); self.assertEqual(campaign.status, ContributionCampaign.Status.ACTIVE)
        self.assertEqual(set(WelfareObligation.objects.filter(campaign=campaign).values_list("member__family__name", flat=True)), {"Asona"})

    def test_the_treasurer_and_the_admin_cannot_decide_it(self):
        campaign = self._start()
        for actor in (self.treasurer, self.admin, self.wm):
            with self.assertRaises(ValidationError):
                welfare_services.decide_family_campaign(campaign=campaign, actor=actor, approve=True)

    def test_either_office_can_reject_it(self):
        campaign = self._start()
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary, approve=False)
        campaign.refresh_from_db(); self.assertEqual(campaign.status, ContributionCampaign.Status.REJECTED)
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 0)


class WelfarePaymentTests(TestCase):
    """Mirrors the funeral payment-recording pattern exactly."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-welfare-payments")
        self.admin = User.objects.create_user(username="welfare_pay_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Pay Test Member", gender="male", family=self.asona)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Monthly Dues", fixed_amount=Decimal("10"), actor=self.admin)
        self.campaign = welfare_services.initiate_community_campaign(category=self.category, title="July Dues", actor=wm_for(self.admin))
        from welfare.models import WelfareObligation
        self.obligation = WelfareObligation.objects.get(campaign=self.campaign, member=self.member)

    def test_recording_a_full_payment_marks_the_obligation_paid(self):
        welfare_services.record_welfare_payment(obligation=self.obligation, amount=Decimal("10"), method="cash", collector=self.admin)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.payment_status, "paid")

    def test_a_partial_payment_leaves_a_real_balance(self):
        welfare_services.record_welfare_payment(obligation=self.obligation, amount=Decimal("4"), method="cash", collector=self.admin)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.balance, Decimal("6"))
        self.assertEqual(self.obligation.payment_status, "partial")

    def test_overpaying_is_rejected(self):
        with self.assertRaises(ValidationError):
            welfare_services.record_welfare_payment(obligation=self.obligation, amount=Decimal("50"), method="cash", collector=self.admin)

    def test_a_repeated_client_op_id_is_idempotent(self):
        import uuid
        op_id = uuid.uuid4()
        p1 = welfare_services.record_welfare_payment(obligation=self.obligation, amount=Decimal("5"), method="cash", collector=self.admin, client_op_id=op_id)
        p2 = welfare_services.record_welfare_payment(obligation=self.obligation, amount=Decimal("5"), method="cash", collector=self.admin, client_op_id=op_id)
        self.assertEqual(p1.id, p2.id)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.amount_paid, Decimal("5"))

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services
from welfare.models import ContributionCampaign, ContributionCategory


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
            category=self.category, title="2026 Annual Dues", actor=self.admin,
        )
        self.assertEqual(campaign.status, ContributionCampaign.Status.ACTIVE)

    def test_a_community_wide_campaign_bills_every_family(self):
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="2026 Annual Dues", actor=self.admin)
        from welfare.models import WelfareObligation
        member_names = set(WelfareObligation.objects.filter(campaign=campaign).values_list("member__full_name", flat=True))
        self.assertIn("Asona Member", member_names)
        self.assertIn("Bretuo Member", member_names)

    def test_an_ordinary_member_cannot_start_a_community_wide_campaign(self):
        member_user = User.objects.create_user(username="welfare_cw_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            welfare_services.initiate_community_campaign(category=self.category, title="Should Fail", actor=member_user)


class FamilyInitiatedCampaignApprovalTests(TestCase):
    """
    'Any family can also use it for welfare, so when a family head
    initiates it, it needs the approval of two other family executives
    before his family members get billed... it should only be within
    his jurisdiction.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-welfare-family")
        self.admin = User.objects.create_user(username="welfare_fam_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="welfare_fam_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Asona Secretary", gender="female", family=self.asona)
        self.secretary_user = User.objects.create_user(username="welfare_fam_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary_user, actor=self.admin)
        self.asona.family_secretary = self.secretary_member
        self.asona.save(update_fields=["family_secretary"])

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Asona Treasurer", gender="male", family=self.asona)
        self.treasurer_user = User.objects.create_user(username="welfare_fam_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer_user, actor=self.admin)
        self.asona.family_treasurer = self.treasurer_member
        self.asona.save(update_fields=["family_treasurer"])

        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)

        self.category = welfare_services.create_contribution_category(
            community=self.bodi, name="Family Welfare Drive", fixed_amount=Decimal("15"), actor=self.admin,
        )

    def test_a_family_initiated_campaign_starts_pending_approval(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        self.assertEqual(campaign.status, ContributionCampaign.Status.PENDING_APPROVAL)

    def test_no_obligations_exist_until_approved(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        from welfare.models import WelfareObligation
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 0)

    def test_a_family_head_can_only_initiate_for_their_own_family(self):
        with self.assertRaises(ValidationError):
            welfare_services.initiate_family_campaign(category=self.category, family=self.bretuo, title="Should Fail", actor=self.head_user)

    def test_the_initiator_cannot_approve_their_own_campaign(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        with self.assertRaises(ValidationError):
            welfare_services.decide_family_campaign(campaign=campaign, actor=self.head_user, approve=True)

    def test_one_approval_is_not_enough_when_two_are_required(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=True)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, ContributionCampaign.Status.PENDING_APPROVAL)

    def test_two_distinct_family_executive_approvals_move_it_to_family_approved_not_active(self):
        """'It has to be approved by the community admin before it works' — family executives alone get it to FAMILY_APPROVED, never straight to billed."""
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=True)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.treasurer_user, approve=True)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, ContributionCampaign.Status.FAMILY_APPROVED)
        from welfare.models import WelfareObligation
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 0)

    def test_the_community_admins_final_approval_activates_the_campaign_and_bills_members(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=True)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.treasurer_user, approve=True)
        welfare_services.approve_family_campaign_by_community_admin(campaign=campaign, actor=self.admin)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, ContributionCampaign.Status.ACTIVE)
        from welfare.models import WelfareObligation
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 3)  # head, secretary, treasurer

    def test_the_community_admin_can_reject_a_family_approved_campaign(self):
        """A real gap otherwise: without this, a Community Admin who disagrees with an already family-approved campaign would have no way to actually stop it."""
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=True)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.treasurer_user, approve=True)
        welfare_services.approve_family_campaign_by_community_admin(campaign=campaign, actor=self.admin, approve=False)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, ContributionCampaign.Status.REJECTED)
        from welfare.models import WelfareObligation
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 0)

    def test_community_admin_cannot_give_final_approval_before_the_family_executives_have(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        with self.assertRaises(ValidationError):
            welfare_services.approve_family_campaign_by_community_admin(campaign=campaign, actor=self.admin)

    def test_a_different_communitys_admin_cannot_give_final_approval(self):
        other_community = Community.objects.create(name="Other Town", slug="other-town-welfare")
        other_admin = User.objects.create_user(username="welfare_fam_other_admin", password="x", community=other_community, role=Role.COMMUNITY_ADMIN)
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=True)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.treasurer_user, approve=True)
        with self.assertRaises(ValidationError):
            welfare_services.approve_family_campaign_by_community_admin(campaign=campaign, actor=other_admin)

    def test_family_approved_campaigns_appear_in_the_community_admins_own_queue(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=True)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.treasurer_user, approve=True)
        pending = welfare_services.list_pending_community_admin_welfare_approvals(self.bodi)
        self.assertEqual(pending.count(), 1)

    def test_an_activated_family_campaign_never_bills_another_family(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=True)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.treasurer_user, approve=True)
        welfare_services.approve_family_campaign_by_community_admin(campaign=campaign, actor=self.admin)
        from welfare.models import WelfareObligation
        member_names = set(WelfareObligation.objects.filter(campaign=campaign).values_list("member__full_name", flat=True))
        self.assertNotIn("Bretuo Member", member_names)

    def test_rejecting_a_campaign_never_bills_anyone(self):
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        welfare_services.decide_family_campaign(campaign=campaign, actor=self.secretary_user, approve=False)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, ContributionCampaign.Status.REJECTED)
        from welfare.models import WelfareObligation
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 0)

    def test_an_outsider_from_another_family_cannot_approve(self):
        outsider_user = User.objects.create_user(username="welfare_fam_outsider", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.bretuo_member, user=outsider_user, actor=self.admin)
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona Welfare Drive", actor=self.head_user)
        with self.assertRaises(ValidationError):
            welfare_services.decide_family_campaign(campaign=campaign, actor=outsider_user, approve=True)


class WelfarePaymentTests(TestCase):
    """Mirrors the funeral payment-recording pattern exactly."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-welfare-payments")
        self.admin = User.objects.create_user(username="welfare_pay_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Pay Test Member", gender="male", family=self.asona)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Monthly Dues", fixed_amount=Decimal("10"), actor=self.admin)
        self.campaign = welfare_services.initiate_community_campaign(category=self.category, title="July Dues", actor=self.admin)
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

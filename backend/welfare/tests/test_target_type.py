from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services
from welfare.models import CampaignTargetMember, ContributionCampaign, WelfareObligation


class TownEldersTargetingTests(TestCase):
    """'TOWN_ELDERS SCOPE — Applies only to configured traditional leaders/elders.' (contribution-scope rules §1)"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tet-bodi")
        self.admin = User.objects.create_user(username="tet_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.elder = member_services.register_member(community=self.bodi, full_name="The Chief", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.elder, title="chief", actor=self.admin)
        self.ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary Member", gender="male", family=self.asona)

        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Traditional Leadership Contribution", fixed_amount=Decimal("200"), actor=self.admin)

    def test_a_town_elders_campaign_only_generates_obligations_for_elders(self):
        campaign = ContributionCampaign.objects.create(
            category=self.category, community=self.bodi, family=None, title="Elder Levy",
            amount=Decimal("200"), status=ContributionCampaign.Status.ACTIVE, initiated_by=self.admin,
            target_type=ContributionCampaign.TargetType.TOWN_ELDERS,
        )
        welfare_services.generate_welfare_obligations(campaign)
        self.assertTrue(WelfareObligation.objects.filter(campaign=campaign, member=self.elder).exists())
        self.assertFalse(WelfareObligation.objects.filter(campaign=campaign, member=self.ordinary_member).exists())

    def test_an_all_eligible_campaign_still_includes_ordinary_members_as_before(self):
        """Confirms the default (unset target_type) behaves exactly as it always did."""
        campaign = ContributionCampaign.objects.create(
            category=self.category, community=self.bodi, family=None, title="Ordinary Levy",
            amount=Decimal("200"), status=ContributionCampaign.Status.ACTIVE, initiated_by=self.admin,
        )
        welfare_services.generate_welfare_obligations(campaign)
        self.assertTrue(WelfareObligation.objects.filter(campaign=campaign, member=self.ordinary_member).exists())
        self.assertTrue(WelfareObligation.objects.filter(campaign=campaign, member=self.elder).exists())


class SelectedMembersTargetingTests(TestCase):
    """
    'Family A owns "Family Education Support Fund"... the campaign
    may apply only to Senior family members, family executives,
    specific contributors depending on the configured rules.' (§10)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="smt-bodi")
        self.admin = User.objects.create_user(username="smt_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.selected_member = member_services.register_member(community=self.bodi, full_name="Selected Member", gender="male", family=self.asona)
        self.unselected_member = member_services.register_member(community=self.bodi, full_name="Unselected Member", gender="male", family=self.asona)

        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Education Support Fund", fixed_amount=Decimal("100"), actor=self.admin)
        self.campaign = ContributionCampaign.objects.create(
            category=self.category, community=self.bodi, family=self.asona, title="Family Education Fund",
            amount=Decimal("100"), status=ContributionCampaign.Status.ACTIVE, initiated_by=self.admin,
            target_type=ContributionCampaign.TargetType.SELECTED_MEMBERS,
        )

    def test_only_explicitly_selected_members_get_an_obligation(self):
        welfare_services.set_campaign_target_members(campaign=self.campaign, member_ids=[self.selected_member.id], actor=self.admin)
        welfare_services.generate_welfare_obligations(self.campaign)
        self.assertTrue(WelfareObligation.objects.filter(campaign=self.campaign, member=self.selected_member).exists())
        self.assertFalse(WelfareObligation.objects.filter(campaign=self.campaign, member=self.unselected_member).exists())

    def test_a_member_outside_the_campaigns_own_family_cannot_be_selected(self):
        bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)
        with self.assertRaises(ValidationError):
            welfare_services.set_campaign_target_members(campaign=self.campaign, member_ids=[bretuo_member.id], actor=self.admin)

    def test_re_setting_the_list_replaces_it_entirely_not_accumulates(self):
        other_member = member_services.register_member(community=self.bodi, full_name="Third Member", gender="male", family=self.asona)
        welfare_services.set_campaign_target_members(campaign=self.campaign, member_ids=[self.selected_member.id], actor=self.admin)
        welfare_services.set_campaign_target_members(campaign=self.campaign, member_ids=[other_member.id], actor=self.admin)
        remaining = CampaignTargetMember.objects.filter(campaign=self.campaign)
        self.assertEqual(remaining.count(), 1)
        self.assertEqual(remaining.first().member_id, other_member.id)

    def test_the_list_cannot_be_changed_once_obligations_already_exist(self):
        """'Never allow scope to be changed casually after obligations have already been generated.'"""
        welfare_services.set_campaign_target_members(campaign=self.campaign, member_ids=[self.selected_member.id], actor=self.admin)
        welfare_services.generate_welfare_obligations(self.campaign)
        with self.assertRaises(ValidationError):
            welfare_services.set_campaign_target_members(campaign=self.campaign, member_ids=[self.unselected_member.id], actor=self.admin)

    def test_an_unauthorized_user_cannot_set_the_target_list(self):
        plain_user = User.objects.create_user(username="smt_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            welfare_services.set_campaign_target_members(campaign=self.campaign, member_ids=[self.selected_member.id], actor=plain_user)


class SetCampaignTargetMembersHttpTests(TestCase):
    def test_full_http_round_trip(self):
        from rest_framework.test import APIClient

        bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="scmh-bodi")
        admin = User.objects.create_user(username="scmh_admin", password="a-real-password-123", community=bodi, role=Role.COMMUNITY_ADMIN)
        asona = family_services.create_family(community=bodi, name="Asona", actor=admin)
        member = member_services.register_member(community=bodi, full_name="Selected Member", gender="male", family=asona)
        category = welfare_services.create_contribution_category(community=bodi, name="Education Support", fixed_amount=Decimal("100"), actor=admin)
        campaign = ContributionCampaign.objects.create(
            category=category, community=bodi, family=asona, title="Family Education Fund",
            amount=Decimal("100"), status=ContributionCampaign.Status.ACTIVE, initiated_by=admin,
            target_type=ContributionCampaign.TargetType.SELECTED_MEMBERS,
        )

        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "scmh_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post(f"/api/welfare/campaigns/{campaign.id}/target-members/", {"member_ids": [str(member.id)]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["targeted_member_count"], 1)
        self.assertEqual(CampaignTargetMember.objects.filter(campaign=campaign).count(), 1)

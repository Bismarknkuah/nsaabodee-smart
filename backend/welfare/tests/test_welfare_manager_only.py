from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import FAMILY_ROLE_TYPES, VISIBLE_ROLES, Role, User, canonical_role
from dashboard.services import build_dashboard
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services
from welfare.models import ContributionCampaign, WelfareObligation


class WelfareManagerOnlyTests(TestCase):
    """
    'Community members are billed on welfare but never create it. The only role that creates welfare is the Community
    Welfare Manager: community welfare contributions (everyone billed), or welfare for a particular family (only that
    family billed) which the family's Head and Secretary must approve. No family welfare managers.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="wmo-bodi")
        self.admin = User.objects.create_user(username="wmo_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Welfare", fixed_amount=Decimal("10"), actor=self.admin)
        self.wm = User.objects.create_user(username="wmo_wm", password="x", community=self.bodi, role=Role.WELFARE_MANAGER)
        self.asona_members = [member_services.register_member(community=self.bodi, full_name=f"Asona {i}", gender="male", family=self.asona) for i in range(2)]
        self.bretuo_members = [member_services.register_member(community=self.bodi, full_name=f"Bretuo {i}", gender="male", family=self.bretuo) for i in range(2)]

    def _officer(self, username, role, family):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
        m = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
        member_services.link_member_to_user(member=m, user=user, actor=self.admin)
        return user

    def test_only_the_welfare_manager_creates_community_welfare(self):
        for username, role in (("wmo_chair", Role.CHAIRMAN), ("wmo_sec", Role.SECRETARY), ("wmo_member", Role.COMMUNITY_MEMBER)):
            with self.assertRaises(ValidationError):
                welfare_services.initiate_community_campaign(category=self.category, title="Nope", actor=User.objects.create_user(username=username, password="x", community=self.bodi, role=role))
        with self.assertRaises(ValidationError):
            welfare_services.initiate_community_campaign(category=self.category, title="Nope", actor=self.admin)
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Community welfare contributions", actor=self.wm)
        self.assertEqual(campaign.status, ContributionCampaign.Status.ACTIVE)
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 4)         # everyone is billed

    def test_a_family_campaign_is_started_by_the_welfare_manager_and_billed_only_after_the_head_and_secretary_approve(self):
        head = self._officer("wmo_asona_head", Role.FAMILY_HEAD, self.asona)
        secretary = self._officer("wmo_asona_sec", Role.FAMILY_SECRETARY, self.asona)
        treasurer = self._officer("wmo_asona_tre", Role.FAMILY_TREASURER, self.asona)
        with self.assertRaises(ValidationError):                                                   # the head no longer starts it
            welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Nope", actor=head)
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona welfare", actor=self.wm)
        self.assertEqual(campaign.status, ContributionCampaign.Status.PENDING_APPROVAL)
        self.assertEqual(WelfareObligation.objects.filter(campaign=campaign).count(), 0)          # nothing billed yet
        with self.assertRaises(ValidationError):                                                   # the treasurer cannot approve
            welfare_services.decide_family_campaign(campaign=campaign, actor=treasurer, approve=True)
        with self.assertRaises(ValidationError):                                                   # nor can community leadership
            welfare_services.decide_family_campaign(campaign=campaign, actor=self.admin, approve=True)
        welfare_services.decide_family_campaign(campaign=campaign, actor=head, approve=True)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, ContributionCampaign.Status.PENDING_APPROVAL)          # one office is not enough
        welfare_services.decide_family_campaign(campaign=campaign, actor=secretary, approve=True)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, ContributionCampaign.Status.ACTIVE)                    # both: live, and billed —
        billed = set(WelfareObligation.objects.filter(campaign=campaign).values_list("member__family__name", flat=True))
        self.assertEqual(billed, {"Asona"})                                                        # only that family

    def test_another_familys_officers_cannot_approve(self):
        bretuo_head = self._officer("wmo_b_head", Role.FAMILY_HEAD, self.bretuo)
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona welfare", actor=self.wm)
        with self.assertRaises(ValidationError):
            welfare_services.decide_family_campaign(campaign=campaign, actor=bretuo_head, approve=True)

    def test_family_welfare_manager_is_retired(self):
        self.assertNotIn("family_welfare_manager", FAMILY_ROLE_TYPES)
        self.assertNotIn("family_welfare_manager", VISIBLE_ROLES)
        self.assertEqual(canonical_role("family_welfare_manager"), "community_member")

    def test_a_member_sees_their_welfare_bill_and_the_rest_of_their_money(self):
        member_user = User.objects.create_user(username="wmo_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.asona_members[0], user=member_user, actor=self.admin)
        welfare_services.initiate_community_campaign(category=self.category, title="Community welfare contributions", actor=self.wm)
        ov = build_dashboard(member_user)["sections"]["member_overview"]
        self.assertEqual(Decimal(ov["money"]["welfare_owing"]), Decimal("10"))
        self.assertEqual(ov["welfare_bills"][0]["scope"], "community")
        for key in ("open_bills", "arrears", "money"):
            self.assertIn(key, ov)
        self.assertNotIn("my_desk_assignments", ov)                                                # a member can hold no desk

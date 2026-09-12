from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from notifications.models import Notification
from tenants.models import Community
from welfare import services as welfare_services


class CampaignNotificationScopeTests(TestCase):
    """
    'Notifications must respect scope. When Family A launches a
    campaign: notifications go to eligible Family A members. Do NOT
    notify all community members unless the campaign scope says
    COMMUNITY.' (contribution-scope rules §43)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="cns-bodi")
        self.admin = User.objects.create_user(username="cns_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.member_a = member_services.register_member(community=self.bodi, full_name="Member A", gender="male", family=self.asona)
        self.head_a_user = User.objects.create_user(username="cns_head_a", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.member_a, user=self.head_a_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.member_a, actor=self.admin)

        self.member_b = member_services.register_member(community=self.bodi, full_name="Member B", gender="male", family=self.bretuo)
        self.member_b_user = User.objects.create_user(username="cns_member_b", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member_b, user=self.member_b_user, actor=self.admin)

        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Medical Welfare", fixed_amount=Decimal("100"), actor=self.admin)

    def test_a_community_wide_campaign_notifies_members_across_every_family(self):
        welfare_services.initiate_community_campaign(category=self.category, title="Community Medical Fund", actor=self.admin)
        self.assertTrue(Notification.objects.filter(recipient_user=self.head_a_user, category="welfare_campaign_launched").exists())
        self.assertTrue(Notification.objects.filter(recipient_user=self.member_b_user, category="welfare_campaign_launched").exists())

    def test_a_family_scoped_campaign_never_notifies_a_different_familys_members(self):
        """The core scope-isolation guarantee, applied to notifications specifically — not just obligations."""
        campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Family A Welfare", amount=Decimal("100"), actor=self.head_a_user)
        campaign.status = campaign.Status.FAMILY_APPROVED
        campaign.save(update_fields=["status"])
        welfare_services.approve_family_campaign_by_community_admin(campaign=campaign, actor=self.admin)

        self.assertTrue(Notification.objects.filter(recipient_user=self.head_a_user, category="welfare_campaign_launched").exists())
        self.assertFalse(Notification.objects.filter(recipient_user=self.member_b_user, category="welfare_campaign_launched").exists())

    def test_a_member_with_no_linked_login_is_simply_skipped_not_an_error(self):
        member_services.register_member(community=self.bodi, full_name="Unlinked Member", gender="male", family=self.asona)
        # Should not raise, even though this member has no linked_user to notify.
        welfare_services.initiate_community_campaign(category=self.category, title="Community Medical Fund 2", actor=self.admin)

    def test_the_notification_message_names_the_actual_campaign(self):
        welfare_services.initiate_community_campaign(category=self.category, title="Very Specific Fund Name", actor=self.admin)
        notification = Notification.objects.get(recipient_user=self.head_a_user, category="welfare_campaign_launched")
        self.assertIn("Very Specific Fund Name", notification.message)

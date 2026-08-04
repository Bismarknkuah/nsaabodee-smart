from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, User
from communication import services as communication_services
from dashboard.services import build_dashboard
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services


class MemberDashboardExpansionTests(TestCase):
    """
    'Members should only access their own information... Family
    information. Meeting invitations. Welfare contributions.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-member-expansion",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="member_exp_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.member = member_services.register_member(community=self.bodi, full_name="Expansion Member", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(username="member_exp_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)

    def test_family_information_appears_on_the_members_own_dashboard(self):
        result = build_dashboard(self.member_user)
        family_info = result["sections"]["member_overview"]["family_info"]
        self.assertEqual(family_info["family_name"], "Asona")
        self.assertEqual(family_info["family_head_name"], "Asona Head")

    def test_a_member_with_no_family_gets_no_family_info(self):
        no_family_member = member_services.register_member(community=self.bodi, full_name="No Family Member", gender="male")
        no_family_user = User.objects.create_user(username="member_exp_no_family", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=no_family_member, user=no_family_user, actor=self.admin)
        result = build_dashboard(no_family_user)
        self.assertIsNone(result["sections"]["member_overview"]["family_info"])

    def test_a_community_wide_meeting_appears_on_the_members_dashboard(self):
        communication_services.schedule_meeting(
            community=self.bodi, title="General Meeting", scheduled_for=timezone.now() + timedelta(days=5), actor=self.admin,
        )
        result = build_dashboard(self.member_user)
        titles = [m["title"] for m in result["sections"]["member_overview"]["upcoming_meetings"]]
        self.assertIn("General Meeting", titles)

    def test_the_members_own_family_meeting_appears_but_another_familys_does_not(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        communication_services.schedule_meeting(
            community=self.bodi, family=self.asona, title="Asona Family Meeting", scheduled_for=timezone.now() + timedelta(days=5), actor=self.admin,
        )
        communication_services.schedule_meeting(
            community=self.bodi, family=bretuo, title="Bretuo Only Meeting", scheduled_for=timezone.now() + timedelta(days=5), actor=self.admin,
        )
        result = build_dashboard(self.member_user)
        titles = [m["title"] for m in result["sections"]["member_overview"]["upcoming_meetings"]]
        self.assertIn("Asona Family Meeting", titles)
        self.assertNotIn("Bretuo Only Meeting", titles)

    def test_an_active_welfare_obligation_appears_on_the_members_dashboard(self):
        category = welfare_services.create_contribution_category(community=self.bodi, name="Annual Dues", fixed_amount=Decimal("20"), actor=self.admin)
        welfare_services.initiate_community_campaign(category=category, title="2026 Dues", actor=self.admin)
        result = build_dashboard(self.member_user)
        obligations = result["sections"]["member_overview"]["welfare_obligations"]
        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations[0]["campaign__title"], "2026 Dues")

    def test_a_pending_approval_welfare_campaign_never_shows_as_an_obligation_yet(self):
        category = welfare_services.create_contribution_category(community=self.bodi, name="Family Drive", fixed_amount=Decimal("10"), actor=self.admin)
        head_user = User.objects.create_user(username="member_exp_head_login", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=head_user, actor=self.admin)
        welfare_services.initiate_family_campaign(category=category, family=self.asona, title="Pending Drive", actor=head_user)
        result = build_dashboard(self.member_user)
        self.assertEqual(len(result["sections"]["member_overview"]["welfare_obligations"]), 0)


class CollectorDashboardExpansionTests(TestCase):
    """'Assigned members... Collection analytics.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-collector-expansion",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="collector_exp_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.collector = User.objects.create_user(username="collector_exp_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Collector Test Member", gender="male", family=self.asona)

        from funerals import services as funeral_services
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Collector Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_collections_trend_appears_on_the_collectors_dashboard(self):
        result = build_dashboard(self.collector)
        self.assertIn("collections_trend", result["sections"]["collector_performance"])
        self.assertEqual(len(result["sections"]["collector_performance"]["collections_trend"]), 7)

    def test_members_to_follow_up_shows_a_real_outstanding_member(self):
        result = build_dashboard(self.collector)
        names = [m["member_name"] for m in result["sections"]["collector_performance"]["members_to_follow_up"]]
        self.assertIn("Collector Test Member", names)

    def test_a_fully_paid_member_no_longer_appears_in_the_follow_up_list(self):
        from funerals.models import ContributionObligation
        from funerals import services as funeral_services
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=obligation.expected_amount, method="cash", collector=self.collector)
        result = build_dashboard(self.collector)
        names = [m["member_name"] for m in result["sections"]["collector_performance"]["members_to_follow_up"]]
        self.assertNotIn("Collector Test Member", names)

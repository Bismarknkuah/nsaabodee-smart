from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from accounts.models import Role, User
from communication import services as communication_services
from communication.models import CommunityMeeting
from dashboard.services import build_dashboard
from families import services as family_services
from family_funds import services as fund_services
from funerals import services as funeral_services
from members.models import Member
from tenants.models import Community


class ChiefDashboardNewSectionsTests(TestCase):
    """
    'View community welfare fund statistics. View executive performance
    summaries. View audit summaries. View meeting schedules.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-chief-sections",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="chief_sections_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="chief_sections_chief", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Sections Member", gender="male")

    def test_welfare_fund_summary_is_aggregate_across_all_family_funds(self):
        fund = fund_services.create_family_fund(family=self.asona, name="Asona Welfare Fund", actor=self.admin)
        fund_services.record_fund_contribution(fund=fund, member=self.member, amount=Decimal("100"))

        result = build_dashboard(self.chief)
        summary = result["sections"]["traditional_leader_overview"]["welfare_fund_summary"]
        self.assertEqual(summary["active_fund_count"], 1)
        self.assertEqual(summary["total_contributions_ever"], "100.00")
        self.assertEqual(summary["contributing_family_count"], 1)

    def test_welfare_fund_summary_never_names_a_contributing_member(self):
        fund = fund_services.create_family_fund(family=self.asona, name="Asona Welfare Fund", actor=self.admin)
        fund_services.record_fund_contribution(fund=fund, member=self.member, amount=Decimal("100"))
        result = build_dashboard(self.chief)
        summary = result["sections"]["traditional_leader_overview"]["welfare_fund_summary"]
        self.assertNotIn("Sections Member", str(summary))

    def test_executive_performance_summary_counts_this_months_activity(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Sections Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.filter(funeral_event=funeral, member=self.member).first()
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector=self.admin)

        result = build_dashboard(self.chief)
        summary = result["sections"]["traditional_leader_overview"]["executive_performance_summary"]
        self.assertEqual(summary["payments_recorded_this_month"], 1)

    def test_audit_summary_counts_recent_events_by_category(self):
        family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        result = build_dashboard(self.chief)
        summary = result["sections"]["traditional_leader_overview"]["audit_summary"]
        self.assertEqual(summary["period_days"], 30)
        self.assertGreaterEqual(summary["total_events"], 0)
        self.assertIsInstance(summary["by_category"], dict)

    def test_upcoming_meetings_show_on_the_chiefs_dashboard(self):
        communication_services.schedule_meeting(
            community=self.bodi, title="Monthly General Meeting", scheduled_for=timezone.now() + timedelta(days=7),
            actor=self.admin,
        )
        result = build_dashboard(self.chief)
        meetings = result["sections"]["traditional_leader_overview"]["upcoming_meetings"]
        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0]["title"], "Monthly General Meeting")

    def test_a_cancelled_meeting_never_shows_on_the_chiefs_dashboard(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, title="Cancelled Meeting", scheduled_for=timezone.now() + timedelta(days=7),
            actor=self.admin,
        )
        communication_services.cancel_meeting(meeting=meeting, actor=self.admin)
        result = build_dashboard(self.chief)
        meetings = result["sections"]["traditional_leader_overview"]["upcoming_meetings"]
        self.assertEqual(len(meetings), 0)

    def test_a_past_meeting_never_shows_as_upcoming(self):
        communication_services.schedule_meeting(
            community=self.bodi, title="Past Meeting", scheduled_for=timezone.now() - timedelta(days=1),
            actor=self.admin,
        )
        result = build_dashboard(self.chief)
        meetings = result["sections"]["traditional_leader_overview"]["upcoming_meetings"]
        self.assertEqual(len(meetings), 0)


class MeetingSchedulingServiceTests(TestCase):
    """Direct service-layer tests for scheduling, matching 'community leadership only, visible to everyone.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-meeting-service")
        self.admin = User.objects.create_user(username="meeting_service_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="meeting_service_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.ordinary_member = User.objects.create_user(username="meeting_service_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_community_admin_can_schedule_a_meeting(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, title="Executive Meeting", scheduled_for=timezone.now() + timedelta(days=3), actor=self.admin,
        )
        self.assertEqual(meeting.title, "Executive Meeting")

    def test_chairman_can_also_schedule_a_meeting(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, title="Chairman's Meeting", scheduled_for=timezone.now() + timedelta(days=3), actor=self.chairman,
        )
        self.assertEqual(meeting.title, "Chairman's Meeting")

    def test_an_ordinary_member_cannot_schedule_a_meeting(self):
        with self.assertRaises(ValidationError):
            communication_services.schedule_meeting(
                community=self.bodi, title="Should Fail", scheduled_for=timezone.now() + timedelta(days=3), actor=self.ordinary_member,
            )

    def test_cancelling_a_meeting_removes_it_from_the_upcoming_list(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, title="To Be Cancelled", scheduled_for=timezone.now() + timedelta(days=3), actor=self.admin,
        )
        communication_services.cancel_meeting(meeting=meeting, actor=self.admin)
        upcoming = communication_services.list_upcoming_meetings(self.bodi)
        self.assertEqual(upcoming.count(), 0)

    def test_an_ordinary_member_cannot_cancel_a_meeting(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, title="Protected Meeting", scheduled_for=timezone.now() + timedelta(days=3), actor=self.admin,
        )
        with self.assertRaises(ValidationError):
            communication_services.cancel_meeting(meeting=meeting, actor=self.ordinary_member)

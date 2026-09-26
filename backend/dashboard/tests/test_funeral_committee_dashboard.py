from decimal import Decimal
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, User
from communication import services as communication_services
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from funerals.permissions import is_committee_member_for
from members.models import Member
from members import services as member_services
from tenants.models import Community


class CommitteeMembershipAccessTests(TestCase):
    """'Committee members should only access information related to the funeral event they are assigned to.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-committee-access",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="committee_access_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Committee Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.other_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Other Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-02", collection_start_date="2026-07-02",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

        self.committee_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Committee Person", gender="male")
        self.committee_user = User.objects.create_user(username="committee_person_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.committee_member, user=self.committee_user, actor=self.admin)

        funeral_services.appoint_committee_position(funeral=self.funeral, member=self.committee_member, title="Logistics Coordinator", actor=self.admin)

    def test_is_committee_member_for_is_true_for_the_appointed_funeral(self):
        self.assertTrue(is_committee_member_for(self.committee_user, self.funeral))

    def test_is_committee_member_for_is_false_for_a_different_funeral(self):
        self.assertFalse(is_committee_member_for(self.committee_user, self.other_funeral))

    def test_an_ordinary_member_with_no_committee_position_is_never_a_committee_member(self):
        outsider = User.objects.create_user(username="committee_outsider", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        outsider_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Outsider", gender="male")
        member_services.link_member_to_user(member=outsider_member, user=outsider, actor=self.admin)
        self.assertFalse(is_committee_member_for(outsider, self.funeral))


class CommitteePositionsDashboardTests(TestCase):
    """'Manage funeral planning activities... View contribution summaries. Monitor expenses. Track event progress. View attendance.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-committee-dashboard",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="committee_dash_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Dashboard Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.other_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Not My Committee's Funeral", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-02", collection_start_date="2026-07-02",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

        self.committee_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Dashboard Committee Person", gender="male")
        self.committee_user = User.objects.create_user(username="dashboard_committee_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.committee_member, user=self.committee_user, actor=self.admin)

        funeral_services.appoint_committee_position(funeral=self.funeral, member=self.committee_member, title="Welfare Officer", actor=self.admin)

    def test_committee_positions_section_appears_on_the_members_dashboard(self):
        result = build_dashboard(self.committee_user)
        self.assertIn("committee_positions", result["sections"])
        positions = result["sections"]["committee_positions"]
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["deceased_name"], "Dashboard Deceased")
        self.assertEqual(positions[0]["your_title"], "Welfare Officer")

    def test_committee_positions_section_never_includes_a_funeral_theyre_not_on(self):
        result = build_dashboard(self.committee_user)
        deceased_names = {p["deceased_name"] for p in result["sections"]["committee_positions"]}
        self.assertNotIn("Not My Committee's Funeral", deceased_names)

    def test_the_positions_section_includes_a_real_task_summary(self):
        from tasks import services as task_services
        task_services.assign_task(
            community=self.bodi, assigned_to=self.committee_member, title="Arrange chairs",
            funeral_event=self.funeral, assigned_by=self.admin,
        )
        result = build_dashboard(self.committee_user)
        positions = result["sections"]["committee_positions"]
        self.assertEqual(positions[0]["task_summary"]["total"], 1)

    def test_the_positions_section_includes_contribution_and_attendance_data(self):
        result = build_dashboard(self.committee_user)
        positions = result["sections"]["committee_positions"]
        self.assertIn("contribution_summary", positions[0])
        self.assertIn("attendance_count", positions[0])

    def test_someone_with_no_committee_position_at_all_gets_no_section(self):
        outsider = User.objects.create_user(username="no_committee_outsider", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        outsider_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="No Committee", gender="male")
        member_services.link_member_to_user(member=outsider_member, user=outsider, actor=self.admin)
        result = build_dashboard(outsider)
        self.assertNotIn("committee_positions", result["sections"])


class FuneralScopedMeetingTests(TestCase):
    """'Schedule meetings' (Funeral Committee) — a funeral's own committee members only, using the same underlying meeting model."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-funeral-meetings")
        self.admin = User.objects.create_user(username="fm2_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="FM2 Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.other_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="FM2 Other Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-02", collection_start_date="2026-07-02",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

        self.committee_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="FM2 Committee Person", gender="male")
        self.committee_user = User.objects.create_user(username="fm2_committee_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.committee_member, user=self.committee_user, actor=self.admin)
        funeral_services.appoint_committee_position(funeral=self.funeral, member=self.committee_member, title="Secretary", actor=self.admin)

        self.ordinary_member = User.objects.create_user(username="fm2_ordinary", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_a_committee_member_can_schedule_a_meeting_for_their_own_funeral(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, funeral=self.funeral, title="Committee Planning Meeting",
            scheduled_for=timezone.now() + timedelta(days=3), actor=self.committee_user,
        )
        self.assertEqual(meeting.funeral_event_id, self.funeral.id)

    def test_a_committee_member_cannot_schedule_a_meeting_for_a_funeral_theyre_not_on(self):
        with self.assertRaises(ValidationError):
            communication_services.schedule_meeting(
                community=self.bodi, funeral=self.other_funeral, title="Should Fail",
                scheduled_for=timezone.now() + timedelta(days=3), actor=self.committee_user,
            )

    def test_an_ordinary_member_cannot_schedule_a_funeral_committee_meeting(self):
        with self.assertRaises(ValidationError):
            communication_services.schedule_meeting(
                community=self.bodi, funeral=self.funeral, title="Should Fail",
                scheduled_for=timezone.now() + timedelta(days=3), actor=self.ordinary_member,
            )

    def test_a_funeral_meeting_appears_only_for_that_funerals_own_committee_view(self):
        communication_services.schedule_meeting(
            community=self.bodi, funeral=self.funeral, title="Only This Funeral's Meeting",
            scheduled_for=timezone.now() + timedelta(days=3), actor=self.committee_user,
        )
        this_funeral_view = communication_services.list_upcoming_meetings(self.bodi, funeral=self.funeral)
        other_funeral_view = communication_services.list_upcoming_meetings(self.bodi, funeral=self.other_funeral)
        self.assertEqual(this_funeral_view.count(), 1)
        self.assertEqual(other_funeral_view.count(), 0)

    def test_a_funeral_committee_meeting_never_leaks_to_the_community_wide_view(self):
        communication_services.schedule_meeting(
            community=self.bodi, funeral=self.funeral, title="Private Committee Matter",
            scheduled_for=timezone.now() + timedelta(days=3), actor=self.committee_user,
        )
        community_wide_view = communication_services.list_upcoming_meetings(self.bodi)
        self.assertEqual(community_wide_view.count(), 0)

    def test_a_meeting_cannot_belong_to_both_a_family_and_a_funeral(self):
        with self.assertRaises(ValidationError):
            communication_services.schedule_meeting(
                community=self.bodi, family=self.asona, funeral=self.funeral, title="Should Fail",
                scheduled_for=timezone.now() + timedelta(days=3), actor=self.admin,
            )

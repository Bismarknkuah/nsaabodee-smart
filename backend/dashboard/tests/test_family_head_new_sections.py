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
from members.models import Member
from tenants.models import Community


class FamilyHeadComplianceBreakdownTests(TestCase):
    """'View members who have paid. View members with outstanding contributions. View members flagged as defaulters.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-fh-compliance",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="fh_compliance_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.paid_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Paid Member", gender="male")
        self.unpaid_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Unpaid Member", gender="male")
        self.other_family_member = Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Other Family Member", gender="male")

        self.head_user = User.objects.create_user(username="fh_compliance_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services_head = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Family Head", gender="male", linked_user=self.head_user)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Compliance Deceased", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        from funerals.models import ContributionObligation
        paid_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.paid_member)
        funeral_services.record_payment(obligation=paid_obligation, amount=paid_obligation.expected_amount, method="cash", collector=self.admin)

    def test_breakdown_shows_every_active_member_of_the_family(self):
        from reports.services import family_member_compliance_breakdown
        breakdown = family_member_compliance_breakdown(self.asona)
        names = {b["member_name"] for b in breakdown}
        self.assertIn("Paid Member", names)
        self.assertIn("Unpaid Member", names)
        self.assertIn("The Family Head", names)

    def test_breakdown_never_includes_another_familys_members(self):
        from reports.services import family_member_compliance_breakdown
        breakdown = family_member_compliance_breakdown(self.asona)
        names = {b["member_name"] for b in breakdown}
        self.assertNotIn("Other Family Member", names)

    def test_a_paid_member_shows_paid_count_and_zero_owed(self):
        from reports.services import family_member_compliance_breakdown
        breakdown = family_member_compliance_breakdown(self.asona)
        entry = next(b for b in breakdown if b["member_name"] == "Paid Member")
        self.assertEqual(entry["paid_count"], 1)
        self.assertEqual(entry["outstanding_count"], 0)
        self.assertEqual(entry["total_owed"], "0")

    def test_an_unpaid_member_shows_outstanding_and_a_real_amount_owed(self):
        from reports.services import family_member_compliance_breakdown
        breakdown = family_member_compliance_breakdown(self.asona)
        entry = next(b for b in breakdown if b["member_name"] == "Unpaid Member")
        self.assertEqual(entry["outstanding_count"], 1)
        self.assertGreater(Decimal(entry["total_owed"]), Decimal("0"))

    def test_the_breakdown_appears_on_the_family_heads_own_dashboard(self):
        result = build_dashboard(self.head_user)
        overview = result["sections"]["family_overview"]
        self.assertIn("member_compliance", overview)
        names = {b["member_name"] for b in overview["member_compliance"]}
        self.assertIn("Unpaid Member", names)
        self.assertNotIn("Other Family Member", names)


class FamilyScopedMeetingTests(TestCase):
    """'Schedule family meetings' — the Family Head's own family only, using the same underlying model as community-wide meetings."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-family-meetings")
        self.admin = User.objects.create_user(username="fm_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_user = User.objects.create_user(username="fm_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        Member.objects.create(community=self.bodi, family=self.asona, full_name="FM Family Head", gender="male", linked_user=self.head_user)

        self.other_head_user = User.objects.create_user(username="fm_other_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        Member.objects.create(community=self.bodi, family=self.bretuo, full_name="FM Other Family Head", gender="male", linked_user=self.other_head_user)

        self.ordinary_member = User.objects.create_user(username="fm_ordinary", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_a_family_head_can_schedule_a_meeting_for_their_own_family(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, family=self.asona, title="Asona Family Meeting",
            scheduled_for=timezone.now() + timedelta(days=5), actor=self.head_user,
        )
        self.assertEqual(meeting.family_id, self.asona.id)

    def test_a_family_head_cannot_schedule_a_meeting_for_another_family(self):
        with self.assertRaises(ValidationError):
            communication_services.schedule_meeting(
                community=self.bodi, family=self.bretuo, title="Should Fail",
                scheduled_for=timezone.now() + timedelta(days=5), actor=self.head_user,
            )

    def test_an_ordinary_member_cannot_schedule_a_family_meeting(self):
        with self.assertRaises(ValidationError):
            communication_services.schedule_meeting(
                community=self.bodi, family=self.asona, title="Should Fail",
                scheduled_for=timezone.now() + timedelta(days=5), actor=self.ordinary_member,
            )

    def test_a_family_meeting_appears_for_that_familys_own_view_but_not_the_other_familys(self):
        communication_services.schedule_meeting(
            community=self.bodi, family=self.asona, title="Asona Only Meeting",
            scheduled_for=timezone.now() + timedelta(days=5), actor=self.head_user,
        )
        asona_view = communication_services.list_upcoming_meetings(self.bodi, family=self.asona)
        bretuo_view = communication_services.list_upcoming_meetings(self.bodi, family=self.bretuo)
        self.assertEqual(asona_view.count(), 1)
        self.assertEqual(bretuo_view.count(), 0)

    def test_a_community_wide_meeting_appears_for_every_familys_view(self):
        communication_services.schedule_meeting(
            community=self.bodi, title="Everyone's Meeting",
            scheduled_for=timezone.now() + timedelta(days=5), actor=self.admin,
        )
        asona_view = communication_services.list_upcoming_meetings(self.bodi, family=self.asona)
        bretuo_view = communication_services.list_upcoming_meetings(self.bodi, family=self.bretuo)
        self.assertEqual(asona_view.count(), 1)
        self.assertEqual(bretuo_view.count(), 1)

    def test_a_family_meeting_never_appears_on_the_community_wide_view(self):
        """The Chief's dashboard, and anyone with no family, must never see one family's own private meeting."""
        communication_services.schedule_meeting(
            community=self.bodi, family=self.asona, title="Private Family Matter",
            scheduled_for=timezone.now() + timedelta(days=5), actor=self.head_user,
        )
        community_wide_view = communication_services.list_upcoming_meetings(self.bodi)
        self.assertEqual(community_wide_view.count(), 0)

    def test_a_family_head_can_cancel_their_own_familys_meeting(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, family=self.asona, title="To Cancel",
            scheduled_for=timezone.now() + timedelta(days=5), actor=self.head_user,
        )
        communication_services.cancel_meeting(meeting=meeting, actor=self.head_user)
        self.assertEqual(communication_services.list_upcoming_meetings(self.bodi, family=self.asona).count(), 0)

    def test_a_family_head_cannot_cancel_another_familys_meeting(self):
        meeting = communication_services.schedule_meeting(
            community=self.bodi, family=self.bretuo, title="Bretuo's Own Meeting",
            scheduled_for=timezone.now() + timedelta(days=5), actor=self.other_head_user,
        )
        with self.assertRaises(ValidationError):
            communication_services.cancel_meeting(meeting=meeting, actor=self.head_user)

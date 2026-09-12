from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from family_funds import services as fund_services
from funerals import services as funeral_services
from members.models import Member
from tenants.models import Community


class RoleDifferentiatedFamilyDashboardTests(TestCase):
    """
    'Family head/secretary/treasurer should have analytics views of
    their family (only their family information). Family head has
    oversight of all family activities, the treasurer has oversight of
    all financial information and aspects.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-role-family-dash",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="rfd_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_user = User.objects.create_user(username="rfd_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        self.head_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Head", gender="male", linked_user=self.head_user)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.treasurer_user = User.objects.create_user(username="rfd_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        self.treasurer_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Treasurer", gender="male", linked_user=self.treasurer_user)

        self.secretary_user = User.objects.create_user(username="rfd_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        self.secretary_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Secretary", gender="male", linked_user=self.secretary_user)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_all_three_roles_see_only_their_own_family_never_a_different_one(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for user in (self.head_user, self.treasurer_user, self.secretary_user):
            result = build_dashboard(user)
            overview = result["sections"]["family_overview"]
            self.assertEqual(overview["family_name"], "Asona")
            self.assertNotEqual(overview["family_name"], bretuo.name)

    def test_family_head_gets_the_financial_overview_and_pending_approvals(self):
        """'Family head has oversight of all family activities.'"""
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="Seller",
            amount=Decimal("200"), date_purchased="2026-07-05", recorded_by=self.secretary_user,
        )
        result = build_dashboard(self.head_user)
        overview = result["sections"]["family_overview"]
        self.assertIn("financial_overview", overview)
        self.assertEqual(len(overview["pending_expense_approvals"]), 1)
        self.assertEqual(overview["pending_expense_approvals"][0]["item_name"], "Coffin")

    def test_family_treasurer_gets_deeper_financial_detail_than_the_head(self):
        """'The treasurer has oversight of all financial information and aspects.'"""
        result = build_dashboard(self.treasurer_user)
        overview = result["sections"]["family_overview"]
        self.assertIn("financial_overview", overview)
        self.assertIn("pending_expense_approvals", overview)
        # Genuinely more than the Head gets — the fund-by-fund and
        # approved/pending/rejected breakdown, not just net position.
        self.assertIn("expenditure_summary", overview)
        self.assertIn("fund_summaries", overview)

    def test_family_head_does_NOT_get_the_treasurers_deeper_detail(self):
        result = build_dashboard(self.head_user)
        overview = result["sections"]["family_overview"]
        self.assertNotIn("expenditure_summary", overview)
        self.assertNotIn("fund_summaries", overview)

    def test_family_secretary_sees_their_own_recorded_expenses_not_an_approval_queue(self):
        """'The secretary who recorded it... can see pending and rejected expenses too' — but this is record-keeping, not an approval capability they don't have."""
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Chairs", seller_name="Seller",
            amount=Decimal("50"), date_purchased="2026-07-05", recorded_by=self.secretary_user,
        )
        result = build_dashboard(self.secretary_user)
        overview = result["sections"]["family_overview"]
        self.assertIn("my_recorded_expenses", overview)
        self.assertEqual(len(overview["my_recorded_expenses"]), 1)
        self.assertEqual(overview["my_recorded_expenses"][0]["item_name"], "Chairs")
        # Secretary never gets the finance-officer sections — they can
        # record an expense but never approve one.
        self.assertNotIn("financial_overview", overview)
        self.assertNotIn("pending_expense_approvals", overview)

    def test_secretary_only_sees_their_own_recorded_expenses_not_the_treasurers(self):
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Secretary's Item", seller_name="Seller",
            amount=Decimal("30"), date_purchased="2026-07-05", recorded_by=self.secretary_user,
        )
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Treasurer's Item", seller_name="Seller",
            amount=Decimal("40"), date_purchased="2026-07-05", recorded_by=self.treasurer_user,
        )
        result = build_dashboard(self.secretary_user)
        items = [e["item_name"] for e in result["sections"]["family_overview"]["my_recorded_expenses"]]
        self.assertIn("Secretary's Item", items)
        self.assertNotIn("Treasurer's Item", items)

    def test_all_three_roles_still_get_the_shared_baseline_sections(self):
        for user in (self.head_user, self.treasurer_user, self.secretary_user):
            overview = build_dashboard(user)["sections"]["family_overview"]
            self.assertIn("statement", overview)
            self.assertIn("member_compliance", overview)
            self.assertIn("upcoming_meetings", overview)
            self.assertEqual(overview["role"], user.role)

    def test_family_head_gets_a_task_summary_counting_every_status(self):
        """'The family head needs more tasks features... check it and add features that need to be added.'"""
        from tasks import services as task_services

        member_a = Member.objects.create(community=self.bodi, family=self.asona, full_name="Task Member A", gender="male")
        member_b = Member.objects.create(community=self.bodi, family=self.asona, full_name="Task Member B", gender="male")
        task_services.assign_task(community=self.bodi, assigned_to=member_a, title="Task A", assigned_by=self.head_user)
        task2 = task_services.assign_task(community=self.bodi, assigned_to=member_b, title="Task B", assigned_by=self.head_user)
        task_services.update_task_status(task=task2, status="in_progress", actor=self.head_user)

        overview = build_dashboard(self.head_user)["sections"]["family_overview"]
        self.assertIn("task_summary", overview)
        self.assertEqual(overview["task_summary"]["pending"], 1)
        self.assertEqual(overview["task_summary"]["in_progress"], 1)
        self.assertEqual(overview["task_summary"]["done"], 0)

    def test_family_head_sees_tasks_awaiting_their_own_approval(self):
        from tasks import services as task_services

        assignee_user = User.objects.create_user(username="rfd_task_assignee", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        assignee_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Task Assignee", gender="male", linked_user=assignee_user)
        task = task_services.assign_task(community=self.bodi, assigned_to=assignee_member, title="Submit for review", assigned_by=self.head_user)
        task_services.update_task_status(task=task, status="pending_approval", actor=assignee_user)

        overview = build_dashboard(self.head_user)["sections"]["family_overview"]
        self.assertEqual(overview["task_summary"]["awaiting_your_approval"], 1)
        self.assertEqual(len(overview["tasks_awaiting_approval"]), 1)
        self.assertEqual(overview["tasks_awaiting_approval"][0]["title"], "Submit for review")

    def test_family_head_task_summary_never_counts_a_different_familys_tasks(self):
        from tasks import services as task_services

        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        bretuo_member = Member.objects.create(community=self.bodi, family=bretuo, full_name="Bretuo Member", gender="male")
        bretuo_head_user = User.objects.create_user(username="rfd_bretuo_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        Member.objects.create(community=self.bodi, family=bretuo, full_name="Bretuo Head", gender="male", linked_user=bretuo_head_user)
        task_services.assign_task(community=self.bodi, assigned_to=bretuo_member, title="Bretuo's own task", assigned_by=bretuo_head_user)

        overview = build_dashboard(self.head_user)["sections"]["family_overview"]
        self.assertEqual(overview["task_summary"]["pending"], 0)

    def test_treasurer_and_secretary_do_NOT_get_the_task_summary(self):
        """This is genuinely the Head's own oversight, not something every family officer needs."""
        for user in (self.treasurer_user, self.secretary_user):
            overview = build_dashboard(user)["sections"]["family_overview"]
            self.assertNotIn("task_summary", overview)
            self.assertNotIn("tasks_awaiting_approval", overview)

    def test_overdue_tasks_are_counted_separately_from_status(self):
        from datetime import date, timedelta
        from tasks import services as task_services

        overdue_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Overdue Member", gender="male")
        task_services.assign_task(
            community=self.bodi, assigned_to=overdue_member, title="Overdue Task",
            assigned_by=self.head_user, due_date=date.today() - timedelta(days=3),
        )
        overview = build_dashboard(self.head_user)["sections"]["family_overview"]
        self.assertEqual(overview["task_summary"]["overdue"], 1)

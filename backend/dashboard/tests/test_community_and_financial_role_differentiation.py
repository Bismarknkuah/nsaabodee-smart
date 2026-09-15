from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class CommunityTaskOversightTests(TestCase):
    """'The community executive should also have oversight analysis based on their tasks.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-community-tasks")
        self.admin = User.objects.create_user(username="ct_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="ct_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_community_admin_sees_a_community_wide_task_summary(self):
        from tasks import services as task_services
        member = member_services.register_member(community=self.bodi, full_name="Task Member", gender="male", family=self.asona)
        task_services.assign_task(community=self.bodi, assigned_to=member, title="Community task", assigned_by=self.admin)

        overview = build_dashboard(self.admin)["sections"]["community_overview"]
        self.assertIn("task_summary", overview)
        self.assertEqual(overview["task_summary"]["pending"], 1)

    def test_chairman_sees_it_too(self):
        overview = build_dashboard(self.chairman)["sections"]["community_overview"]
        self.assertIn("task_summary", overview)

    def test_traditional_leader_sees_task_summary_too_since_they_can_now_assign(self):
        leader = User.objects.create_user(username="ct_leader", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        overview = build_dashboard(leader)["sections"]["traditional_leader_overview"]
        self.assertIn("task_summary", overview)

    def test_task_summary_counts_every_status_correctly(self):
        from tasks import services as task_services
        member_a = member_services.register_member(community=self.bodi, full_name="Member A", gender="male", family=self.asona)
        member_b = member_services.register_member(community=self.bodi, full_name="Member B", gender="male", family=self.asona)
        task_services.assign_task(community=self.bodi, assigned_to=member_a, title="Task A", assigned_by=self.admin)
        task2 = task_services.assign_task(community=self.bodi, assigned_to=member_b, title="Task B", assigned_by=self.admin)
        task_services.update_task_status(task=task2, status="in_progress", actor=self.admin)

        summary = build_dashboard(self.admin)["sections"]["community_overview"]["task_summary"]
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["in_progress"], 1)
        self.assertEqual(summary["done"], 0)


class RoleDifferentiatedFinancialOfficerViewTests(TestCase):
    """'Treasurer sees all the financial aspects, and other executives also see what they are capable to.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-financial-roles",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="rfo_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="rfo_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.financial_secretary = User.objects.create_user(username="rfo_finsec", password="x", community=self.bodi, role=Role.FINANCIAL_SECRETARY)
        self.auditor = User.objects.create_user(username="rfo_auditor", password="x", community=self.bodi, role=Role.AUDITOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            own_family_amount=Decimal("10"),
        )

    def _make_a_pending_reversal(self):
        from funerals.models import ContributionObligation
        member = member_services.register_member(community=self.bodi, full_name="Reversal Member", gender="male", family=self.asona)
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=member)
        payment = funeral_services.record_payment(obligation=obligation, amount=obligation.expected_amount, method="cash", collector_name="Test Collector")
        return funeral_services.request_payment_reversal(payment=payment, reason="Wrong amount entered", actor=self.treasurer)

    def test_treasurer_gets_the_actionable_reversal_list_not_just_a_count(self):
        self._make_a_pending_reversal()
        overview = build_dashboard(self.treasurer)["sections"]["financial_overview"]
        self.assertIn("pending_reversal_requests", overview)
        self.assertEqual(len(overview["pending_reversal_requests"]), 1)

    def test_financial_secretary_gets_the_actionable_list_too(self):
        """They share the same request authority as Treasurer (REVERSAL_REQUEST_ROLES)."""
        self._make_a_pending_reversal()
        overview = build_dashboard(self.financial_secretary)["sections"]["financial_overview"]
        self.assertIn("pending_reversal_requests", overview)

    def test_auditor_does_NOT_get_the_actionable_list_they_cant_act_on(self):
        """An Auditor can never request or approve a reversal — the count in `base` is enough; the actionable list would be misleading."""
        self._make_a_pending_reversal()
        overview = build_dashboard(self.auditor)["sections"]["financial_overview"]
        self.assertNotIn("pending_reversal_requests", overview)
        self.assertIn("pending_payment_reversals_count", overview)

    def test_auditor_gets_a_review_focused_view_instead(self):
        overview = build_dashboard(self.auditor)["sections"]["financial_overview"]
        self.assertIn("suspicious_transaction_summary", overview)
        self.assertIn("recent_reversal_history", overview)

    def test_treasurer_does_NOT_get_the_auditors_review_sections(self):
        overview = build_dashboard(self.treasurer)["sections"]["financial_overview"]
        self.assertNotIn("suspicious_transaction_summary", overview)
        self.assertNotIn("recent_reversal_history", overview)

    def test_auditors_reversal_history_excludes_still_pending_ones(self):
        reversal = self._make_a_pending_reversal()
        overview = build_dashboard(self.auditor)["sections"]["financial_overview"]
        history_ids = [r["id"] for r in overview["recent_reversal_history"]]
        self.assertNotIn(str(reversal.id), history_ids)

    def test_all_three_still_get_the_shared_baseline_data(self):
        for user in (self.treasurer, self.financial_secretary, self.auditor):
            overview = build_dashboard(user)["sections"]["financial_overview"]
            self.assertIn("today", overview)
            self.assertIn("month_to_date", overview)
            self.assertIn("outstanding_members", overview)

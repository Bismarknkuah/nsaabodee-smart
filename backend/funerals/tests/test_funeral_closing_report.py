from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funeral_logistics import services as logistics_services
from funeral_logistics.models import FuneralExpense
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class FuneralClosingReportTests(TestCase):
    """
    'Each funeral should have its own fund [so] the family knows the
    expenditure of that particular funeral, so accountability wouldn't
    be a problem... after every funeral each ledger should know the
    amount they received, and those who didn't pay.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="fcr-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="fcr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.paid_member = member_services.register_member(community=self.bodi, full_name="Paid Member", gender="male", family=self.asona)
        self.unpaid_member = member_services.register_member(community=self.bodi, full_name="Unpaid Member", gender="female", family=self.asona)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01", actor=self.admin,
        )
        paid_obligation = self.funeral.obligations.get(member=self.paid_member)
        funeral_services.record_payment(obligation=paid_obligation, amount=paid_obligation.expected_amount, method="cash", collector_name="Front Desk")

    def test_total_received_matches_only_this_funerals_own_payments(self):
        report = funeral_services.funeral_closing_report(self.funeral)
        paid_obligation = self.funeral.obligations.get(member=self.paid_member)
        self.assertEqual(Decimal(report["total_received"]), paid_obligation.amount_paid)

    def test_ledger_breakdown_shows_each_ledgers_own_amount_received(self):
        """'After every funeral each ledger should be able to know the amount they received' — the seven-ledger split, not just one merged total."""
        report = funeral_services.funeral_closing_report(self.funeral)
        breakdown = report["ledger_breakdown"]
        paid_obligation = self.funeral.obligations.get(member=self.paid_member)
        self.assertEqual(Decimal(breakdown["family_ledger"]["collected_total"]), paid_obligation.amount_paid)
        self.assertIn("community_ledger", breakdown)
        self.assertIn("guest_ledger", breakdown)
        self.assertIn("asupede_ledger", breakdown)

    def test_who_did_not_pay_lists_the_unpaid_member_but_not_the_paid_one(self):
        report = funeral_services.funeral_closing_report(self.funeral)
        names = {e["member_name"] for e in report["who_did_not_pay"]}
        self.assertIn("Unpaid Member", names)
        self.assertNotIn("Paid Member", names)

    def test_who_did_not_pay_includes_the_exact_balance_owed(self):
        report = funeral_services.funeral_closing_report(self.funeral)
        unpaid_obligation = self.funeral.obligations.get(member=self.unpaid_member)
        entry = next(e for e in report["who_did_not_pay"] if e["member_name"] == "Unpaid Member")
        self.assertEqual(Decimal(entry["balance"]), unpaid_obligation.balance)

    def test_total_spent_on_logistics_only_counts_paid_and_partial_expenses(self):
        approver = User.objects.create_user(username="fcr_approver", password="x", community=self.bodi, role=Role.TREASURER)
        paid_expense = logistics_services.record_expense(
            funeral=self.funeral, description="Chairs", category=FuneralExpense.Category.VENUE,
            incurred_on="2026-07-02", amount=Decimal("80"), recorded_by=self.admin,
        )
        logistics_services.decide_expense_status(expense=paid_expense, status=FuneralExpense.Status.PAID, actor=approver)
        logistics_services.record_expense(
            funeral=self.funeral, description="Coffin quote", category=FuneralExpense.Category.COFFIN,
            incurred_on="2026-07-02", amount=Decimal("500"), recorded_by=self.admin,
        )  # left at its default Pending Approval status — should not count as spent yet
        report = funeral_services.funeral_closing_report(self.funeral)
        self.assertEqual(Decimal(report["total_spent_on_logistics"]), Decimal("80"))

    def test_a_payment_toward_a_different_funeral_never_counts_toward_this_ones_total_received(self):
        """
        The real point of 'each funeral should have its own fund' —
        verified directly against a payment, not against member
        enrollment (every active member is legitimately enrolled in
        every funeral that's still open when they register, by
        design — that's a separate, correct behavior, not what this
        isolation claim is actually about).
        """
        other_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Second Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-08-01", collection_start_date="2026-08-01", actor=self.admin,
        )
        other_obligation = other_funeral.obligations.get(member=self.paid_member)
        funeral_services.record_payment(obligation=other_obligation, amount=other_obligation.expected_amount, method="cash", collector_name="Front Desk")

        report = funeral_services.funeral_closing_report(self.funeral)
        paid_obligation = self.funeral.obligations.get(member=self.paid_member)
        self.assertEqual(Decimal(report["total_received"]), paid_obligation.amount_paid)


class FuneralClosingReportEndpointTests(TestCase):
    """The HTTP layer — the view action wiring, and the PDF export path, neither exercised by the service-level tests above."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="fcre-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="fcre_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Endpoint Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01", actor=self.admin,
        )

    def _login(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "fcre_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_closing_report_endpoint_returns_json_by_default(self):
        client = self._login()
        res = client.get(f"/api/funerals/{self.funeral.id}/closing-report/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["deceased_name"], "Endpoint Deceased")
        self.assertIn("who_did_not_pay", res.data)

    def test_closing_report_endpoint_returns_a_real_pdf_when_exported(self):
        client = self._login()
        res = client.get(f"/api/funerals/{self.funeral.id}/closing-report/?export=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))

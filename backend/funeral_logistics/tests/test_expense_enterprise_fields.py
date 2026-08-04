from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funeral_logistics import services
from funeral_logistics.models import FuneralExpense
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class ExpenseEnterpriseFieldsTests(TestCase):
    """'Item, Quantity, Unit price, Total amount, Supplier, Buyer, Approver, Payment status... Credit payments create liabilities.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-expense-enterprise",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="expense_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="expense_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Expense Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.buyer_member = member_services.register_member(community=self.bodi, full_name="The Buyer", gender="male", family=self.asona)

    def test_quantity_and_unit_price_auto_compute_the_total_amount(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Plastic chairs", category=FuneralExpense.Category.VENUE,
            quantity=50, unit_price=Decimal("4.50"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        self.assertEqual(expense.amount, Decimal("225.00"))

    def test_amount_alone_still_works_without_a_unit_price_breakdown(self):
        """Backward compatible with the original, already-working path — not every real expense breaks down this way."""
        expense = services.record_expense(
            funeral=self.funeral, description="Cemetery fees", category=FuneralExpense.Category.BURIAL_FEES,
            amount=Decimal("800"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        self.assertEqual(expense.amount, Decimal("800"))

    def test_neither_amount_nor_a_full_quantity_and_price_breakdown_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.record_expense(
                funeral=self.funeral, description="Missing numbers", category=FuneralExpense.Category.OTHER,
                incurred_on="2026-07-03", recorded_by=self.admin,
            )

    def test_supplier_buyer_item_and_notes_are_all_recorded(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Coffin", category=FuneralExpense.Category.COFFIN,
            amount=Decimal("1500"), incurred_on="2026-07-03", recorded_by=self.admin,
            item_name="Mahogany casket", supplier_name="Accra Casket Supplies", buyer=self.buyer_member,
            notes="Family specifically requested mahogany.",
        )
        self.assertEqual(expense.item_name, "Mahogany casket")
        self.assertEqual(expense.supplier_name, "Accra Casket Supplies")
        self.assertEqual(expense.buyer_id, self.buyer_member.id)
        self.assertIn("mahogany", expense.notes.lower())

    def test_a_new_expense_defaults_to_pending_approval_not_silently_paid(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Transport", category=FuneralExpense.Category.TRANSPORT,
            amount=Decimal("300"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        self.assertEqual(expense.status, FuneralExpense.Status.PENDING_APPROVAL)
        self.assertEqual(expense.amount_paid, Decimal("0"))

    def test_approving_as_paid_sets_amount_paid_to_the_full_amount(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Transport", category=FuneralExpense.Category.TRANSPORT,
            amount=Decimal("300"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        updated = services.decide_expense_status(expense=expense, status=FuneralExpense.Status.PAID, actor=self.treasurer)
        self.assertEqual(updated.amount_paid, Decimal("300"))
        self.assertEqual(updated.approved_by_id, self.treasurer.id)
        self.assertIsNotNone(updated.approved_at)

    def test_the_recorder_cannot_approve_their_own_expense(self):
        """'The system must enforce maker-checker (dual approval) controls for sensitive financial... operations.'"""
        expense = services.record_expense(
            funeral=self.funeral, description="Transport", category=FuneralExpense.Category.TRANSPORT,
            amount=Decimal("300"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            services.decide_expense_status(expense=expense, status=FuneralExpense.Status.PAID, actor=self.admin)

    def test_marking_credit_creates_a_genuine_liability(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Printing", category=FuneralExpense.Category.PRINTING,
            amount=Decimal("200"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        services.decide_expense_status(expense=expense, status=FuneralExpense.Status.CREDIT, actor=self.treasurer)
        liabilities = services.list_expense_liabilities(community=self.bodi)
        self.assertEqual(len(liabilities), 1)
        self.assertEqual(liabilities[0].id, expense.id)

    def test_a_fully_paid_expense_never_shows_as_a_liability(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Printing", category=FuneralExpense.Category.PRINTING,
            amount=Decimal("200"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        services.decide_expense_status(expense=expense, status=FuneralExpense.Status.PAID, actor=self.treasurer)
        self.assertEqual(services.list_expense_liabilities(community=self.bodi), [])

    def test_a_partial_payment_requires_an_amount_paid_and_is_still_a_liability(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Catering", category=FuneralExpense.Category.CATERING,
            amount=Decimal("2000"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            services.decide_expense_status(expense=expense, status=FuneralExpense.Status.PARTIAL, actor=self.treasurer)

        updated = services.decide_expense_status(expense=expense, status=FuneralExpense.Status.PARTIAL, amount_paid=Decimal("1200"), actor=self.treasurer)
        self.assertEqual(updated.amount_paid, Decimal("1200"))
        liabilities = services.list_expense_liabilities(community=self.bodi)
        self.assertEqual(len(liabilities), 1)

    def test_amount_paid_cannot_exceed_the_expenses_total(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Catering", category=FuneralExpense.Category.CATERING,
            amount=Decimal("2000"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            services.decide_expense_status(expense=expense, status=FuneralExpense.Status.PARTIAL, amount_paid=Decimal("5000"), actor=self.treasurer)

    def test_cancelling_a_pending_expense_zeroes_out_amount_paid(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Transport", category=FuneralExpense.Category.TRANSPORT,
            amount=Decimal("300"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        updated = services.decide_expense_status(expense=expense, status=FuneralExpense.Status.CANCELLED, actor=self.treasurer)
        self.assertEqual(updated.amount_paid, Decimal("0"))
        self.assertNotIn(updated, services.list_expense_liabilities(community=self.bodi))

    def test_a_cancelled_expense_is_excluded_from_the_funerals_own_summary_total(self):
        kept = services.record_expense(
            funeral=self.funeral, description="Transport", category=FuneralExpense.Category.TRANSPORT,
            amount=Decimal("300"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        services.decide_expense_status(expense=kept, status=FuneralExpense.Status.PAID, actor=self.treasurer)

        cancelled = services.record_expense(
            funeral=self.funeral, description="Cancelled catering order", category=FuneralExpense.Category.CATERING,
            amount=Decimal("2000"), incurred_on="2026-07-03", recorded_by=self.admin,
        )
        services.decide_expense_status(expense=cancelled, status=FuneralExpense.Status.CANCELLED, actor=self.treasurer)

        summary = services.expense_summary(self.funeral)
        self.assertEqual(summary["total_expenses"], "300.00")
        self.assertEqual(summary["expense_count"], 1)
        self.assertEqual(summary["cancelled_count"], 1)


class ExpenseEnterpriseFieldsHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-expense-http",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="expense_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="expense_http_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        self.member = User.objects.create_user(username="expense_http_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="HTTP Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_round_trip_record_with_quantity_and_price_then_decide_status(self):
        client = self._login("expense_http_admin")
        record_res = client.post(f"/api/funerals/{self.funeral.id}/expenses/", {
            "description": "Chairs", "category": "venue", "quantity": 100, "unit_price": "3.50", "incurred_on": "2026-07-03",
        })
        self.assertEqual(record_res.status_code, 201)
        self.assertEqual(record_res.data["amount"], "350.00")
        self.assertEqual(record_res.data["status"], "pending_approval")
        expense_id = record_res.data["id"]

        decide_res = self._login("expense_http_treasurer").post(f"/api/funerals/{self.funeral.id}/expenses/{expense_id}/status/", {"status": "paid"})
        self.assertEqual(decide_res.status_code, 200)
        self.assertEqual(decide_res.data["status"], "paid")
        self.assertEqual(decide_res.data["balance_owed"], "0.00")

    def test_the_community_liabilities_endpoint_shows_credit_expenses(self):
        client = self._login("expense_http_admin")
        record_res = client.post(f"/api/funerals/{self.funeral.id}/expenses/", {
            "description": "Coffin", "category": "coffin", "amount": "1500", "incurred_on": "2026-07-03",
        })
        expense_id = record_res.data["id"]
        self._login("expense_http_treasurer").post(f"/api/funerals/{self.funeral.id}/expenses/{expense_id}/status/", {"status": "credit"})

        liabilities_res = client.get("/api/expenses/liabilities/")
        self.assertEqual(liabilities_res.status_code, 200)
        self.assertEqual(len(liabilities_res.data), 1)
        self.assertEqual(liabilities_res.data[0]["status"], "credit")

    def test_the_expenses_overview_endpoint_shows_every_active_funerals_real_total(self):
        """'The funeral expenses should have its own link to be one of the multiple tasks' — a dedicated overview, not just outstanding/credit expenses."""
        client = self._login("expense_http_admin")
        record_res = client.post(f"/api/funerals/{self.funeral.id}/expenses/", {
            "description": "Coffin", "category": "coffin", "amount": "1500", "incurred_on": "2026-07-03",
        })
        expense_id = record_res.data["id"]
        self._login("expense_http_treasurer").post(f"/api/funerals/{self.funeral.id}/expenses/{expense_id}/status/", {"status": "paid"})

        overview_res = client.get("/api/expenses/overview/")
        self.assertEqual(overview_res.status_code, 200)
        self.assertEqual(len(overview_res.data), 1)
        self.assertEqual(overview_res.data[0]["total_expenses"], "1500.00")
        self.assertEqual(overview_res.data[0]["deceased_name"], self.funeral.deceased_name)

    def test_an_ordinary_member_cannot_record_an_expense_or_decide_its_status(self):
        record_res = self._login("expense_http_admin").post(f"/api/funerals/{self.funeral.id}/expenses/", {
            "description": "Transport", "category": "transport", "amount": "300", "incurred_on": "2026-07-03",
        })
        expense_id = record_res.data["id"]

        member_client = self._login("expense_http_member")
        res1 = member_client.post(f"/api/funerals/{self.funeral.id}/expenses/", {
            "description": "Should be rejected", "category": "other", "amount": "50", "incurred_on": "2026-07-03",
        })
        self.assertEqual(res1.status_code, 403)
        res2 = member_client.post(f"/api/funerals/{self.funeral.id}/expenses/{expense_id}/status/", {"status": "paid"})
        self.assertEqual(res2.status_code, 403)

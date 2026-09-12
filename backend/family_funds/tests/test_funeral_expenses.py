from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from family_funds import services as fund_services
from family_funds.models import FamilyFuneralExpense
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class FuneralExpenseWorkflowTests(TestCase):
    """
    'Any expenditure for the funeral will be documented... date an item
    was purchased, item name, seller name, seller contact, amount paid,
    who paid the money. Anything bought has to be approved by the
    finance officer of the family. Abusuapanin also oversees all
    activities.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Secretary Person", gender="female", family=self.asona)
        self.secretary_user = User.objects.create_user(username="asona_secretary", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary_user, actor=self.admin)
        family_services.assign_family_officer(family=self.asona, member=self.secretary_member, officer_role="secretary", actor=self.head_user)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Treasurer Person", gender="male", family=self.asona)
        self.treasurer_user = User.objects.create_user(username="asona_treasurer", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer_user, actor=self.admin)
        family_services.assign_family_officer(family=self.asona, member=self.treasurer_member, officer_role="treasurer", actor=self.head_user)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_expense_starts_pending(self):
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC Casket Co.",
            seller_contact="0244000000", amount=Decimal("2000"), date_purchased="2026-07-02",
            paid_by_member=self.treasurer_member, recorded_by=self.secretary_user,
        )
        self.assertEqual(expense.status, FamilyFuneralExpense.Status.PENDING)

    def test_the_family_head_cannot_record_purchase_an_expense(self):
        """'The family head is not allowed to purchase any items, his own is to review, reject or approve items bought.'"""
        with self.assertRaises(ValidationError):
            fund_services.record_funeral_expense(
                family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC Casket Co.",
                amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.head_user,
            )

    def test_the_family_head_can_still_approve_and_reject_despite_not_recording(self):
        """His own authority — review, approve, reject — is untouched by the recording restriction."""
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC Casket Co.",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        fund_services.approve_funeral_expense(expense=expense, actor=self.head_user)
        expense.refresh_from_db()
        self.assertEqual(expense.status, FamilyFuneralExpense.Status.APPROVED)

    def test_family_expenses_can_be_exported_as_a_real_pdf(self):
        """'Family expenses should also be printable or downloaded.'"""
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC Casket Co.",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        client = self._login("abusuapanin")
        res = client.get(f"/api/families/{self.asona.id}/funeral-expenses/summary/?export=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))

    def test_secretary_can_record_an_expense_via_http(self):
        client = self._login("asona_secretary")
        res = client.post(f"/api/families/{self.asona.id}/funeral-expenses/", {
            "funeral_event": str(self.funeral.id), "item_name": "Chairs and canopy", "seller_name": "Event Rentals GH",
            "seller_contact": "0201234567", "amount": "500", "date_purchased": "2026-07-03",
            "paid_by_member_id": str(self.treasurer_member.id),
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending")
        self.assertEqual(res.data["seller_name"], "Event Rentals GH")

    def test_family_cannot_record_expense_for_a_funeral_that_isnt_theirs(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        with self.assertRaises(ValidationError):
            fund_services.record_funeral_expense(
                family=bretuo, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
                amount=Decimal("100"), date_purchased="2026-07-02",
            )

    def test_treasurer_can_approve_an_expense(self):
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC Casket Co.",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        client = self._login("asona_treasurer")
        res = client.post(f"/api/families/{self.asona.id}/funeral-expenses/{expense.id}/decision/", {"action": "approve"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "approved")

    def test_secretary_cannot_approve_her_own_recorded_expense(self):
        """The one who recorded it isn't automatically the one who can approve it — only the treasurer can."""
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        client = self._login("asona_secretary")
        res = client.post(f"/api/families/{self.asona.id}/funeral-expenses/{expense.id}/decision/", {"action": "approve"})
        self.assertEqual(res.status_code, 403)

    def test_family_head_can_view_and_also_approve(self):
        """The abusuapanin has ultimate authority over his own family's affairs, same as the treasurer."""
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        client = self._login("abusuapanin")
        view_res = client.get(f"/api/families/{self.asona.id}/funeral-expenses/")
        self.assertEqual(view_res.status_code, 200)
        self.assertEqual(len(view_res.data), 1)

        decision_res = client.post(f"/api/families/{self.asona.id}/funeral-expenses/{expense.id}/decision/", {"action": "approve"})
        self.assertEqual(decision_res.status_code, 200)
        self.assertEqual(decision_res.data["status"], "approved")

    def test_secretary_still_cannot_approve_even_though_head_now_can(self):
        """Widening approval to the head doesn't widen it to the secretary who recorded the expense."""
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        client = self._login("asona_secretary")
        res = client.post(f"/api/families/{self.asona.id}/funeral-expenses/{expense.id}/decision/", {"action": "approve"})
        self.assertEqual(res.status_code, 403)

    def test_treasurer_can_reject_with_a_reason(self):
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Extravagant flowers", seller_name="Florist",
            amount=Decimal("5000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        fund_services.reject_funeral_expense(expense=expense, actor=self.treasurer_user, reason="Too expensive — get a cheaper quote")
        expense.refresh_from_db()
        self.assertEqual(expense.status, FamilyFuneralExpense.Status.REJECTED)
        self.assertEqual(expense.rejection_reason, "Too expensive — get a cheaper quote")

    def test_cannot_approve_an_already_decided_expense_twice(self):
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02",
        )
        fund_services.approve_funeral_expense(expense=expense, actor=self.treasurer_user)
        with self.assertRaises(ValidationError):
            fund_services.approve_funeral_expense(expense=expense, actor=self.treasurer_user)

    def test_expenditure_summary_splits_by_status(self):
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02",
        )
        e2 = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Canopy", seller_name="Rentals",
            amount=Decimal("500"), date_purchased="2026-07-02",
        )
        fund_services.approve_funeral_expense(expense=e2, actor=self.treasurer_user)

        summary = fund_services.funeral_expenditure_summary(self.asona)
        self.assertEqual(Decimal(summary["pending"]["total"]), Decimal("2000"))
        self.assertEqual(Decimal(summary["approved"]["total"]), Decimal("500"))
        self.assertEqual(Decimal(summary["total_all_recorded"]), Decimal("2500"))

    def test_treasurer_committee_role_cannot_see_family_expenses(self):
        """Isolation holds for expenses the same way it does for the fund itself."""
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02",
        )
        community_treasurer = User.objects.create_user(username="committee_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        client = self._login("committee_treasurer")
        res = client.get(f"/api/families/{self.asona.id}/funeral-expenses/")
        self.assertEqual(res.status_code, 403)


class ExpenseNotificationTests(TestCase):
    """'The finance officer should oversee... to see what's going on' — real notifications, not just a status field to check manually."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin4", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin4", password="x", community=self.bodi, role=Role.FAMILY_HEAD, email="head@example.com")
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Secretary Person", gender="female", family=self.asona)
        self.secretary_user = User.objects.create_user(username="asona_secretary4", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER, email="secretary@example.com")
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary_user, actor=self.admin)
        family_services.assign_family_officer(family=self.asona, member=self.secretary_member, officer_role="secretary", actor=self.head_user)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Treasurer Person", gender="male", family=self.asona)
        self.treasurer_user = User.objects.create_user(username="asona_treasurer4", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER, email="treasurer@example.com")
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer_user, actor=self.admin)
        family_services.assign_family_officer(family=self.asona, member=self.treasurer_member, officer_role="treasurer", actor=self.head_user)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_recording_an_expense_notifies_both_treasurer_and_head(self):
        from notifications.models import Notification
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        notified_users = set(
            Notification.objects.filter(category=Notification.Category.FAMILY_EXPENSE_APPROVAL).values_list("recipient_user_id", flat=True)
        )
        self.assertIn(self.head_user.id, notified_users)
        self.assertIn(self.treasurer_user.id, notified_users)
        self.assertNotIn(self.secretary_user.id, notified_users)  # she recorded it, doesn't need a "please approve" nudge

    def test_approving_an_expense_notifies_the_secretary_who_recorded_it(self):
        from notifications.models import Notification
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        fund_services.approve_funeral_expense(expense=expense, actor=self.treasurer_user)

        decision_notifications = Notification.objects.filter(
            category=Notification.Category.FAMILY_EXPENSE_APPROVAL, recipient_user=self.secretary_user,
        )
        self.assertTrue(decision_notifications.exists())
        self.assertIn("approved", decision_notifications.first().message)

    def test_rejecting_an_expense_notifies_the_secretary_with_the_reason(self):
        from notifications.models import Notification
        expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Extravagant flowers", seller_name="Florist",
            amount=Decimal("5000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        fund_services.reject_funeral_expense(expense=expense, actor=self.head_user, reason="Too expensive")

        notification = Notification.objects.filter(
            category=Notification.Category.FAMILY_EXPENSE_APPROVAL, recipient_user=self.secretary_user,
        ).latest("created_at")
        self.assertIn("rejected", notification.message)
        self.assertIn("Too expensive", notification.message)

    def test_notifications_actually_get_delivered_via_email(self):
        from django.core import mail
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("2000"), date_purchased="2026-07-02", recorded_by=self.secretary_user,
        )
        recipient_emails = {m.to[0] for m in mail.outbox}
        self.assertIn("head@example.com", recipient_emails)
        self.assertIn("treasurer@example.com", recipient_emails)


class FamilyFinancialOverviewTests(TestCase):
    """'Abusuapanin also oversees all activities' — one combined fund-vs-spend picture."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin5", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin5", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.contributor = member_services.register_member(community=self.bodi, full_name="A Contributor", gender="female", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_net_position_only_counts_approved_expenses_not_pending(self):
        fund = fund_services.create_family_fund(family=self.asona, name="General Fund", actor=self.head_user)
        fund_services.record_fund_contribution(fund=fund, member=self.contributor, amount=Decimal("1000"))

        approved_expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC",
            amount=Decimal("300"), date_purchased="2026-07-02",
        )
        fund_services.approve_funeral_expense(expense=approved_expense, actor=self.head_user)

        # This one stays pending — must NOT reduce net_position.
        fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Extra flowers", seller_name="Florist",
            amount=Decimal("200"), date_purchased="2026-07-02",
        )

        overview = fund_services.family_financial_overview(self.asona)
        self.assertEqual(Decimal(overview["total_fund_contributions"]), Decimal("1000"))
        self.assertEqual(Decimal(overview["total_approved_expenses"]), Decimal("300"))
        self.assertEqual(Decimal(overview["total_pending_expenses"]), Decimal("200"))
        self.assertEqual(Decimal(overview["net_position"]), Decimal("700"))  # 1000 - 300, NOT -500

    def test_financial_overview_reachable_over_http_for_the_head(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "abusuapanin5", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/families/{self.asona.id}/financial-overview/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("net_position", res.data)

    def test_financial_overview_denied_to_other_familys_officers(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        bretuo_head_member = member_services.register_member(community=self.bodi, full_name="Bretuo Head", gender="male", family=bretuo)
        bretuo_head_user = User.objects.create_user(username="bretuo_head5", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=bretuo_head_member, user=bretuo_head_user, actor=self.admin)
        family_services.assign_family_head(family=bretuo, member=bretuo_head_member, actor=self.admin)

        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "bretuo_head5", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/families/{self.asona.id}/financial-overview/")
        self.assertEqual(res.status_code, 403)


class ExpenseVoucherTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin6", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin6", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.expense = fund_services.record_funeral_expense(
            family=self.asona, funeral_event=self.funeral, item_name="Coffin", seller_name="ABC Casket Co.",
            seller_contact="0244000000", amount=Decimal("2000"), date_purchased="2026-07-02",
        )

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "abusuapanin6", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_pending_expense_has_no_voucher(self):
        client = self._login()
        res = client.get(f"/api/families/{self.asona.id}/funeral-expenses/{self.expense.id}/voucher/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("No voucher available", res.data["text"])

    def test_approved_expense_voucher_shows_the_real_details(self):
        fund_services.approve_funeral_expense(expense=self.expense, actor=self.head_user)
        client = self._login()
        res = client.get(f"/api/families/{self.asona.id}/funeral-expenses/{self.expense.id}/voucher/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Coffin", res.data["text"])
        self.assertIn("ABC Casket Co.", res.data["text"])
        self.assertIn("APPROVED", res.data["text"])

    def test_pdf_voucher_rejected_for_a_pending_expense(self):
        client = self._login()
        res = client.get(f"/api/families/{self.asona.id}/funeral-expenses/{self.expense.id}/voucher/?export=pdf")
        self.assertEqual(res.status_code, 400)

    def test_pdf_voucher_downloads_once_approved(self):
        fund_services.approve_funeral_expense(expense=self.expense, actor=self.head_user)
        client = self._login()
        res = client.get(f"/api/families/{self.asona.id}/funeral-expenses/{self.expense.id}/voucher/?export=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF-"))

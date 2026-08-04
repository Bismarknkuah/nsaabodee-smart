from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funeral_logistics import services
from funeral_logistics.models import FuneralAttendance, FuneralExpense
from funerals import services as funeral_services
from gifts import services as gift_services
from members import services as member_services
from tenants.models import Community


class FuneralExpenseTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )

    def test_record_expense_generates_voucher_number(self):
        expense = services.record_expense(
            funeral=self.funeral, description="Catering for 200 guests", amount=Decimal("2000"),
            category=FuneralExpense.Category.CATERING, incurred_on="2026-07-03", recorded_by=self.admin,
        )
        self.assertTrue(expense.voucher_number.startswith("BODI-EXP-"))

    def test_expense_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            services.record_expense(
                funeral=self.funeral, description="Bad", amount=Decimal("0"),
                category=FuneralExpense.Category.OTHER, incurred_on="2026-07-03",
            )

    def test_expense_summary_groups_by_category(self):
        services.record_expense(funeral=self.funeral, description="Rice", amount=Decimal("500"),
                                 category=FuneralExpense.Category.CATERING, incurred_on="2026-07-03")
        services.record_expense(funeral=self.funeral, description="Bus hire", amount=Decimal("300"),
                                 category=FuneralExpense.Category.TRANSPORT, incurred_on="2026-07-03")
        summary = services.expense_summary(self.funeral)
        self.assertEqual(summary["expense_count"], 2)
        self.assertEqual(Decimal(summary["total_expenses"]), Decimal("800"))
        self.assertEqual(Decimal(summary["by_category"]["catering"]), Decimal("500"))

    def test_duplicate_offline_expense_is_idempotent(self):
        op_id = "33333333-3333-3333-3333-333333333333"
        e1 = services.record_expense(funeral=self.funeral, description="Coffin", amount=Decimal("1200"),
                                      category=FuneralExpense.Category.COFFIN, incurred_on="2026-07-03", client_op_id=op_id)
        e2 = services.record_expense(funeral=self.funeral, description="Coffin", amount=Decimal("1200"),
                                      category=FuneralExpense.Category.COFFIN, incurred_on="2026-07-03", client_op_id=op_id)
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(FuneralExpense.objects.filter(funeral_event=self.funeral).count(), 1)


class FuneralAttendanceTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_record_member_attendance(self):
        record = services.record_attendance(funeral=self.funeral, member=self.member)
        self.assertEqual(record.member_id, self.member.id)

    def test_record_guest_attendance(self):
        record = services.record_attendance(funeral=self.funeral, guest_name="A visiting sympathizer")
        self.assertIsNone(record.member_id)
        self.assertEqual(record.guest_name, "A visiting sympathizer")

    def test_checking_in_same_member_twice_is_a_no_op_not_an_error(self):
        r1 = services.record_attendance(funeral=self.funeral, member=self.member)
        r2 = services.record_attendance(funeral=self.funeral, member=self.member)
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(FuneralAttendance.objects.filter(funeral_event=self.funeral, member=self.member).count(), 1)

    def test_attendance_requires_member_or_guest_name(self):
        with self.assertRaises(ValidationError):
            services.record_attendance(funeral=self.funeral)

    def test_attendance_summary_counts_members_and_guests_separately(self):
        services.record_attendance(funeral=self.funeral, member=self.member)
        services.record_attendance(funeral=self.funeral, guest_name="Guest A")
        services.record_attendance(funeral=self.funeral, guest_name="Guest B")
        summary = services.attendance_summary(self.funeral)
        self.assertEqual(summary["members_attended"], 1)
        self.assertEqual(summary["guests_attended"], 2)
        self.assertIn("Guest A", summary["guest_names"])


class FinancialOverviewTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_overview_combines_all_three_pictures_without_merging_them(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Donor", amount_cash=Decimal("200"))
        services.record_expense(funeral=self.funeral, description="Catering", amount=Decimal("100"),
                                 category=FuneralExpense.Category.CATERING, incurred_on="2026-07-03")

        overview = services.funeral_financial_overview(self.funeral)
        self.assertEqual(Decimal(overview["contributions_collected"]), Decimal("50"))
        self.assertEqual(Decimal(overview["gift_cash_collected"]), Decimal("200"))
        self.assertEqual(Decimal(overview["total_expenses"]), Decimal("100"))
        self.assertEqual(Decimal(overview["net_cash_position"]), Decimal("150"))  # 50 + 200 - 100

        # And confirm the underlying ledgers are still completely independent tables:
        from gifts.models import GiftDonation
        self.assertEqual(GiftDonation.objects.filter(funeral_event=self.funeral).count(), 1)
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=self.funeral).count(), 1)
        self.assertEqual(FuneralExpense.objects.filter(funeral_event=self.funeral).count(), 1)

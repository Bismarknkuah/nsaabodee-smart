from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funeral_logistics import services as logistics_services
from funeral_logistics.models import FuneralExpense
from funerals import services as funeral_services
from gifts import services as gift_services
from members import services as member_services
from reports import receipts, services
from tenants.models import Community


class CollectionsReportTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.collector = User.objects.create_user(username="collector1", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_daily_report_totals_contributions_by_method(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector=self.collector)

        report = services.daily_report(community=self.bodi, on_date=date.today())
        self.assertEqual(report["contributions"]["count"], 1)
        self.assertEqual(Decimal(report["contributions"]["total"]), Decimal("50"))
        self.assertEqual(Decimal(report["contributions"]["by_method"]["cash"]), Decimal("50"))

    def test_gift_cash_counted_but_item_only_gift_excluded_from_cash_total(self):
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A", amount_cash=Decimal("40"),
                                            payment_method="mobile_money", collected_by=self.collector)
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="B", gift_item="Goat",
                                            estimated_item_value=Decimal("300"), collected_by=self.collector)

        report = services.daily_report(community=self.bodi, on_date=date.today())
        self.assertEqual(report["gift_cash"]["count"], 1)  # only the cash one
        self.assertEqual(Decimal(report["gift_cash"]["total"]), Decimal("40"))
        self.assertEqual(Decimal(report["gift_cash"]["by_method"]["mobile_money"]), Decimal("40"))

    def test_combined_cash_position_sums_both_ledgers_without_altering_them(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A", amount_cash=Decimal("40"), payment_method="cash")

        report = services.daily_report(community=self.bodi, on_date=date.today())
        self.assertEqual(Decimal(report["combined_cash_position_by_method"]["cash"]), Decimal("90"))

        obligation.refresh_from_db()
        self.assertEqual(obligation.amount_paid, Decimal("50"))  # untouched by the report

    def test_report_scoped_to_one_collector_excludes_others(self):
        other_collector = User.objects.create_user(username="collector2", password="x", community=self.bodi, role=Role.COLLECTOR)
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("20"), method="cash", collector=self.collector)

        # A second obligation on a second member, paid by the other collector.
        member2 = member_services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.asona)
        obligation2 = ContributionObligation.objects.get(funeral_event=self.funeral, member=member2)
        funeral_services.record_payment(obligation=obligation2, amount=Decimal("50"), method="cash", collector=other_collector)

        report = services.collector_performance_report(collector=self.collector, start_date=date.today(), end_date=date.today())
        self.assertEqual(report["contributions"]["count"], 1)
        self.assertEqual(Decimal(report["contributions"]["total"]), Decimal("20"))

    def test_monthly_report_date_range_end_of_month(self):
        report = services.monthly_report(community=self.bodi, year=2024, month=2)  # 2024 is a leap year
        self.assertEqual(report["end_date"], "2024-02-29")

    def test_expense_statement_groups_by_category(self):
        logistics_services.record_expense(funeral=self.funeral, description="Rice", amount=Decimal("500"),
                                           category=FuneralExpense.Category.CATERING, incurred_on=date.today())
        statement = services.expense_statement(community=self.bodi, start_date=date.today(), end_date=date.today())
        self.assertEqual(statement["expense_count"], 1)
        self.assertEqual(Decimal(statement["total"]), Decimal("500"))


class FamilyStatementTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.asona_member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.bretuo)

    def test_family_statement_separates_own_family_vs_outsider_obligations(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        statement = services.family_statement(self.asona)
        # Asona members owe the own-family rate for this funeral (they're the deceased's family).
        self.assertEqual(statement["as_deceaseds_family"]["obligation_count"], 1)
        self.assertEqual(Decimal(statement["as_deceaseds_family"]["expected_total"]), Decimal("50"))
        # Asona has no members owing as outsiders anywhere yet.
        self.assertEqual(statement["members_as_outsiders_elsewhere"]["obligation_count"], 0)


class ReceiptTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_contribution_receipt_data_has_every_required_field(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector=self.admin)

        data = receipts.contribution_receipt_data(payment)
        for field in ["receipt_number", "member_name", "membership_number", "family_name",
                      "amount", "payment_method", "funeral_deceased_name", "date", "time"]:
            self.assertIn(field, data)
        self.assertEqual(data["member_name"], "Kojo Mensah")
        self.assertEqual(Decimal(data["amount"]), Decimal("50"))

    def test_contribution_receipt_text_is_printable_plain_text(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        text = receipts.contribution_receipt_text(payment, self.bodi.name)
        self.assertIn("Kojo Mensah", text)
        self.assertIn("GHS 50", text)
        self.assertIsInstance(text, str)

    def test_gift_receipt_data_and_text(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Kind Donor", gift_item="A cow", estimated_item_value=Decimal("800"),
        )
        data = receipts.gift_receipt_data(donation)
        self.assertEqual(data["donor_name"], "A Kind Donor")
        self.assertEqual(Decimal(data["total_value"]), Decimal("800"))

        text = receipts.gift_receipt_text(donation, self.bodi.name)
        self.assertIn("A Kind Donor", text)
        self.assertIn("A cow", text)


class MyReceiptsAndDeliveryChannelTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(
            username="kojo_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER
        )
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_cash_payment_is_classified_physical(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        self.assertEqual(receipts.contribution_receipt_data(payment)["delivery_channel"], "physical")

    def test_momo_payment_is_classified_electronic(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="mobile_money")
        self.assertEqual(receipts.contribution_receipt_data(payment)["delivery_channel"], "electronic")

    def test_gift_cash_physical_gift_item_electronic(self):
        cash_gift = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A", amount_cash=Decimal("20"), payment_method="cash")
        item_gift = gift_services.record_gift_donation(funeral=self.funeral, donor_name="B", gift_item="Yam",
                                                         estimated_item_value=Decimal("30"))
        self.assertEqual(receipts.gift_receipt_data(cash_gift)["delivery_channel"], "physical")
        self.assertEqual(receipts.gift_receipt_data(item_gift)["delivery_channel"], "electronic")

    def test_unlinked_user_gets_empty_receipts_not_an_error(self):
        result = services.my_receipts(user=self.member_user)
        self.assertFalse(result["has_member_profile"])
        self.assertEqual(result["receipts"], [])

    def test_linked_user_sees_both_their_payments_and_gifts_they_gave(self):
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)

        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("20"), method="cash")
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Kojo Mensah", donor_member=self.member,
            amount_cash=Decimal("10"), payment_method="mobile_money",
        )

        result = services.my_receipts(user=self.member_user)
        self.assertTrue(result["has_member_profile"])
        self.assertEqual(len(result["receipts"]), 2)
        ledgers = {r["ledger"] for r in result["receipts"]}
        self.assertEqual(ledgers, {"contribution", "gift"})
        channels = {r["delivery_channel"] for r in result["receipts"]}
        self.assertEqual(channels, {"physical", "electronic"})

    def test_receipt_appears_in_dashboard_regardless_of_who_else_paid_on_the_funeral(self):
        """Cash-paying members still get their receipt in the dashboard too — not only momo payers."""
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        result = services.my_receipts(user=self.member_user)
        self.assertEqual(len(result["receipts"]), 1)
        self.assertEqual(result["receipts"][0]["delivery_channel"], "physical")


class PrintTrackingTests(TestCase):
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

    def test_cash_payment_starts_unprinted_and_appears_in_unprinted_list(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        self.assertIsNone(payment.printed_at)

        unprinted = services.unprinted_receipts(community=self.bodi)
        self.assertEqual(len(unprinted["unprinted_contribution_payments"]), 1)
        self.assertEqual(unprinted["unprinted_contribution_payments"][0]["payment_id"], str(payment.id))

    def test_marking_printed_removes_it_from_the_unprinted_list(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        services.mark_contribution_receipt_printed(payment=payment)
        payment.refresh_from_db()
        self.assertIsNotNone(payment.printed_at)

        unprinted = services.unprinted_receipts(community=self.bodi)
        self.assertEqual(len(unprinted["unprinted_contribution_payments"]), 0)

    def test_marking_printed_twice_is_safe(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        services.mark_contribution_receipt_printed(payment=payment)
        first_timestamp = payment.printed_at
        services.mark_contribution_receipt_printed(payment=payment)
        payment.refresh_from_db()
        self.assertIsNotNone(payment.printed_at)
        self.assertGreaterEqual(payment.printed_at, first_timestamp)

    def test_electronic_payment_never_appears_in_unprinted_list(self):
        """Momo/bank payments were never meant to be printed — they should never show up as 'needs printing'."""
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="mobile_money")

        unprinted = services.unprinted_receipts(community=self.bodi)
        self.assertEqual(len(unprinted["unprinted_contribution_payments"]), 0)

    def test_gift_cash_donation_tracked_separately_from_contribution_payments(self):
        donation = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Donor", amount_cash=Decimal("40"))
        unprinted = services.unprinted_receipts(community=self.bodi)
        self.assertEqual(len(unprinted["unprinted_gift_donations"]), 1)

        services.mark_gift_receipt_printed(donation=donation)
        unprinted_after = services.unprinted_receipts(community=self.bodi)
        self.assertEqual(len(unprinted_after["unprinted_gift_donations"]), 0)

    def test_item_only_gift_never_appears_in_unprinted_list(self):
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A", gift_item="A cow", estimated_item_value=Decimal("800"))
        unprinted = services.unprinted_receipts(community=self.bodi)
        self.assertEqual(len(unprinted["unprinted_gift_donations"]), 0)

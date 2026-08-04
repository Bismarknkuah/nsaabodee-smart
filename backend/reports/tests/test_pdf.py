from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from members import services as member_services
from reports import pdf, receipts, services
from tenants.models import Community


class PdfGenerationTests(TestCase):
    """
    These don't parse the PDF back into text (that would need an extra
    dependency this project doesn't otherwise need) — they check the
    thing actually IS a PDF (starts with the %PDF magic bytes, ends with
    %%EOF, and is a plausible size), which is what matters for "does this
    download work when a browser opens it".
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
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def _assert_is_pdf(self, content: bytes):
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", content[-1024:])
        self.assertGreater(len(content), 500)

    def test_contribution_receipt_pdf_is_a_valid_pdf(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector=self.admin)

        data = receipts.contribution_receipt_data(payment)
        content = pdf.contribution_receipt_pdf(data, self.bodi.name)
        self._assert_is_pdf(content)

    def test_contribution_receipt_pdf_handles_missing_collector_and_family(self):
        # A payment with no collector recorded, and a member with no family,
        # are both real states the platform allows — the PDF must not crash on them.
        member_no_family = member_services.register_member(community=self.bodi, full_name="No Family Guy", gender="male")
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=member_no_family)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash")

        data = receipts.contribution_receipt_data(payment)
        content = pdf.contribution_receipt_pdf(data, self.bodi.name)
        self._assert_is_pdf(content)

    def test_gift_receipt_pdf_cash_only(self):
        donation = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Donor", amount_cash=Decimal("100"))
        data = receipts.gift_receipt_data(donation)
        content = pdf.gift_receipt_pdf(data, self.bodi.name)
        self._assert_is_pdf(content)

    def test_gift_receipt_pdf_item_only(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Donor", gift_item="A cow", estimated_item_value=Decimal("800")
        )
        data = receipts.gift_receipt_data(donation)
        content = pdf.gift_receipt_pdf(data, self.bodi.name)
        self._assert_is_pdf(content)

    def test_gift_receipt_pdf_mixed_cash_and_item(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Donor", amount_cash=Decimal("50"),
            gift_item="Rice", estimated_item_value=Decimal("120"),
        )
        data = receipts.gift_receipt_data(donation)
        content = pdf.gift_receipt_pdf(data, self.bodi.name)
        self._assert_is_pdf(content)

    def test_collections_report_pdf_with_zero_activity(self):
        # No payments recorded at all yet — every total is zero. Must still render.
        import datetime
        report = services.daily_report(community=self.bodi, on_date=datetime.date.today())
        content = pdf.collections_report_pdf(report, self.bodi.name, "Today")
        self._assert_is_pdf(content)

    def test_collections_report_pdf_with_activity(self):
        import datetime
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A", amount_cash=Decimal("20"), payment_method="mobile_money")

        report = services.daily_report(community=self.bodi, on_date=datetime.date.today())
        content = pdf.collections_report_pdf(report, self.bodi.name, "Today")
        self._assert_is_pdf(content)

    def test_family_statement_pdf(self):
        statement = services.family_statement(self.asona)
        content = pdf.family_statement_pdf(statement, self.bodi.name)
        self._assert_is_pdf(content)

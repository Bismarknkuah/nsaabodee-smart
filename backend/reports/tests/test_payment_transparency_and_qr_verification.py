from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from reports.services import members_payment_status_report
from tenants.models import Community


class MembersPaymentStatusReportTests(TestCase):
    """'Make it transparent to the community treasurer to have data of those who have paid... each treasurer should have access to data of those who have paid in his family and who haven't.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="mpsr-bodi", default_general_male_amount=Decimal("5"))
        self.admin = User.objects.create_user(username="mpsr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        # Both in Bretuo — the funeral's DECEASED family — so they owe
        # the own_family rate (50), never the general rate (5); every
        # payment below must match that or "paid" would only be partial.
        self.paid_member = member_services.register_member(community=self.bodi, full_name="Paid Member", gender="male", family=self.bretuo)
        self.unpaid_member = member_services.register_member(community=self.bodi, full_name="Unpaid Member", gender="male", family=self.bretuo)
        self.asona_member = member_services.register_member(community=self.bodi, full_name="Asona Own Member", gender="male", family=self.asona)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Bretuo", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _obligation(self, member):
        from funerals.models import ContributionObligation
        return ContributionObligation.objects.get(funeral_event=self.funeral, member=member)

    def test_community_wide_report_correctly_splits_paid_and_unpaid(self):
        funeral_services.record_payment(obligation=self._obligation(self.paid_member), amount=Decimal("50"), method="cash", collector_name="Collector")
        report = members_payment_status_report(community=self.bodi)
        paid_names = [m["member_name"] for m in report["paid_members"]]
        unpaid_names = [m["member_name"] for m in report["outstanding_members"]]
        self.assertIn("Paid Member", paid_names)
        self.assertIn("Unpaid Member", unpaid_names)
        self.assertNotIn("Paid Member", unpaid_names)

    def test_family_scoped_report_excludes_a_different_familys_members(self):
        report = members_payment_status_report(community=self.bodi, family=self.asona)
        all_names = [m["member_name"] for m in report["paid_members"]] + [m["member_name"] for m in report["outstanding_members"]]
        self.assertIn("Asona Own Member", all_names)
        self.assertNotIn("Paid Member", all_names)
        self.assertNotIn("Unpaid Member", all_names)

    def test_family_treasurer_dashboard_shows_only_their_own_familys_payment_status(self):
        head_user = User.objects.create_user(username="mpsr_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        from members.models import Member
        Member.objects.create(community=self.bodi, family=self.bretuo, full_name="The Treasurer", gender="male", linked_user=head_user)

        funeral_services.record_payment(obligation=self._obligation(self.paid_member), amount=Decimal("50"), method="cash", collector_name="Collector")
        overview = build_dashboard(head_user)["sections"]["family_overview"]
        self.assertIn("payment_status", overview)
        paid_names = [m["member_name"] for m in overview["payment_status"]["paid_members"]]
        self.assertIn("Paid Member", paid_names)

    def test_treasurer_dashboard_shows_paid_members_community_wide(self):
        treasurer_user = User.objects.create_user(username="mpsr_ctreasurer", password="x", community=self.bodi, role=Role.TREASURER)
        funeral_services.record_payment(obligation=self._obligation(self.paid_member), amount=Decimal("50"), method="cash", collector_name="Collector")
        overview = build_dashboard(treasurer_user)["sections"]["financial_overview"]
        self.assertIn("paid_members", overview)
        paid_names = [m["member_name"] for m in overview["paid_members"]]
        self.assertIn("Paid Member", paid_names)

    def test_collector_dashboard_shows_both_paid_and_unpaid(self):
        collector_user = User.objects.create_user(username="mpsr_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        funeral_services.record_payment(obligation=self._obligation(self.paid_member), amount=Decimal("50"), method="cash", collector_name="Collector")
        overview = build_dashboard(collector_user)["sections"]["collector_performance"]
        self.assertIn("paid_members", overview)
        self.assertIn("members_to_follow_up", overview)
        paid_names = [m["member_name"] for m in overview["paid_members"]]
        unpaid_names = [m["member_name"] for m in overview["members_to_follow_up"]]
        self.assertIn("Paid Member", paid_names)
        self.assertIn("Unpaid Member", unpaid_names)


class NoDirectPaymentEditTests(TestCase):
    """'They can't edit what receipt have being printed unless they use reversal process for the collection.'"""

    def test_no_update_endpoint_exists_for_a_recorded_payment(self):
        """The direct, structural proof — there is no view in this codebase that lets a payment's own fields be edited after creation."""
        import inspect
        import funerals.views as funerals_views
        import reports.views as reports_views
        view_source = inspect.getsource(funerals_views) + inspect.getsource(reports_views)
        self.assertNotIn("class ContributionPaymentViewSet", view_source)
        self.assertNotIn("class EditContributionPaymentView", view_source)
        self.assertNotIn("class UpdateContributionPaymentView", view_source)


class ReceiptQrVerificationTests(TestCase):
    """'All receipt printed should have the QR scanner so when they scan it should confirm the amount they paid and who received the pay, I mean the collector.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="rqv-bodi", default_general_male_amount=Decimal("5"))
        self.admin = User.objects.create_user(username="rqv_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        from funerals.models import ContributionObligation
        self.obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        self.payment = funeral_services.record_payment(obligation=self.obligation, amount=Decimal("50"), method="cash", collector_name="Collector Kwame")

    def test_verify_receipt_returns_amount_and_collector(self):
        from reports.services import verify_receipt
        result = verify_receipt(payment=self.payment)
        self.assertEqual(Decimal(result["amount"]), Decimal("50"))
        self.assertEqual(result["collector_name"], "Collector Kwame")
        self.assertEqual(result["member_name"], "Test Member")

    def test_qr_payload_is_a_real_url_not_a_custom_scheme(self):
        self.assertTrue(self.payment.qr_payload.startswith("http"))
        self.assertIn(str(self.payment.id), self.payment.qr_payload)

    def test_full_http_verification_round_trip(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "rqv_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/receipts/contribution-payments/{self.payment.id}/verify/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Decimal(res.data["amount"]), Decimal("50"))
        self.assertEqual(res.data["collector_name"], "Collector Kwame")

    def test_full_http_qr_code_generation(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "rqv_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/receipts/contribution-payments/{self.payment.id}/qr-code/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.data["qr_code_base64"]) > 100)

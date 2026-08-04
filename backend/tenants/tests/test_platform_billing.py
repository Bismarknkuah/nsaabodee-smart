from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import Community, PlatformBillingRecord


class PlatformBillingServiceTests(TestCase):
    """
    'The system must clearly separate platform service fees from
    community funds. Subscription payments belong to the platform,
    while funeral contributions and donations always belong to the
    respective community or bereaved family.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-billing")
        self.platform_admin = User.objects.create_superuser(username="root_billing", password="x")
        self.community_admin = User.objects.create_user(username="bodi_billing_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_admin = User.objects.create_user(
            username="other_billing_admin", password="x",
            community=Community.objects.create(name="Other Town", slug="other-billing"), role=Role.COMMUNITY_ADMIN,
        )

    def test_platform_admin_can_create_a_billing_record(self):
        record = services.create_billing_record(community=self.bodi, description="5-day Single Funeral access", amount=Decimal("50"), actor=self.platform_admin)
        self.assertEqual(record.status, PlatformBillingRecord.Status.UNPAID)

    def test_a_community_admin_cannot_create_their_own_billing_record(self):
        """Exactly like a customer doesn't write their own invoice."""
        with self.assertRaises(ValidationError):
            services.create_billing_record(community=self.bodi, description="Trying to bill myself", amount=Decimal("50"), actor=self.community_admin)

    def test_a_zero_or_negative_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.create_billing_record(community=self.bodi, description="Free?", amount=Decimal("0"), actor=self.platform_admin)

    def test_marking_a_record_paid(self):
        record = services.create_billing_record(community=self.bodi, description="Monthly subscription", amount=Decimal("100"), actor=self.platform_admin)
        updated = services.mark_billing_record_paid(record=record, actor=self.platform_admin, payment_reference="MOMO-REF-12345")
        self.assertEqual(updated.status, PlatformBillingRecord.Status.PAID)
        self.assertEqual(updated.payment_reference, "MOMO-REF-12345")
        self.assertEqual(updated.marked_paid_by, self.platform_admin)

    def test_a_community_admin_cannot_mark_their_own_record_paid(self):
        record = services.create_billing_record(community=self.bodi, description="Fee", amount=Decimal("50"), actor=self.platform_admin)
        with self.assertRaises(ValidationError):
            services.mark_billing_record_paid(record=record, actor=self.community_admin)

    def test_cannot_mark_an_already_decided_record_paid_again(self):
        record = services.create_billing_record(community=self.bodi, description="Fee", amount=Decimal("50"), actor=self.platform_admin)
        services.mark_billing_record_paid(record=record, actor=self.platform_admin)
        with self.assertRaises(ValidationError):
            services.mark_billing_record_paid(record=record, actor=self.platform_admin)

    def test_waiving_a_record(self):
        record = services.create_billing_record(community=self.bodi, description="Fee", amount=Decimal("50"), actor=self.platform_admin)
        updated = services.waive_billing_record(record=record, actor=self.platform_admin)
        self.assertEqual(updated.status, PlatformBillingRecord.Status.WAIVED)

    def test_a_communitys_own_admin_can_view_their_own_billing_records(self):
        services.create_billing_record(community=self.bodi, description="Fee", amount=Decimal("50"), actor=self.platform_admin)
        records = services.list_billing_records_for_viewing(community=self.bodi, actor=self.community_admin)
        self.assertEqual(len(records), 1)

    def test_a_different_communitys_admin_cannot_view_this_communitys_billing_records(self):
        services.create_billing_record(community=self.bodi, description="Fee", amount=Decimal("50"), actor=self.platform_admin)
        with self.assertRaises(ValidationError):
            services.list_billing_records_for_viewing(community=self.bodi, actor=self.other_admin)

    def test_platform_billing_is_never_mixed_with_the_communitys_own_contribution_ledger(self):
        """The core of the whole requirement: creating a platform billing record must never touch, appear in, or affect the community's own funeral/contribution totals."""
        from families import services as family_services
        from funerals import services as funeral_services
        from members.models import Member

        asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.community_admin)
        member = Member.objects.create(community=self.bodi, family=asona, full_name="Kojo", gender="male")
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.community_admin, own_family_amount=Decimal("50"),
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")

        # A large platform billing record now exists for this community too.
        services.create_billing_record(community=self.bodi, description="Annual subscription", amount=Decimal("5000"), actor=self.platform_admin)

        # The community's own contribution total must be completely unaffected by that platform billing record's existence.
        obligation.refresh_from_db()
        self.assertEqual(obligation.amount_paid, Decimal("50"))
        summary = funeral_services.funeral_summary(funeral)
        self.assertNotIn("platform", str(summary).lower())


class PlatformBillingHttpTests(TestCase):
    """
    Also specifically proves the real bug found and fixed this session:
    a NameError on DjangoValidationError inside these exact views' except
    blocks, which no earlier test had ever actually triggered because
    none exercised a genuine FAILURE path through this HTTP layer.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-billing-http")
        self.platform_admin = User.objects.create_superuser(username="root_billing_http", password="a-real-password-123")
        self.community_admin = User.objects.create_user(username="bodi_billing_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_create_then_mark_paid_flow_via_http(self):
        admin_client = self._login("root_billing_http")
        create_res = admin_client.post(f"/api/tenants/communities/{self.bodi.id}/billing-records/", {
            "description": "5-day Single Funeral access", "amount": "50.00",
        })
        self.assertEqual(create_res.status_code, 201)
        record_id = create_res.data["id"]

        mark_paid_res = admin_client.post(f"/api/tenants/communities/{self.bodi.id}/billing-records/{record_id}/mark-paid/", {"payment_reference": "BANK-REF-999"})
        self.assertEqual(mark_paid_res.status_code, 200)
        self.assertEqual(mark_paid_res.data["status"], "paid")

    def test_this_is_the_bug_this_session_actually_found_a_community_admin_trying_to_waive_a_record_gets_a_clean_403_not_a_500(self):
        """
        THIS is the exact failure path that was broken: WaiveBillingRecordView's
        own `except DjangoValidationError` block referenced a name that was
        never actually imported at module level, so a genuine
        ValidationError raised inside it would have crashed with an
        unhandled NameError (a 500) instead of returning the intended,
        clean 403. Fixed by adding the real top-level import; this test
        proves the fix by deliberately triggering that exact path.
        """
        admin_client = self._login("root_billing_http")
        create_res = admin_client.post(f"/api/tenants/communities/{self.bodi.id}/billing-records/", {"description": "Fee", "amount": "50.00"})
        record_id = create_res.data["id"]

        community_client = self._login("bodi_billing_http_admin")
        res = community_client.post(f"/api/tenants/communities/{self.bodi.id}/billing-records/{record_id}/waive/")
        self.assertEqual(res.status_code, 403)
        self.assertIn("platform administrator", str(res.data).lower())

    def test_community_admin_can_view_but_not_mark_paid(self):
        admin_client = self._login("root_billing_http")
        create_res = admin_client.post(f"/api/tenants/communities/{self.bodi.id}/billing-records/", {"description": "Fee", "amount": "50.00"})
        record_id = create_res.data["id"]

        community_client = self._login("bodi_billing_http_admin")
        view_res = community_client.get(f"/api/tenants/communities/{self.bodi.id}/billing-records/")
        self.assertEqual(view_res.status_code, 200)
        self.assertEqual(len(view_res.data), 1)

        mark_paid_res = community_client.post(f"/api/tenants/communities/{self.bodi.id}/billing-records/{record_id}/mark-paid/")
        self.assertEqual(mark_paid_res.status_code, 400)  # rejected by the serializer's save(), a clean validation error, not a crash

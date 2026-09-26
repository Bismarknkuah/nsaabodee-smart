from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from tenants.models import Community


class RecordPaymentsAcrossActiveFuneralsTests(TestCase):
    """
    'Sometimes there can be more than two funerals and the collectors
    have to key their payment into the system — since it's a community
    ledger, community members are mandatory to pay all — so the system
    should be more efficient and friendly, so it can be faster.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-batch-payments",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="batch_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        # The paying member is in a third family, so they're a genuine
        # outside contributor to both funerals, not the deceased's own
        # family either time (which pays a different, non-own_family rate).
        self.contributor_family = family_services.create_family(community=self.bodi, name="Contributor Family", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kwabena Mensah", gender="male", family=self.contributor_family)

        self.older_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Older Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-06-01", collection_start_date="2026-06-01",
            own_family_amount=Decimal("10"),
        )
        self.newer_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Newer Deceased", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            own_family_amount=Decimal("10"),
        )

    def test_settles_every_outstanding_obligation_across_active_funerals(self):
        payments = funeral_services.record_payments_across_active_funerals(
            member=self.member, method="cash", collector_name="Test Collector",
        )
        self.assertEqual(len(payments), 2)

        older_obligation = ContributionObligation.objects.get(funeral_event=self.older_funeral, member=self.member)
        newer_obligation = ContributionObligation.objects.get(funeral_event=self.newer_funeral, member=self.member)
        self.assertEqual(older_obligation.balance, Decimal("0"))
        self.assertEqual(newer_obligation.balance, Decimal("0"))

    def test_processes_oldest_funeral_first_so_debt_priority_never_blocks_a_sibling_payment(self):
        """The exact reason for the ordering — without it, the newer funeral's payment would trip the debt-priority check against the older one, from within the very same batch."""
        payments = funeral_services.record_payments_across_active_funerals(
            member=self.member, method="cash", collector_name="Test Collector",
        )
        self.assertEqual(payments[0].obligation.funeral_event_id, self.older_funeral.id)
        self.assertEqual(payments[1].obligation.funeral_event_id, self.newer_funeral.id)

    def test_a_fully_paid_member_gets_an_empty_list_not_an_error(self):
        funeral_services.record_payments_across_active_funerals(member=self.member, method="cash", collector_name="Test Collector")
        second_call = funeral_services.record_payments_across_active_funerals(member=self.member, method="cash", collector_name="Test Collector")
        self.assertEqual(second_call, [])

    def test_a_closed_funeral_is_never_included(self):
        closed_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Closed Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-01-01", collection_start_date="2026-01-01",
            own_family_amount=Decimal("10"),
        )
        closed_obligation = ContributionObligation.objects.get(funeral_event=closed_funeral, member=self.member)
        funeral_services.record_payment(obligation=closed_obligation, amount=closed_obligation.expected_amount, method="cash", collector_name="Test Collector")
        closed_funeral.status = "closed"
        closed_funeral.save(update_fields=["status"])

        payments = funeral_services.record_payments_across_active_funerals(member=self.member, method="cash", collector_name="Test Collector")
        funeral_ids = {p.obligation.funeral_event_id for p in payments}
        self.assertNotIn(closed_funeral.id, funeral_ids)

    def test_wallet_method_is_rejected_the_same_way_as_a_single_payment(self):
        with self.assertRaises(ValidationError):
            funeral_services.record_payments_across_active_funerals(member=self.member, method="wallet", collector_name="Test Collector")

    def test_full_http_round_trip(self):
        User.objects.create_user(username="batch_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "batch_collector", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post(
            "/api/members/record-payments-across-active-funerals/",
            {"member_id": str(self.member.id), "method": "cash", "collector_name": "HTTP Test Collector"},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data), 2)

    def test_a_plain_member_cannot_use_this_endpoint(self):
        plain_member = member_services.register_member(community=self.bodi, full_name="Plain Member", gender="male", family=self.contributor_family)
        plain_user = User.objects.create_user(username="batch_plain_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=plain_member, user=plain_user, actor=self.admin)

        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "batch_plain_member", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            "/api/members/record-payments-across-active-funerals/",
            {"member_id": str(self.member.id), "method": "cash", "collector_name": "Shouldn't work"},
        )
        self.assertEqual(res.status_code, 403)

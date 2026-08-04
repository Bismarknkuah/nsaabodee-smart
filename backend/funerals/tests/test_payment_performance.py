import time
from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class PaymentRecordingPerformanceTests(TestCase):
    """
    'Thousands plus will be paid within 6 hours each day during funeral
    time' — this can't be a real load test in this sandbox (no way to
    simulate concurrent network traffic here), but it CAN honestly check
    the one thing a sandbox test *can* catch: that recording a payment
    doesn't do something egregiously slow like an N+1 query per
    obligation. A bounded timing assertion, not a claim about real
    production throughput.
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

        self.members = [
            member_services.register_member(community=self.bodi, full_name=f"Member {i}", gender="male", family=self.asona)
            for i in range(200)
        ]
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_recording_a_single_payment_uses_a_bounded_number_of_queries(self):
        """A single payment should be a small, fixed number of queries — never one that grows with the number of members."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.members[0])

        # Observed at 7 queries in practice — asserting <=10 (an upper
        # bound, not an exact match) so a legitimate small addition later
        # doesn't break this test, while still catching a genuine N+1
        # regression (which would blow this budget by many multiples).
        with CaptureQueriesContext(connection) as ctx:
            funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        self.assertLessEqual(len(ctx.captured_queries), 10, "More queries than expected for a single payment — check for an N+1.")

    def test_recording_200_payments_completes_quickly(self):
        from funerals.models import ContributionObligation
        obligations = list(ContributionObligation.objects.filter(funeral_event=self.funeral).select_related("member"))

        start = time.perf_counter()
        for obligation in obligations:
            funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        elapsed = time.perf_counter() - start

        average_ms = (elapsed / len(obligations)) * 1000
        # A generous bound for this sandbox's shared/throttled CPU — the
        # real claim here is "no obvious O(n) blowup," not a production
        # throughput guarantee. 50ms/payment sequentially would already
        # be ~3 seconds for 200 members; thousands of REAL payments
        # across many collectors' phones in parallel is a genuinely
        # different (and better) situation than one process doing them
        # one after another, which is all a sandbox can measure honestly.
        self.assertLess(average_ms, 50, f"Average {average_ms:.1f}ms/payment — investigate for an N+1 query.")

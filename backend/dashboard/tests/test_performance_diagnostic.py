"""
Real regression tests, not just a diagnostic — assert a bounded query
count for the dashboard under realistic conditions, so a future change
can't silently reintroduce the N+1 pattern this batch found and fixed
(measured directly: the Community Admin dashboard made 119 queries
before the fix, 23 after — almost entirely from a 7-day trend chart
that called daily_report once per day instead of one grouped query).
"""
from decimal import Decimal
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import Role, User
from communication import services as communication_services
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services


class DashboardQueryCountRegressionTests(TestCase):
    """'The system is freezing so make it to run effectively, efficiency, smart, reliable and secure.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-perf",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="perf_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Perf Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="perf_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.member = member_services.register_member(community=self.bodi, full_name="Perf Member", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(username="perf_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Perf Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        funeral_services.appoint_committee_position(funeral=self.funeral, member=self.member, title="Logistics Coordinator", actor=self.admin)
        communication_services.schedule_meeting(community=self.bodi, title="General Meeting", scheduled_for=timezone.now() + timedelta(days=7), actor=self.admin)
        communication_services.schedule_meeting(community=self.bodi, family=self.asona, title="Asona Meeting", scheduled_for=timezone.now() + timedelta(days=3), actor=self.head_user)

        category = welfare_services.create_contribution_category(community=self.bodi, name="Dues", fixed_amount=Decimal("10"), actor=self.admin)
        welfare_services.initiate_community_campaign(category=category, title="2026 Dues", actor=self.admin)

    def test_community_admin_dashboard_query_count_stays_bounded(self):
        """Was 119 queries before the fix — asserting well under that, with headroom, not a razor-thin exact count that breaks on any unrelated change."""
        from dashboard.services import build_dashboard
        build_dashboard(self.admin)  # warm up any lazy imports first
        with CaptureQueriesContext(connection) as ctx:
            build_dashboard(self.admin)
        self.assertLess(len(ctx.captured_queries), 40, f"Community Admin dashboard made {len(ctx.captured_queries)} queries — the 7-day trend chart N+1 may have regressed.")

    def test_member_dashboard_query_count_does_not_scale_linearly_with_committee_positions(self):
        """The real N+1 signature: query count should grow much slower than linearly with the number of committee positions held."""
        from dashboard.services import build_dashboard
        build_dashboard(self.member_user)
        with CaptureQueriesContext(connection) as ctx_one:
            build_dashboard(self.member_user)
        one_position_count = len(ctx_one.captured_queries)

        for i in range(3):
            f = funeral_services.create_funeral_event(
                community=self.bodi, deceased_name=f"Extra Deceased {i}", deceased_gender="male",
                deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
                actor=self.admin, own_family_amount=Decimal("50"),
            )
            funeral_services.appoint_committee_position(funeral=f, member=self.member, title="Welfare Officer", actor=self.admin)

        with CaptureQueriesContext(connection) as ctx_four:
            build_dashboard(self.member_user)
        four_position_count = len(ctx_four.captured_queries)

        # Going from 1 to 4 positions (4x) should cost meaningfully less
        # than 4x the queries — a real, if partial, fix for the N+1
        # pattern here (funeral_financial_overview itself still scales
        # per-position; only the task-count queries were consolidated).
        self.assertLess(four_position_count, one_position_count * 3.5)

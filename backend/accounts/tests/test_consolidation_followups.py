from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import FuneralDeskAssignment
from members import services as member_services
from members.models import CollectorNomination
from notifications.models import Notification
from notifications.services import notify_treasurers
from tenants.models import Community


class ConsolidationFollowUpTests(TestCase):
    """
    When the Treasurer merged into the Financial Secretary, every place that still named only
    "treasurer" quietly became unreachable. These are the ones the audit found.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="cfu-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="cfu_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chair = User.objects.create_user(username="cfu_chair", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="cfu_sec", password="x", community=self.bodi, role=Role.SECRETARY)
        self.fin = User.objects.create_user(username="cfu_fin", password="x", community=self.bodi, role=Role.FINANCIAL_SECRETARY)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

    def test_a_community_collector_nomination_can_be_fully_approved_by_the_financial_secretary(self):
        """It used to wait on a 'treasurer' that no one can hold any more, so it could never complete."""
        member = member_services.register_member(community=self.bodi, full_name="Kofi Collector", gender="male", family=self.asona)
        nomination = member_services.nominate_collector(member=member, collector_type="general", actor=self.chair)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.fin, decision="approve")
        member_services.decide_collector_nomination(nomination=nomination, actor=self.secretary, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, CollectorNomination.Status.APPROVED)

    def test_the_financial_secretary_may_open_a_contributions_desk(self):
        funeral = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Deceased", deceased_gender="male", deceased_family=self.asona, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)
        self.assertTrue(funeral_services._can_assign_desk_workers_for(self.fin, funeral, FuneralDeskAssignment.DeskType.COMMUNITY))
        self.assertFalse(funeral_services._can_assign_desk_workers_for(self.secretary, funeral, FuneralDeskAssignment.DeskType.COMMUNITY))

    def test_a_defaulter_escalation_reaches_the_financial_secretary(self):
        member = member_services.register_member(community=self.bodi, full_name="Slow Payer", gender="male", family=self.asona)
        notify_treasurers(community=self.bodi, member=member, message="has missed several contributions")
        roles = set(Notification.objects.filter(related_member=member).values_list("recipient_role", flat=True))
        self.assertIn(Role.FINANCIAL_SECRETARY, roles)

    def test_the_auditor_reads_but_can_never_record_or_decide(self):
        """Why the Auditor is not merged into the Financial Secretary."""
        from funeral_logistics.permissions import EXPENSE_ROLES, EXPENSE_VIEWING_ROLES
        self.assertNotIn(Role.AUDITOR, EXPENSE_ROLES)
        self.assertIn(Role.AUDITOR, EXPENSE_VIEWING_ROLES)
        self.assertIn(Role.FINANCIAL_SECRETARY, EXPENSE_ROLES)

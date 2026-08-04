from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from members.models import Member
from tenants.models import Community


class PaymentRecordingRestrictionTests(TestCase):
    """
    'Apart from collectors/frontdesk officer no officer should record
    payment or make payment, unless they are paying for themselves as
    each usertype also a community member.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-payment-restrict",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin_actor = User.objects.create_user(username="restrict_setup_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin_actor)

        self.other_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Someone Else", gender="male")

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin_actor, own_family_amount=Decimal("50"),
        )
        self.other_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.other_member)

    def _login(self, username, password="a-real-password-123"):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": password})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_a_collector_can_still_record_a_payment_for_someone_else(self):
        User.objects.create_user(username="restrict_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        client = self._login("restrict_collector")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash"})
        self.assertEqual(res.status_code, 201)

    def test_treasurer_can_no_longer_record_a_payment_for_someone_else(self):
        """The core of the change: this used to be allowed, and now correctly isn't."""
        User.objects.create_user(username="restrict_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        client = self._login("restrict_treasurer")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash"})
        self.assertEqual(res.status_code, 403)

    def test_community_admin_can_no_longer_record_a_payment_for_someone_else(self):
        client = self._login("restrict_setup_admin")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash"})
        self.assertEqual(res.status_code, 403)

    def test_any_role_can_still_pay_their_own_obligation(self):
        """The actual exception this change adds: self-payment works regardless of role — a Treasurer, a Chairman, anyone, paying THEIR OWN contribution."""
        own_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Treasurer As Member", gender="male")
        treasurer_user = User.objects.create_user(username="self_pay_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        member_services.link_member_to_user(member=own_member, user=treasurer_user, actor=self.admin_actor)
        own_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=own_member)

        client = self._login("self_pay_treasurer")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{own_obligation.id}/record-payment/", {"amount": "20", "method": "cash"})
        self.assertEqual(res.status_code, 201)

    def test_self_payment_exception_cannot_be_used_to_pay_someone_elses_obligation(self):
        """The exception is checked against the SPECIFIC obligation, not a blanket 'has a member profile' grant."""
        own_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Financial Sec As Member", gender="female")
        fs_user = User.objects.create_user(username="self_pay_fs", password="a-real-password-123", community=self.bodi, role=Role.FINANCIAL_SECRETARY)
        member_services.link_member_to_user(member=own_member, user=fs_user, actor=self.admin_actor)

        client = self._login("self_pay_fs")
        # Trying to pay the OTHER member's obligation, not their own.
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash"})
        self.assertEqual(res.status_code, 403)

    def test_a_desk_assigned_worker_can_still_record_payments_for_others_regardless_of_role(self):
        """The existing desk-assignment capability system is untouched by this change."""
        member_user = User.objects.create_user(username="restrict_desk_worker", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        funeral_services.assign_desk_worker(funeral=self.funeral, user=member_user, desk_type="community", actor=self.admin_actor)

        client = self._login("restrict_desk_worker")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash"})
        self.assertEqual(res.status_code, 201)

    def test_treasurer_can_no_longer_record_a_gift_for_someone_else(self):
        User.objects.create_user(username="restrict_treasurer_gift", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        client = self._login("restrict_treasurer_gift")
        res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20"})
        self.assertEqual(res.status_code, 403)

    def test_collector_can_still_record_a_gift(self):
        User.objects.create_user(username="restrict_collector_gift", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        client = self._login("restrict_collector_gift")
        res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20"})
        self.assertEqual(res.status_code, 201)


class TaskAssignmentRestrictionTests(TestCase):
    """'A community member can't assign a task to someone.' Verified directly, not just assumed from the role set's contents."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-task-restrict")
        self.admin_actor = User.objects.create_user(username="task_restrict_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin_actor)
        self.member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Some Member", gender="male")
        self.other_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Another Member", gender="female")

        self.member_user = User.objects.create_user(username="task_restrict_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin_actor)

    def test_a_community_member_cannot_assign_a_task_to_someone_else(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "task_restrict_member", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/tasks/", {"assigned_to": str(self.other_member.id), "title": "Should not be allowed"})
        self.assertEqual(res.status_code, 403)

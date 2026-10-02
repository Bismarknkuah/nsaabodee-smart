from django.core.exceptions import ValidationError
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
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash", "collector_name": "Test Collector"})
        self.assertEqual(res.status_code, 201)

    def test_treasurer_can_no_longer_record_a_payment_for_someone_else(self):
        """The core of the change: this used to be allowed, and now correctly isn't."""
        User.objects.create_user(username="restrict_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        client = self._login("restrict_treasurer")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash", "collector_name": "Test Collector"})
        self.assertEqual(res.status_code, 403)

    def test_community_admin_can_no_longer_record_a_payment_for_someone_else(self):
        client = self._login("restrict_setup_admin")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash", "collector_name": "Test Collector"})
        self.assertEqual(res.status_code, 403)

    def test_an_executive_pays_their_own_bill_from_the_member_account_and_never_from_the_executive_one(self):
        """
        'Don't bill any of the executive roles — those who manage the executive account are also members.'
        A bill is the community MEMBER's. The exception that lets anyone pay their own contribution now means:
        on the community-member account. From the executive dashboard the same person is refused.
        """
        from funerals.models import ContributionPayment
        own_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Treasurer As Member", gender="male")
        treasurer_user = User.objects.create_user(username="self_pay_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        member_services.link_member_to_user(member=own_member, user=treasurer_user, actor=self.admin_actor)
        own_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=own_member)
        url = f"/api/funerals/{self.funeral.id}/obligations/{own_obligation.id}/record-payment/"
        body = {"amount": "20", "method": "cash", "collector_name": "Test Col"}

        client = self._login("self_pay_treasurer")
        refused = client.post(url, body)                                        # executive dashboard
        self.assertEqual(refused.status_code, 403)
        self.assertIn("community member account", refused.data["detail"])
        self.assertFalse(ContributionPayment.objects.filter(obligation=own_obligation).exists())

        # ...and pays it from their separate member login — 'a separate member login per person'.
        member_services.create_member_login(member=own_member, username="self_pay_treasurer_member", password="a-real-password-123", actor=self.admin_actor)
        paid = self._login("self_pay_treasurer_member").post(url, body)
        self.assertEqual(paid.status_code, 201, paid.data)
        self.assertTrue(ContributionPayment.objects.filter(obligation=own_obligation).exists())
        treasurer_user.refresh_from_db()
        self.assertEqual(treasurer_user.role, Role.TREASURER)                   # the executive login is untouched

    def test_a_plain_community_member_pays_their_own_bill_freely(self):
        own_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Plain Member", gender="female")
        user = User.objects.create_user(username="self_pay_plain", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=own_member, user=user, actor=self.admin_actor)
        ob = ContributionObligation.objects.get(funeral_event=self.funeral, member=own_member)
        res = self._login("self_pay_plain").post(f"/api/funerals/{self.funeral.id}/obligations/{ob.id}/record-payment/", {"amount": "3", "method": "cash", "collector_name": "Me"})
        self.assertEqual(res.status_code, 201, res.data)

    def test_self_payment_exception_cannot_be_used_to_pay_someone_elses_obligation(self):
        """The exception is checked against the SPECIFIC obligation, not a blanket 'has a member profile' grant."""
        own_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Financial Sec As Member", gender="female")
        fs_user = User.objects.create_user(username="self_pay_fs", password="a-real-password-123", community=self.bodi, role=Role.FINANCIAL_SECRETARY)
        member_services.link_member_to_user(member=own_member, user=fs_user, actor=self.admin_actor)

        client = self._login("self_pay_fs")
        # Trying to pay the OTHER member's obligation, not their own.
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/", {"amount": "20", "method": "cash", "collector_name": "Test Collector"})
        self.assertEqual(res.status_code, 403)

    def test_a_community_member_can_never_be_assigned_a_desk(self):
        """A community-member account plays no other role, and only collectors receive money — so no desk for members."""
        member_user = User.objects.create_user(username="restrict_desk_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError) as ctx:
            funeral_services.assign_desk_worker(funeral=self.funeral, user=member_user, desk_type="community", actor=self.admin_actor)
        self.assertIn("not a collector", str(ctx.exception))
        with self.assertRaises(ValidationError):                                # ...and no login is created on the spot either
            funeral_services.assign_desk_worker(funeral=self.funeral, user=None, desk_type="community", actor=self.admin_actor)

    def test_a_desk_lets_a_collector_take_payments_beyond_their_usual_jurisdiction_for_that_funeral(self):
        """What a desk is FOR now: a Bretuo family collector, refused Asona members by jurisdiction, may work this funeral's community desk."""
        from members.models import CollectorNomination
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin_actor)
        col = User.objects.create_user(username="restrict_desk_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        m = member_services.register_member(community=self.bodi, full_name="Bretuo Collector", gender="male", family=bretuo)
        member_services.link_member_to_user(member=m, user=col, actor=self.admin_actor)
        CollectorNomination.objects.create(community=self.bodi, member=m, collector_type="family", scoped_family=bretuo, status=CollectorNomination.Status.APPROVED)
        url = f"/api/funerals/{self.funeral.id}/obligations/{self.other_obligation.id}/record-payment/"
        body = {"amount": "20", "method": "cash", "collector_name": "Test Collector"}
        client = self._login("restrict_desk_collector")
        self.assertEqual(client.post(url, body).status_code, 403)               # an Asona member is outside a Bretuo collector's jurisdiction
        funeral_services.assign_desk_worker(funeral=self.funeral, user=col, desk_type="community", actor=self.admin_actor)
        self.assertEqual(client.post(url, body).status_code, 201)               # ...but not outside this funeral's desk

    def test_treasurer_can_no_longer_record_a_gift_for_someone_else(self):
        User.objects.create_user(username="restrict_treasurer_gift", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        client = self._login("restrict_treasurer_gift")
        res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20", "collector_name": "Test Collector"})
        self.assertEqual(res.status_code, 403)

    def test_the_guest_contribution_collector_records_a_gift(self):
        """'For visitors level there should be a collector for guest contribution' — that role takes guests' gifts."""
        User.objects.create_user(username="restrict_gift_collector", password="a-real-password-123", community=self.bodi, role=Role.GIFT_COLLECTOR)
        client = self._login("restrict_gift_collector")
        res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20", "collector_name": "Test Collector"})
        self.assertEqual(res.status_code, 201)

    def test_a_contribution_collector_with_no_donation_nomination_cannot_record_a_gift(self):
        """Collecting the mandatory contribution and taking guests' gifts are different jobs, in different ledgers."""
        User.objects.create_user(username="restrict_collector_gift", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        client = self._login("restrict_collector_gift")
        res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20", "collector_name": "Test Collector"})
        self.assertEqual(res.status_code, 403)


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

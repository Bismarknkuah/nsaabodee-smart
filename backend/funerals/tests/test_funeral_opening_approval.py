from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation, FuneralEvent
from members import services as member_services
from tenants.models import Community


class FuneralOpeningApprovalServiceTests(TestCase):
    """
    'Is the family head who will open the ledger when there's a funeral.
    Once ledger is opened the community secretary, chairman, or admin —
    two of them — have to approve the request before every member is
    billed.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.treasurer = User.objects.create_user(username="treasurer", password="x", community=self.bodi, role=Role.TREASURER)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        self.ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary", gender="male", family=self.asona)

    def test_requesting_a_funeral_creates_it_pending_with_no_obligations_yet(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.head_member.linked_user,
        )
        self.assertEqual(funeral.status, FuneralEvent.Status.PENDING_APPROVAL)
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=funeral).count(), 0)

    def test_the_requester_cannot_approve_their_own_funeral_opening(self):
        """'Under no circumstance shall a user be able to approve... their own official transactions... where a conflict of interest exists.'"""
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.chairman,
        )
        with self.assertRaises(ValidationError):
            funeral_services.approve_funeral_opening(funeral=funeral, approver=self.chairman)

    def test_a_single_approval_is_not_enough(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.secretary)
        funeral.refresh_from_db()
        self.assertEqual(funeral.status, FuneralEvent.Status.PENDING_APPROVAL)
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=funeral).count(), 0)

    def test_the_same_person_approving_twice_never_counts_as_two(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.secretary)  # same person again
        funeral.refresh_from_db()
        self.assertEqual(funeral.status, FuneralEvent.Status.PENDING_APPROVAL)

    def test_two_distinct_approvals_activate_the_funeral_and_bill_everyone(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.chairman)
        funeral.refresh_from_db()
        self.assertEqual(funeral.status, FuneralEvent.Status.ACTIVE)
        # Both real members (head + ordinary) are billed the instant it activates.
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=funeral).count(), 2)

    def test_progress_reporting(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        progress = funeral_services.funeral_approval_progress(funeral)
        self.assertEqual(progress["approval_count"], 0)
        self.assertEqual(progress["still_needed"], 2)

        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.secretary)
        progress = funeral_services.funeral_approval_progress(funeral)
        self.assertEqual(progress["approval_count"], 1)
        self.assertEqual(progress["still_needed"], 1)

    def test_rejecting_a_pending_request_cancels_it(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        funeral_services.reject_funeral_opening(funeral=funeral, actor=self.chairman)
        funeral.refresh_from_db()
        self.assertEqual(funeral.status, FuneralEvent.Status.CANCELLED)

    def test_cannot_reject_a_funeral_thats_already_active(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Direct Creation", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        with self.assertRaises(ValidationError):
            funeral_services.reject_funeral_opening(funeral=funeral, actor=self.chairman)


class FuneralOpeningApprovalHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="the_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.random_member_user = User.objects.create_user(username="rando", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_family_head_can_request_an_opening_for_his_own_family(self):
        client = self._login("the_head")
        res = client.post("/api/funerals/request/", {
            "deceased_name": "Yaw Asona", "deceased_gender": "male",
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending_approval")

    def test_family_head_cannot_request_an_opening_for_a_different_family(self):
        client = self._login("the_head")
        res = client.post("/api/funerals/request/", {
            "deceased_name": "Someone Else", "deceased_gender": "male",
            "deceased_family_id": str(self.bretuo.id),
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        self.assertEqual(res.status_code, 400)

    def test_an_ordinary_community_member_cannot_request_an_opening_at_all(self):
        client = self._login("rando")
        res = client.post("/api/funerals/request/", {
            "deceased_name": "Yaw Asona", "deceased_gender": "male",
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        self.assertEqual(res.status_code, 403)

    def test_full_flow_request_then_two_approvals_then_active(self):
        client = self._login("the_head")
        request_res = client.post("/api/funerals/request/", {
            "deceased_name": "Yaw Asona", "deceased_gender": "male",
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        funeral_id = request_res.data["id"]

        secretary_client = self._login("secretary")
        approve1 = secretary_client.post(f"/api/funerals/{funeral_id}/approve-opening/")
        self.assertEqual(approve1.status_code, 200)
        self.assertEqual(approve1.data["status"], "pending_approval")

        chairman_client = self._login("chairman")
        approve2 = chairman_client.post(f"/api/funerals/{funeral_id}/approve-opening/")
        self.assertEqual(approve2.status_code, 200)
        self.assertEqual(approve2.data["status"], "active")

    def test_family_head_cannot_approve_openings_himself(self):
        client = self._login("the_head")
        request_res = client.post("/api/funerals/request/", {
            "deceased_name": "Yaw Asona", "deceased_gender": "male",
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        funeral_id = request_res.data["id"]
        approve_res = client.post(f"/api/funerals/{funeral_id}/approve-opening/")
        self.assertEqual(approve_res.status_code, 403)


class ConcurrentMultipleLedgersTests(TestCase):
    """
    'A family head/family and the community chairman/secretary [can]
    open one or more ledgers at the same time depending on the number
    of funerals on that date... two families or more can do funeral at
    the same time same as one family head can open two or more ledgers
    at the same time.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.asona_head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        self.asona_head_user = User.objects.create_user(username="asona_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.asona_head_member, user=self.asona_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.asona_head_member, actor=self.admin)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.bretuo_head_member = member_services.register_member(community=self.bodi, full_name="Bretuo Head", gender="male", family=self.bretuo)
        self.bretuo_head_user = User.objects.create_user(username="bretuo_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.bretuo_head_member, user=self.bretuo_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=self.bretuo_head_member, actor=self.admin)

    def test_two_different_families_can_both_have_pending_requests_on_the_same_day(self):
        asona_request = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        bretuo_request = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Someone Bretuo", deceased_gender="female",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.assertEqual(asona_request.status, FuneralEvent.Status.PENDING_APPROVAL)
        self.assertEqual(bretuo_request.status, FuneralEvent.Status.PENDING_APPROVAL)
        self.assertNotEqual(asona_request.id, bretuo_request.id)

    def test_approving_one_familys_funeral_does_not_touch_the_others_approvals(self):
        asona_request = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        bretuo_request = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Someone Bretuo", deceased_gender="female",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        funeral_services.approve_funeral_opening(funeral=asona_request, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=asona_request, approver=self.chairman)

        asona_request.refresh_from_db()
        bretuo_request.refresh_from_db()
        self.assertEqual(asona_request.status, FuneralEvent.Status.ACTIVE)
        self.assertEqual(bretuo_request.status, FuneralEvent.Status.PENDING_APPROVAL)  # untouched

    def test_one_family_head_can_open_two_or_more_ledgers_at_the_same_time(self):
        """Two deaths in the same extended family close together — the same head requests both."""
        first_request = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="First Asona Death", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        second_request = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Second Asona Death", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-02", collection_start_date="2026-07-02",
        )
        self.assertNotEqual(first_request.id, second_request.id)
        self.assertEqual(FuneralEvent.objects.filter(deceased_family=self.asona, status=FuneralEvent.Status.PENDING_APPROVAL).count(), 2)

        # Both can be independently approved and activated without interfering with each other.
        funeral_services.approve_funeral_opening(funeral=first_request, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=first_request, approver=self.chairman)
        funeral_services.approve_funeral_opening(funeral=second_request, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=second_request, approver=self.chairman)
        first_request.refresh_from_db()
        second_request.refresh_from_db()
        self.assertEqual(first_request.status, FuneralEvent.Status.ACTIVE)
        self.assertEqual(second_request.status, FuneralEvent.Status.ACTIVE)

        # A member of Asona family is billed correctly, independently, on BOTH ledgers.
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=first_request, member=self.asona_head_member).count(), 1)
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=second_request, member=self.asona_head_member).count(), 1)

    def test_full_http_flow_two_families_requesting_and_approving_concurrently(self):
        asona_client = self._login("asona_head")
        bretuo_client = self._login("bretuo_head")

        asona_res = asona_client.post("/api/funerals/request/", {
            "deceased_name": "Someone Asona", "deceased_gender": "male",
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        bretuo_res = bretuo_client.post("/api/funerals/request/", {
            "deceased_name": "Someone Bretuo", "deceased_gender": "female",
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        self.assertEqual(asona_res.status_code, 201)
        self.assertEqual(bretuo_res.status_code, 201)

        pending_res = self._login("secretary").get("/api/funerals/?status=pending_approval")
        self.assertEqual(pending_res.data["count"], 2)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

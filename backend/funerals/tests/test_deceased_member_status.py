from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class DeceasedMemberStatusTransitionTests(TestCase):
    """'When someone dies or they do his or her funeral, their membership account should go inactive.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="dmst-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="dmst_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.deceased = member_services.register_member(community=self.bodi, full_name="Yaw Asona", gender="male", family=self.asona)

    def test_creating_a_funeral_directly_transitions_the_linked_member_to_deceased(self):
        self.assertEqual(self.deceased.status, Member.Status.ACTIVE)
        funeral_services.create_funeral_event(
            community=self.bodi, deceased_name=self.deceased.full_name, deceased_gender="male",
            deceased_family=self.asona, deceased_member=self.deceased, cause_of_death="Natural causes",
            date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.deceased.refresh_from_db()
        self.assertEqual(self.deceased.status, Member.Status.DECEASED)

    def test_a_funeral_with_no_linked_member_does_not_touch_anyones_status(self):
        """The deceased was never a registered Member — deceased_name alone is enough for the funeral itself."""
        funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Unregistered", deceased_gender="male",
            deceased_family=self.asona, cause_of_death="Natural causes",
            date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.deceased.refresh_from_db()
        self.assertEqual(self.deceased.status, Member.Status.ACTIVE)

    def test_a_pending_funeral_request_does_not_transition_status_until_approved(self):
        """A rejected or still-pending request should never have already changed the deceased's own membership status."""
        pending = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name=self.deceased.full_name, deceased_gender="male",
            deceased_family=self.asona, deceased_member=self.deceased, cause_of_death="Natural causes",
            date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.deceased.refresh_from_db()
        self.assertEqual(self.deceased.status, Member.Status.ACTIVE)

        secretary = User.objects.create_user(username="dmst_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        chairman = User.objects.create_user(username="dmst_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        funeral_services.approve_funeral_opening(funeral=pending, approver=secretary)
        self.deceased.refresh_from_db()
        self.assertEqual(self.deceased.status, Member.Status.ACTIVE)  # only one of two approvals so far

        funeral_services.approve_funeral_opening(funeral=pending, approver=chairman)
        self.deceased.refresh_from_db()
        self.assertEqual(self.deceased.status, Member.Status.DECEASED)  # now live, second approval done it

    def test_creating_a_funeral_over_http_with_a_deceased_member_transitions_status(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "dmst_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/funerals/", {
            "deceased_name": self.deceased.full_name, "deceased_gender": "male",
            "deceased_family_id": str(self.asona.id), "deceased_member_id": str(self.deceased.id),
            "cause_of_death": "Natural causes",
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        self.assertEqual(res.status_code, 201, res.data)
        self.deceased.refresh_from_db()
        self.assertEqual(self.deceased.status, Member.Status.DECEASED)

    def test_creating_a_funeral_over_http_without_cause_of_death_is_rejected(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "dmst_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/funerals/", {
            "deceased_name": "Someone", "deceased_gender": "male",
            "deceased_family_id": str(self.asona.id),
            "date_of_death": "2026-07-01", "collection_start_date": "2026-07-01",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("cause_of_death", res.data)

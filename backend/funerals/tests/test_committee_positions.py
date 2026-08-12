from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import FuneralCommitteePosition
from members import services as member_services
from tenants.models import Community


class FuneralCommitteePositionServiceTests(TestCase):
    """'Every funeral creates a committee workspace... Chairman, Vice Chairman... Custom positions allowed.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-committee",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="committee_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Committee Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="committee_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Committee Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.volunteer = member_services.register_member(community=self.bodi, full_name="Committee Volunteer", gender="female", family=self.asona)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Person", gender="male", family=self.bretuo)

    def test_the_deceaseds_own_family_head_can_appoint_a_suggested_position(self):
        position = funeral_services.appoint_committee_position(funeral=self.funeral, member=self.volunteer, title="Logistics Officer", actor=self.head_user)
        self.assertEqual(position.title, "Logistics Officer")

    def test_a_custom_title_is_allowed(self):
        position = funeral_services.appoint_committee_position(funeral=self.funeral, member=self.volunteer, title="Live Streaming Coordinator", actor=self.head_user)
        self.assertEqual(position.title, "Live Streaming Coordinator")

    def test_community_wide_leadership_can_also_appoint(self):
        position = funeral_services.appoint_committee_position(funeral=self.funeral, member=self.bretuo_member, title="Security Officer", actor=self.admin)
        self.assertEqual(position.title, "Security Officer")

    def test_a_different_familys_head_cannot_appoint_for_this_funeral(self):
        other_head_member = member_services.register_member(community=self.bodi, full_name="Bretuo Head", gender="male", family=self.bretuo)
        other_head_user = User.objects.create_user(username="committee_other_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=other_head_member, user=other_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=other_head_member, actor=self.admin)
        with self.assertRaises(ValidationError):
            funeral_services.appoint_committee_position(funeral=self.funeral, member=self.bretuo_member, title="PR Officer", actor=other_head_user)

    def test_the_family_secretary_has_the_same_authority_as_the_head_here_matching_desk_assignment(self):
        """Deliberately mirrors _can_assign_desk_workers_for's existing rule for the Family desk type — Secretary shares this authority with the Head, not just Community-wide leadership."""
        secretary_member = member_services.register_member(community=self.bodi, full_name="Committee Secretary", gender="female", family=self.asona)
        secretary_user = User.objects.create_user(username="committee_secretary_user", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=secretary_member, user=secretary_user, actor=self.admin)
        position = funeral_services.appoint_committee_position(funeral=self.funeral, member=self.volunteer, title="Food Coordinator", actor=secretary_user)
        self.assertEqual(position.title, "Food Coordinator")

    def test_an_ordinary_family_treasurer_cannot_appoint_only_head_secretary_or_community_leadership_can(self):
        treasurer_member = member_services.register_member(community=self.bodi, full_name="Committee Treasurer", gender="male", family=self.asona)
        treasurer_user = User.objects.create_user(username="committee_treasurer_user", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        member_services.link_member_to_user(member=treasurer_member, user=treasurer_user, actor=self.admin)
        with self.assertRaises(ValidationError):
            funeral_services.appoint_committee_position(funeral=self.funeral, member=self.volunteer, title="Food Coordinator", actor=treasurer_user)

    def test_this_never_grants_any_desk_or_payment_recording_authority(self):
        """The core design constraint — appointing to the committee is not the same as assigning a payment desk."""
        funeral_services.appoint_committee_position(funeral=self.funeral, member=self.volunteer, title="Treasurer", actor=self.head_user)
        from funerals.permissions import is_desk_worker_for
        volunteer_user = User.objects.create_user(username="committee_volunteer_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.volunteer, user=volunteer_user, actor=self.admin)
        self.assertFalse(is_desk_worker_for(volunteer_user, self.funeral, "contributions"))

    def test_removing_a_position_deletes_it(self):
        position = funeral_services.appoint_committee_position(funeral=self.funeral, member=self.volunteer, title="Welfare Officer", actor=self.head_user)
        funeral_services.remove_committee_position(position=position, actor=self.head_user)
        self.assertFalse(FuneralCommitteePosition.objects.filter(id=position.id).exists())

    def test_my_committee_positions_shows_a_members_own_assignments_across_funerals(self):
        funeral_services.appoint_committee_position(funeral=self.funeral, member=self.volunteer, title="Food Coordinator", actor=self.head_user)
        positions = funeral_services.list_my_committee_positions(member=self.volunteer)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].title, "Food Coordinator")

    def test_my_committee_positions_is_empty_for_someone_with_no_member_profile(self):
        self.assertEqual(funeral_services.list_my_committee_positions(member=None), [])


class FuneralCommitteePositionHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-committee-http",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="committee_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="HTTP Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.volunteer = member_services.register_member(community=self.bodi, full_name="HTTP Volunteer", gender="male", family=self.asona)
        self.volunteer_user = User.objects.create_user(username="committee_http_volunteer", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.volunteer, user=self.volunteer_user, actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_round_trip_appoint_view_and_remove(self):
        admin_client = self._login("committee_http_admin")
        appoint_res = admin_client.post(f"/api/funerals/{self.funeral.id}/committee-positions/", {"member_id": str(self.volunteer.id), "title": "Protocol Officer"})
        self.assertEqual(appoint_res.status_code, 201)
        position_id = appoint_res.data["id"]

        list_res = admin_client.get(f"/api/funerals/{self.funeral.id}/committee-positions/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.data), 1)

        remove_res = admin_client.delete(f"/api/funerals/{self.funeral.id}/committee-positions/{position_id}/")
        self.assertEqual(remove_res.status_code, 204)

    def test_the_my_committee_positions_route_is_genuinely_reachable_not_swallowed_by_the_detail_route(self):
        """The real routing risk with a list-level custom action alongside a UUID detail route — verified directly, not assumed."""
        admin_client = self._login("committee_http_admin")
        admin_client.post(f"/api/funerals/{self.funeral.id}/committee-positions/", {"member_id": str(self.volunteer.id), "title": "PR Officer"})

        volunteer_client = self._login("committee_http_volunteer")
        res = volunteer_client.get("/api/funerals/my-committee-positions/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "PR Officer")

    def test_an_ordinary_member_cannot_appoint_a_committee_position(self):
        client = self._login("committee_http_volunteer")
        res = client.post(f"/api/funerals/{self.funeral.id}/committee-positions/", {"member_id": str(self.volunteer.id), "title": "Chairman"})
        self.assertEqual(res.status_code, 400)

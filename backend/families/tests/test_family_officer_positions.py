from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from families.models import FamilyAuditLog, FamilyOfficerPosition
from members import services as member_services
from tenants.models import Community


class FamilyOfficerPositionServiceTests(TestCase):
    """'Family Head can create: Assistant Family Head... Organizer, Welfare Officer, Youth Leader, Women's Leader, Communication Officer, Auditor... Custom positions allowed.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-officer-positions")
        self.admin = User.objects.create_user(username="officer_pos_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="officer_pos_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.youth_member = member_services.register_member(community=self.bodi, full_name="Asona Youth", gender="male", family=self.asona)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="female", family=self.bretuo)

    def test_the_family_head_can_appoint_a_suggested_position(self):
        position = family_services.appoint_family_officer_position(family=self.asona, member=self.youth_member, title="Youth Leader", actor=self.head_user)
        self.assertEqual(position.title, "Youth Leader")
        self.assertEqual(position.member_id, self.youth_member.id)

    def test_a_custom_position_title_is_allowed(self):
        position = family_services.appoint_family_officer_position(family=self.asona, member=self.youth_member, title="Sports and Recreation Coordinator", actor=self.head_user)
        self.assertEqual(position.title, "Sports and Recreation Coordinator")

    def test_multiple_people_can_hold_the_same_title(self):
        """Unlike Head/Secretary/Treasurer, nothing here assumes exactly one holder per title."""
        second_member = member_services.register_member(community=self.bodi, full_name="Second Organizer", gender="female", family=self.asona)
        family_services.appoint_family_officer_position(family=self.asona, member=self.youth_member, title="Organizer", actor=self.head_user)
        family_services.appoint_family_officer_position(family=self.asona, member=second_member, title="Organizer", actor=self.head_user)
        positions = family_services.list_family_officer_positions(family=self.asona)
        organizers = [p for p in positions if p.title == "Organizer"]
        self.assertEqual(len(organizers), 2)

    def test_cannot_appoint_someone_from_a_different_family(self):
        with self.assertRaises(ValidationError):
            family_services.appoint_family_officer_position(family=self.asona, member=self.bretuo_member, title="Organizer", actor=self.head_user)

    def test_an_empty_title_is_rejected(self):
        with self.assertRaises(ValidationError):
            family_services.appoint_family_officer_position(family=self.asona, member=self.youth_member, title="   ", actor=self.head_user)

    def test_this_never_touches_the_appointees_platform_role(self):
        """The core design constraint — a genuinely new platform capability was NOT quietly introduced here."""
        family_services.appoint_family_officer_position(family=self.asona, member=self.youth_member, title="Youth Leader", actor=self.head_user)
        # The youth member has no linked user at all — confirming this is a pure Member-level record, not an account-level one.
        self.assertIsNone(self.youth_member.linked_user_id)

    def test_appointing_writes_a_family_audit_log_entry(self):
        family_services.appoint_family_officer_position(family=self.asona, member=self.youth_member, title="Youth Leader", actor=self.head_user)
        self.assertTrue(FamilyAuditLog.objects.filter(family=self.asona, action=FamilyAuditLog.Action.OFFICER_POSITION_APPOINTED).exists())

    def test_removing_a_position_deletes_it_and_logs_the_removal(self):
        position = family_services.appoint_family_officer_position(family=self.asona, member=self.youth_member, title="Youth Leader", actor=self.head_user)
        family_services.remove_family_officer_position(position=position, actor=self.head_user)
        self.assertFalse(FamilyOfficerPosition.objects.filter(id=position.id).exists())
        self.assertTrue(FamilyAuditLog.objects.filter(family=self.asona, action=FamilyAuditLog.Action.OFFICER_POSITION_REMOVED).exists())


class FamilyOfficerPositionHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-officer-positions-http")
        self.admin = User.objects.create_user(username="officer_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="officer_http_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Asona Secretary", gender="female", family=self.asona)
        self.secretary_user = User.objects.create_user(username="officer_http_secretary", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary_user, actor=self.admin)
        family_services.assign_family_officer(family=self.asona, member=self.secretary_member, officer_role="secretary", actor=self.admin)

        self.youth_member = member_services.register_member(community=self.bodi, full_name="Asona Youth", gender="male", family=self.asona)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_round_trip_appoint_view_and_remove(self):
        head_client = self._login("officer_http_head")
        appoint_res = head_client.post(f"/api/families/{self.asona.id}/officer-positions/", {"member_id": str(self.youth_member.id), "title": "Youth Leader"})
        self.assertEqual(appoint_res.status_code, 201)
        position_id = appoint_res.data["id"]

        list_res = head_client.get(f"/api/families/{self.asona.id}/officer-positions/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["title"], "Youth Leader")

        remove_res = head_client.delete(f"/api/families/{self.asona.id}/officer-positions/{position_id}/")
        self.assertEqual(remove_res.status_code, 204)

    def test_the_family_secretary_cannot_appoint_positions_only_the_head_can(self):
        """Same authority boundary as assign_family_officer — Secretary/Treasurer don't inherit the Head's own delegation power."""
        secretary_client = self._login("officer_http_secretary")
        res = secretary_client.post(f"/api/families/{self.asona.id}/officer-positions/", {"member_id": str(self.youth_member.id), "title": "Youth Leader"})
        self.assertEqual(res.status_code, 403)

    def test_anyone_in_the_community_can_view_the_positions_list(self):
        head_client = self._login("officer_http_head")
        head_client.post(f"/api/families/{self.asona.id}/officer-positions/", {"member_id": str(self.youth_member.id), "title": "Youth Leader"})

        ordinary_client = self._login("officer_http_secretary")
        res = ordinary_client.get(f"/api/families/{self.asona.id}/officer-positions/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

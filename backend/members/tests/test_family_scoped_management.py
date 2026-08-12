from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class FamilyScopedMemberManagementTests(TestCase):
    """
    'Each family head and secretary should be able to create accounts
    for the family members' — scoped to THEIR family only, both for
    registering new members and for editing/linking existing ones.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.asona_secretary_member = member_services.register_member(
            community=self.bodi, full_name="Asona Secretary Person", gender="male", family=self.asona
        )
        self.asona_secretary_user = User.objects.create_user(
            username="asona_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY
        )
        member_services.link_member_to_user(member=self.asona_secretary_member, user=self.asona_secretary_user, actor=self.admin)
        family_services.assign_family_officer(family=self.asona, member=self.asona_secretary_member, officer_role="secretary", actor=self.admin)

        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="female", family=self.bretuo)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_family_secretary_can_register_a_member_into_their_own_family(self):
        client = self._login("asona_secretary")
        res = client.post("/api/members/", {"full_name": "New Asona Member", "gender": "male"})
        self.assertEqual(res.status_code, 201)

    def test_family_secretary_cannot_register_a_member_into_a_different_family(self):
        client = self._login("asona_secretary")
        res = client.post("/api/members/", {"full_name": "Sneaky", "gender": "male", "family_id": str(self.bretuo.id)})
        self.assertEqual(res.status_code, 400)

    def test_family_secretary_cannot_edit_a_member_of_a_different_family(self):
        """
        '404 now, not 403 — a stronger boundary than before: a different
        family's member isn't just edit-blocked, they're invisible to
        this search/detail scope entirely (see search_members'
        FAMILY_SCOPED_MEMBER_ROLES), so there's nothing here to even
        return a 403 about.
        """
        client = self._login("asona_secretary")
        res = client.patch(f"/api/members/{self.bretuo_member.id}/", {"phone": "0244000000"})
        self.assertEqual(res.status_code, 404)

    def test_family_secretary_can_edit_a_member_of_their_own_family(self):
        own_family_member = member_services.register_member(community=self.bodi, full_name="Another Asona Person", gender="male", family=self.asona)
        client = self._login("asona_secretary")
        res = client.patch(f"/api/members/{own_family_member.id}/", {"phone": "0244000000"})
        self.assertEqual(res.status_code, 200)

    def test_family_secretary_cannot_link_a_login_for_a_member_of_a_different_family(self):
        client = self._login("asona_secretary")
        res = client.post(f"/api/members/{self.bretuo_member.id}/link-user/", {"username": "shouldnt_work", "password": "a-real-password-123"})
        self.assertEqual(res.status_code, 404)

    def test_a_family_level_executive_only_sees_their_own_familys_roster(self):
        """
        'Family head or executive shouldn't have access to other
        families' information or members' information... they should
        only see their members, not other members from a different
        family.' The real, corrected behavior — this replaces an
        earlier test that (incorrectly, at the time) asserted the
        opposite: that viewing was never restricted at all.
        """
        client = self._login("asona_secretary")
        res = client.get("/api/members/")
        self.assertEqual(res.status_code, 200)
        names = {m["full_name"] for m in res.data["results"]}
        self.assertIn("Asona Secretary Person", names)
        self.assertNotIn("Bretuo Member", names)

    def test_community_admin_still_sees_the_whole_roster_across_every_family(self):
        """Community-wide roles keep their existing, legitimate visibility unchanged — only family-level executives are newly scoped."""
        client = self._login("admin")
        res = client.get("/api/members/")
        names = {m["full_name"] for m in res.data["results"]}
        self.assertIn("Asona Secretary Person", names)
        self.assertIn("Bretuo Member", names)

    def test_a_family_level_executive_cannot_widen_their_view_by_passing_another_familys_id(self):
        client = self._login("asona_secretary")
        res = client.get(f"/api/members/?family={self.bretuo.id}")
        names = {m["full_name"] for m in res.data["results"]}
        self.assertNotIn("Bretuo Member", names)


class RegisteredByNullEditRegressionTests(TestCase):
    """
    Real bug found while testing family-scoped edits: Member.registered_by
    had null=True (correctly allowing on_delete=SET_NULL when the
    registering staff account is later removed) but was MISSING
    blank=True — so the moment that happened, full_clean() on any future
    edit failed with an unattributed "This field cannot be blank," making
    the member permanently un-editable through the normal update path.
    This is exactly the scenario on_delete=SET_NULL exists to support
    gracefully, so it must never break editing.
    """

    def test_a_member_with_no_registering_user_can_still_be_edited(self):
        bodi = Community.objects.create(name="Bodi", slug="bodi-regnull")
        admin = User.objects.create_user(username="admin_regnull", password="x", community=bodi, role=Role.COMMUNITY_ADMIN)
        asona = family_services.create_family(community=bodi, name="Asona", actor=admin)
        # Deliberately no registered_by, the exact state left behind
        # after on_delete=SET_NULL fires for a deleted staff account.
        member = member_services.register_member(community=bodi, full_name="No Registrar", gender="male", family=asona)
        self.assertIsNone(member.registered_by)

        client = self._login_as(admin, bodi)
        res = client.patch(f"/api/members/{member.id}/", {"phone": "0244000000"})
        self.assertEqual(res.status_code, 200)
        member.refresh_from_db()
        self.assertEqual(member.phone, "0244000000")

    def _login_as(self, user, community):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": user.username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

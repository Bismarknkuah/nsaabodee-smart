from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class ContextSwitchRetiredTests(TestCase):
    """
    The executive/personal dashboard switch is retired: 'build a separate member login per person, and member
    accounts play no other roles'. An executive login is an executive; a member login is a member; neither switches.
    (This file replaced the 26 tests of the old switch; what they protected — no executive work from a member
    account, no billing on an executive account — is covered by test_member_account_and_guest_retirement.)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="csr-bodi")
        self.admin = User.objects.create_user(username="csr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_nobody_can_switch_and_the_message_points_to_the_member_login(self):
        member = member_services.register_member(community=self.bodi, full_name="Chair", gender="male", family=self.asona)
        chair = member_services.assign_role_to_member(member=member, role="chairman", actor=self.admin, username="csr_chair", password="a-real-password-123")
        self.assertFalse(chair.can_switch_dashboard_context())
        c = APIClient(); c.force_authenticate(chair)
        res = c.post("/api/auth/switch-context/", {"context": "personal"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("member login", str(res.data))

    def test_an_executive_login_is_always_the_executive(self):
        member = member_services.register_member(community=self.bodi, full_name="Col", gender="male", family=self.asona)
        col = member_services.assign_role_to_member(member=member, role="collector", actor=self.admin, username="csr_col", password="a-real-password-123")
        col.active_context = "personal"; col.save(update_fields=["active_context"])   # a stale value from before the split
        c = APIClient(); c.force_authenticate(col)
        me = c.get("/api/auth/me/").data
        self.assertEqual((me["role"], me["effective_role"]), ("collector", "collector"))

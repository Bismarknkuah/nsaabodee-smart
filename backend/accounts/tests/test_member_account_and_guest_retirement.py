from decimal import Decimal
from importlib import import_module

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import EXECUTIVE_ROLES, VISIBLE_ROLES, Role, User, canonical_role
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class SeparateMemberLoginTests(TestCase):
    """
    'Build a separate member login per person, and member accounts play no other roles.' A person who holds an
    office has two logins: an executive login for the office, and a member login for their own bills, receipts and
    wallet. The member login is a community member and nothing else; the executive login is never billed.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="sml-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="sml_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

    def _login(self, username, password="a-real-password-123"):
        c = APIClient(); r = c.post("/api/auth/login/", {"username": username, "password": password})
        assert r.status_code == 200, r.data
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}"); return c

    def test_assigning_an_office_creates_a_separate_executive_login_and_leaves_the_member_login_a_member(self):
        member = member_services.register_member(community=self.bodi, full_name="Kofi", gender="male", family=self.asona)
        member_login = member_services.create_member_login(member=member, username="kofi", password="a-real-password-123", actor=self.admin)
        exec_login = member_services.assign_role_to_member(member=member, role="collector", actor=self.admin, username="kofi.collector", password="a-real-password-123")
        member.refresh_from_db(); member_login.refresh_from_db()
        self.assertEqual((member.linked_user_id, member.executive_login_id), (member_login.id, exec_login.id))
        self.assertEqual(member_login.role, "community_member")           # untouched
        self.assertEqual(exec_login.role, "collector")
        self.assertEqual(member_login.member_profile.id, member.id)      # both logins resolve to the same person
        self.assertEqual(exec_login.member_profile.id, member.id)
        with self.assertRaises(ValidationError):                          # one member login only
            member_services.create_member_login(member=member, username="kofi2", password="a-real-password-123", actor=self.admin)

    def test_the_member_login_plays_no_other_role_and_the_executive_login_never_pays(self):
        member = member_services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.asona)
        member_services.create_member_login(member=member, username="ama", password="a-real-password-123", actor=self.admin)
        member_services.assign_role_to_member(member=member, role="financial_secretary", actor=self.admin, username="ama.fin", password="a-real-password-123")
        funeral = funeral_services.create_funeral_event(community=self.bodi, deceased_name="D", deceased_gender="male", deceased_family=self.asona, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)
        ob = funeral.obligations.get(member=member)
        pay = f"/api/funerals/{funeral.id}/obligations/{ob.id}/record-payment/"
        body = {"amount": "3", "method": "cash", "collector_name": "Me"}

        exec_c, member_c = self._login("ama.fin"), self._login("ama")
        self.assertEqual(exec_c.get("/api/reports/collections/daily/").status_code, 200)        # the office works
        refused = exec_c.post(pay, body)                                                           # ...but never pays its own bill
        self.assertEqual(refused.status_code, 403)
        self.assertIn("'ama'", refused.data["detail"])                                             # and is told which login does
        self.assertEqual(member_c.post(pay, body).status_code, 201)                                # the member login pays
        self.assertEqual(member_c.get("/api/reports/collections/daily/").status_code, 403)         # and holds no office
        me = member_c.get("/api/auth/me/").data
        self.assertEqual((me["role"], me["effective_role"], me["can_switch_dashboard_context"]), ("community_member", "community_member", False))
        self.assertIsNone(me["member_login"])                                                      # told nothing about the executive login
        self.assertEqual(exec_c.get("/api/auth/me/").data["member_login"], {"exists": True, "username": "ama"})
        self.assertEqual(exec_c.post("/api/auth/switch-context/", {"context": "personal"}).status_code, 400)   # nothing to switch to

    def test_an_executive_creates_their_own_member_login_from_the_executive_login(self):
        member = member_services.register_member(community=self.bodi, full_name="Yaw", gender="male", family=self.asona)
        member_services.assign_role_to_member(member=member, role="secretary", actor=self.admin, username="yaw.sec", password="a-real-password-123")
        c = self._login("yaw.sec")
        self.assertEqual(c.get("/api/auth/me/").data["member_login"], {"exists": False, "username": None})
        res = c.post(f"/api/members/{member.id}/member-login/", {"username": "yaw", "password": "a-real-password-123"})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(c.get("/api/auth/me/").data["member_login"], {"exists": True, "username": "yaw"})
        self.assertEqual(self._login("yaw").get("/api/auth/me/").data["role"], "community_member")

    def test_discharge_closes_the_executive_login_and_keeps_the_member_login(self):
        member = member_services.register_member(community=self.bodi, full_name="Esi", gender="female", family=self.asona)
        member_services.create_member_login(member=member, username="esi", password="a-real-password-123", actor=self.admin)
        exec_login = member_services.assign_role_to_member(member=member, role="collector", actor=self.admin, username="esi.col", password="a-real-password-123")
        member_services.discharge_from_role(member=member, actor=self.admin, reason="term ended")
        exec_login.refresh_from_db(); member.refresh_from_db()
        self.assertFalse(exec_login.is_active)
        self.assertIsNone(member.executive_login_id)
        self.assertEqual(self._login("esi").get("/api/auth/me/").data["role"], "community_member")   # 'can still use their personal account'

    def test_discharge_with_no_member_login_turns_the_only_login_into_the_member_login(self):
        member = member_services.register_member(community=self.bodi, full_name="Kwame", gender="male", family=self.asona)
        exec_login = member_services.assign_role_to_member(member=member, role="collector", actor=self.admin, username="kwame.col", password="a-real-password-123")
        member_services.discharge_from_role(member=member, actor=self.admin)
        exec_login.refresh_from_db(); member.refresh_from_db()
        self.assertEqual((exec_login.role, exec_login.is_active), ("community_member", True))
        self.assertEqual((member.linked_user_id, member.executive_login_id), (exec_login.id, None))

    def test_the_migration_moves_every_office_holder_to_the_executive_login(self):
        plain = member_services.register_member(community=self.bodi, full_name="Plain", gender="male", family=self.asona)
        exec_m = member_services.register_member(community=self.bodi, full_name="Exec", gender="male", family=self.asona)
        u_plain = User.objects.create_user(username="mig_plain", password="x", community=self.bodi, role="community_member")
        u_exec = User.objects.create_user(username="mig_exec", password="x", community=self.bodi, role="chairman")
        Member.objects.filter(id=plain.id).update(linked_user=u_plain); Member.objects.filter(id=exec_m.id).update(linked_user=u_exec)   # the pre-split shape
        import_module("members.migrations.0014_split_executive_logins").executives_move_to_the_executive_login(django_apps, None)
        plain.refresh_from_db(); exec_m.refresh_from_db()
        self.assertEqual((plain.linked_user_id, plain.executive_login_id), (u_plain.id, None))
        self.assertEqual((exec_m.linked_user_id, exec_m.executive_login_id), (None, u_exec.id))
        self.assertEqual(u_exec.member_profile.id, exec_m.id)                                       # the office keeps working

    def test_every_executive_role_is_an_office_and_the_member_role_is_not(self):
        for role in ("town_registration_officer", "family_registration_officer", "welfare_manager", "family_welfare_manager", "gift_collector", "collector", "chairman"):
            self.assertIn(role, {str(r) for r in EXECUTIVE_ROLES})
        self.assertNotIn(Role.COMMUNITY_MEMBER, EXECUTIVE_ROLES)
        self.assertNotIn(Role.PLATFORM_ADMIN, EXECUTIVE_ROLES)

    def test_an_executive_dashboard_carries_no_billing(self):
        for i, role in enumerate((Role.CHAIRMAN, Role.COLLECTOR, Role.FINANCIAL_SECRETARY, Role.WELFARE_MANAGER)):
            m = member_services.register_member(community=self.bodi, full_name=f"E{i}", gender="male", family=self.asona)
            u = member_services.assign_role_to_member(member=m, role=role, actor=self.admin, username=f"sml_e{i}", password="a-real-password-123")
            sections = build_dashboard(u)["sections"]
            self.assertNotIn("member_overview", sections, f"{role} dashboard carries the member's own billing")


class GuestRoleRetirementTests(TestCase):
    def test_guest_is_retired_everywhere_it_used_to_be_offered(self):
        self.assertNotIn(Role.GUEST, VISIBLE_ROLES)
        self.assertEqual(canonical_role("guest"), "community_member")
        self.assertEqual(User().role, Role.COMMUNITY_MEMBER)

    def test_the_migration_turns_existing_guest_logins_into_community_members_without_deleting_them(self):
        community = Community.objects.create(name="Bodi", slug="grt-bodi")
        guest = User.objects.create_user(username="grt_guest", password="x", community=community, role="guest")
        chair = User.objects.create_user(username="grt_chair", password="x", community=community, role=Role.CHAIRMAN)
        import_module("accounts.migrations.0018_retire_guest_role").guests_become_community_members(django_apps, None)
        guest.refresh_from_db(); chair.refresh_from_db()
        self.assertEqual((guest.role, guest.is_active, chair.role), (Role.COMMUNITY_MEMBER, True, Role.CHAIRMAN))

    def test_a_converted_guest_with_no_member_record_gets_a_clear_message_not_a_crash(self):
        community = Community.objects.create(name="Bodi", slug="grt-bodi2")
        user = User.objects.create_user(username="grt_orphan", password="x", community=community, role=Role.COMMUNITY_MEMBER)
        self.assertEqual(build_dashboard(user)["sections"]["member_overview"]["message"], "No member profile linked yet.")

    def test_a_community_member_cannot_be_the_base_of_a_custom_role(self):
        from accounts import services
        self.assertNotIn("community_member", services.COMMUNITY_CUSTOM_BASE_ROLES)
        self.assertNotIn("community_member", services.FAMILY_CUSTOM_BASE_ROLES)

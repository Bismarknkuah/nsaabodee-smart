from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import COMMUNITY_ROLE_TYPES, FAMILY_ROLE_TYPES, Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community
from welfare import services as welfare_services


class WelfareManagersAndDischargeTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="wmd-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="wmd_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        for fam in (self.asona, self.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=self.admin)
            family_services.approve_family_rate(family=fam, actor=self.admin)
        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Welfare", fixed_amount=Decimal("10"), actor=self.admin)

    def _user(self, username, role, family=None):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
        if family is not None:
            m = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
            member_services.link_member_to_user(member=m, user=user, actor=self.admin)
        return user

    # ---- welfare managers ----
    def test_the_roles_exist_at_their_levels(self):
        """One welfare role, at community level — 'no family will have their personal welfare managers'."""
        self.assertIn("welfare_manager", COMMUNITY_ROLE_TYPES)
        self.assertNotIn("family_welfare_manager", FAMILY_ROLE_TYPES)

    def test_the_community_welfare_manager_runs_community_welfare_and_starts_a_familys_for_the_family_to_approve(self):
        wm = self._user("wmd_wm", Role.WELFARE_MANAGER)
        campaign = welfare_services.initiate_community_campaign(category=self.category, title="Harmattan relief", amount=Decimal("10"), actor=wm)
        self.assertIsNotNone(campaign.id)
        family = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Asona welfare", actor=wm)
        self.assertEqual(family.status, "pending_approval")                       # the family's Head and Secretary approve before anyone is billed
        self.assertEqual(list(build_dashboard(wm)["sections"]), ["welfare_manager_overview"])
        self.assertEqual(build_dashboard(wm)["sections"]["welfare_manager_overview"]["level"], "community")

    def test_welfare_managers_never_record_money(self):
        from funerals.jurisdiction import collector_grants
        self.assertEqual(collector_grants(self._user("wmd_wm2", Role.WELFARE_MANAGER)), [])

    # ---- discharge ----
    def test_whoever_can_assign_can_discharge_and_the_person_keeps_their_personal_account(self):
        """'Users with an executive role can be discharged... and can still use their personal account... the executive account shouldn't be different from an ordinary member's.'"""
        member = member_services.register_member(community=self.bodi, full_name="Kofi", gender="male", family=self.asona)
        user = member_services.assign_role_to_member(member=member, role="collector", actor=self.admin, username="wmd_kofi", password="a-real-password-123")
        CollectorNomination.objects.create(community=self.bodi, member=member, collector_type="family", scoped_family=self.asona, status=CollectorNomination.Status.APPROVED)
        funeral = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Deceased", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)
        obligation_before = funeral.obligations.get(member=member)

        member_services.discharge_from_role(member=member, actor=self.admin, reason="Term ended")
        user.refresh_from_db(); member.refresh_from_db()
        self.assertEqual(user.role, "community_member")
        self.assertTrue(user.is_active)                       # the personal account survives
        self.assertIsNone(user.custom_role_id)
        self.assertFalse(CollectorNomination.objects.filter(member=member, status=CollectorNomination.Status.APPROVED).exists())
        self.assertEqual(funeral.obligations.get(member=member).expected_amount, obligation_before.expected_amount)  # billing belongs to the member, not the role

    def test_discharge_authority_mirrors_assignment(self):
        head = self._user("wmd_head", Role.FAMILY_HEAD, self.asona)
        sec = self._user("wmd_sec", Role.FAMILY_SECRETARY, self.asona)
        bretuo_head = self._user("wmd_b_head", Role.FAMILY_HEAD, self.bretuo)
        collector = self._user("wmd_col", Role.COLLECTOR, self.asona)
        officer = self._user("wmd_fro", Role.FAMILY_REGISTRATION_OFFICER, self.asona)
        with self.assertRaises(ValidationError):   # another family's head cannot
            member_services.discharge_from_role(member=officer.member_profile, actor=bretuo_head)
        with self.assertRaises(ValidationError):   # a collector cannot
            member_services.discharge_from_role(member=officer.member_profile, actor=collector)
        member_services.discharge_from_role(member=officer.member_profile, actor=sec)   # the family secretary, who can assign, can
        officer.refresh_from_db(); self.assertEqual(officer.role, "community_member")
        with self.assertRaises(ValidationError):   # nobody discharges themselves
            member_services.discharge_from_role(member=head.member_profile, actor=head)

    def test_discharge_endpoint(self):
        officer = self._user("wmd_fro2", Role.FAMILY_REGISTRATION_OFFICER, self.asona)
        c = APIClient(); c.force_authenticate(self.admin)
        res = c.post(f"/api/members/{officer.member_profile.id}/discharge/", {"reason": "x"})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["role"], "community_member")   # no member login existed, so the only login became the member login

    def test_a_member_login_cannot_take_money_and_an_executive_login_cannot_pay_its_own_bill(self):
        """'Member accounts play no other roles' — and the executive login is never billed."""
        collector = self._user("wmd_col2", Role.COLLECTOR, self.asona)
        member_login = member_services.create_member_login(member=collector.member_profile, username="wmd_col2_member", password="a-real-password-123", actor=self.admin)
        payer = member_services.register_member(community=self.bodi, full_name="Payer", gender="male", family=self.asona)
        funeral = funeral_services.create_funeral_event(community=self.bodi, deceased_name="Open", deceased_gender="male", deceased_family=self.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02", actor=self.admin)
        other = funeral.obligations.get(member=payer); own = funeral.obligations.get(member=collector.member_profile)
        body = {"amount": "1", "method": "cash", "collector_name": "C"}
        m = APIClient(); m.force_authenticate(member_login)
        self.assertEqual(m.post(f"/api/funerals/{funeral.id}/obligations/{other.id}/record-payment/", body).status_code, 403)   # a member takes nobody's money
        self.assertEqual(m.post(f"/api/funerals/{funeral.id}/obligations/{own.id}/record-payment/", body).status_code, 201)     # ...only pays their own
        e = APIClient(); e.force_authenticate(collector)
        self.assertEqual(e.post(f"/api/funerals/{funeral.id}/obligations/{other.id}/record-payment/", body).status_code, 201)   # the executive collects
        self.assertEqual(e.post(f"/api/funerals/{funeral.id}/obligations/{own.id}/record-payment/", body).status_code, 403)     # ...and never pays its own


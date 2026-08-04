from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community


class DashboardContextSwitchingServiceTests(TestCase):
    """'Switch to Personal Dashboard... does not require logout, does not create another account, only changes permission context.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-context-switch")
        self.admin = User.objects.create_user(username="context_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Context Treasurer", gender="male", family=self.asona)
        self.treasurer = User.objects.create_user(username="context_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer, actor=self.admin)

        self.plain_member = User.objects.create_user(username="context_plain_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_an_executive_with_a_linked_profile_can_switch_to_personal(self):
        from accounts import services as account_services
        updated = account_services.switch_dashboard_context(user=self.treasurer, context="personal")
        self.assertEqual(updated.active_context, "personal")

    def test_switching_writes_a_real_audit_log_entry(self):
        """'This switch must... log the switch in the audit log.'"""
        from accounts import services as account_services
        from audit_log.models import AuditLogEntry
        account_services.switch_dashboard_context(user=self.treasurer, context="personal")
        entry = AuditLogEntry.objects.filter(action="dashboard_context_switched", actor=self.treasurer).first()
        self.assertIsNotNone(entry)
        self.assertIn("personal", entry.description)

    def test_switching_back_and_forth_writes_two_separate_entries(self):
        from accounts import services as account_services
        from audit_log.models import AuditLogEntry
        account_services.switch_dashboard_context(user=self.treasurer, context="personal")
        account_services.switch_dashboard_context(user=self.treasurer, context="executive")
        self.assertEqual(AuditLogEntry.objects.filter(action="dashboard_context_switched", actor=self.treasurer).count(), 2)

    def test_switching_to_the_same_context_already_active_writes_no_new_entry(self):
        from accounts import services as account_services
        from audit_log.models import AuditLogEntry
        account_services.switch_dashboard_context(user=self.treasurer, context="executive")  # already the default
        self.assertEqual(AuditLogEntry.objects.filter(action="dashboard_context_switched", actor=self.treasurer).count(), 0)

    def test_a_user_can_never_be_in_both_contexts_at_once(self):
        """'Prevent simultaneous execution of both contexts' — holds by construction: active_context is a single field, not a set, so switching to one is exclusive of the other, not additive."""
        from accounts import services as account_services
        account_services.switch_dashboard_context(user=self.treasurer, context="personal")
        self.treasurer.refresh_from_db()
        self.assertEqual(self.treasurer.active_context, "personal")
        self.assertNotEqual(self.treasurer.active_context, "executive")

        account_services.switch_dashboard_context(user=self.treasurer, context="executive")
        self.treasurer.refresh_from_db()
        self.assertEqual(self.treasurer.active_context, "executive")
        self.assertNotEqual(self.treasurer.active_context, "personal")

    def test_switching_never_touches_the_actual_stored_role(self):
        from accounts import services as account_services
        account_services.switch_dashboard_context(user=self.treasurer, context="personal")
        self.treasurer.refresh_from_db()
        self.assertEqual(self.treasurer.role, "treasurer")

    def test_a_plain_community_member_has_nothing_to_switch(self):
        """No executive/personal distinction exists for a role with no executive powers to begin with."""
        self.assertFalse(self.plain_member.can_switch_dashboard_context())
        from accounts import services as account_services
        with self.assertRaises(ValidationError):
            account_services.switch_dashboard_context(user=self.plain_member, context="personal")

    def test_an_executive_with_no_linked_member_profile_cannot_switch(self):
        unlinked_treasurer = User.objects.create_user(username="context_unlinked_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.assertFalse(unlinked_treasurer.can_switch_dashboard_context())

    def test_switching_back_to_executive_works(self):
        from accounts import services as account_services
        account_services.switch_dashboard_context(user=self.treasurer, context="personal")
        account_services.switch_dashboard_context(user=self.treasurer, context="executive")
        self.treasurer.refresh_from_db()
        self.assertEqual(self.treasurer.active_context, "executive")

    def test_an_invalid_context_value_is_rejected(self):
        from accounts import services as account_services
        with self.assertRaises(ValidationError):
            account_services.switch_dashboard_context(user=self.treasurer, context="nonsense")


class ExecutiveActionsBlockedInPersonalContextTests(TestCase):
    """The actual enforcement — a genuine executive, blocked from executive actions the moment they've switched, without their role changing at all."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-context-enforcement",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="enforce_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Enforce Treasurer", gender="male", family=self.asona)
        self.treasurer = User.objects.create_user(username="enforce_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Enforce Secretary", gender="female", family=self.asona)
        self.secretary = User.objects.create_user(username="enforce_secretary", password="a-real-password-123", community=self.bodi, role=Role.SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary, actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_switching_to_personal_then_trying_to_approve_a_payment_reversal_is_blocked(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Enforce Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        payer = member_services.register_member(community=self.bodi, full_name="Enforce Payer", gender="male", family=self.asona)
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=payer)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector=self.admin)
        reversal = funeral_services.request_payment_reversal(payment=payment, reason="Wrong member", actor=self.admin)

        client = self._login("enforce_secretary")
        switch_res = client.post("/api/auth/switch-context/", {"context": "personal"})
        self.assertEqual(switch_res.status_code, 200)
        self.assertEqual(switch_res.data["active_context"], "personal")
        # Confirm the stored role is genuinely untouched by the switch itself.
        self.assertEqual(switch_res.data["role"], "secretary")

        approve_res = client.post(f"/api/payment-reversals/{reversal.id}/approve/", {})
        self.assertEqual(approve_res.status_code, 403)

        switch_back = client.post("/api/auth/switch-context/", {"context": "executive"})
        self.assertEqual(switch_back.status_code, 200)
        approve_res_2 = client.post(f"/api/payment-reversals/{reversal.id}/approve/", {})
        self.assertEqual(approve_res_2.status_code, 200)

    def test_a_desk_assigned_ordinary_member_can_still_record_payments_regardless_of_context(self):
        """The safety property this design depends on — a role with no executive/personal distinction can never be blocked by this check."""
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Desk Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        payer = member_services.register_member(community=self.bodi, full_name="Desk Payer", gender="male", family=self.asona)
        ordinary_member = User.objects.create_user(username="enforce_ordinary_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        funeral_services.assign_desk_worker(funeral=funeral, actor=self.admin, desk_type="community", user=ordinary_member)

        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=payer)
        client = self._login("enforce_ordinary_member")
        res = client.post(f"/api/funerals/{funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        self.assertEqual(res.status_code, 201)

    def test_a_community_member_cannot_switch_context_at_all(self):
        member = User.objects.create_user(username="enforce_cant_switch", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        client = self._login("enforce_cant_switch")
        res = client.post("/api/auth/switch-context/", {"context": "personal"})
        self.assertEqual(res.status_code, 400)

    def test_switching_to_personal_shows_the_member_dashboard_not_the_financial_one(self):
        client = self._login("enforce_treasurer")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        dashboard_res = client.get("/api/dashboard/")
        self.assertEqual(dashboard_res.status_code, 200)
        self.assertIn("member_overview", dashboard_res.data["sections"])
        self.assertNotIn("financial_overview", dashboard_res.data["sections"])


class MethodAwareContextEnforcementTests(TestCase):
    """
    Member registration and task assignment are mixed read/write
    viewsets — a blanket RequiresExecutiveContext would have wrongly
    blocked someone from viewing the roster or updating their own
    assigned task's status while in Personal Dashboard. These tests
    confirm the method-aware variants get the distinction right.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-method-aware")
        self.admin = User.objects.create_user(username="method_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.chairman_member = member_services.register_member(community=self.bodi, full_name="Method Chairman", gender="male", family=self.asona)
        self.chairman = User.objects.create_user(username="method_chairman", password="a-real-password-123", community=self.bodi, role=Role.CHAIRMAN)
        member_services.link_member_to_user(member=self.chairman_member, user=self.chairman, actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_registering_a_new_member_is_blocked_in_personal_context(self):
        client = self._login("method_chairman")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        res = client.post("/api/members/", {"full_name": "Should Be Blocked", "gender": "male"})
        self.assertEqual(res.status_code, 403)

    def test_viewing_the_member_roster_still_works_in_personal_context(self):
        """The whole point of the method-aware variant — GET is never blocked."""
        client = self._login("method_chairman")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        res = client.get("/api/members/")
        self.assertEqual(res.status_code, 200)

    def test_editing_an_existing_member_is_blocked_in_personal_context(self):
        client = self._login("method_chairman")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        res = client.patch(f"/api/members/{self.chairman_member.id}/", {"phone": "0200000000"}, content_type="application/json")
        self.assertEqual(res.status_code, 403)

    def test_registering_still_works_normally_back_in_executive_context(self):
        client = self._login("method_chairman")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        client.post("/api/auth/switch-context/", {"context": "executive"})
        res = client.post("/api/members/", {"full_name": "Should Work Now", "gender": "female"})
        self.assertEqual(res.status_code, 201)

    def test_assigning_a_new_task_is_blocked_in_personal_context(self):
        target = member_services.register_member(community=self.bodi, full_name="Task Target", gender="female", family=self.asona)
        client = self._login("method_chairman")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        res = client.post("/api/tasks/", {"assigned_to": str(target.id), "title": "Should be blocked"})
        self.assertEqual(res.status_code, 403)

    def test_updating_the_status_of_my_own_assigned_task_still_works_in_personal_context(self):
        """The actual reason a method-based (not action-based) check would have been wrong — this is a PATCH, not a safe method, but must still work."""
        from tasks import services as task_services
        task = task_services.assign_task(community=self.bodi, assigned_to=self.chairman_member, title="My own task", assigned_by=self.admin)

        client = self._login("method_chairman")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        res = client.patch(f"/api/tasks/{task.id}/", {"status": "in_progress"}, content_type="application/json")
        self.assertEqual(res.status_code, 200)

    def test_viewing_tasks_still_works_in_personal_context(self):
        client = self._login("method_chairman")
        client.post("/api/auth/switch-context/", {"context": "personal"})
        res = client.get("/api/tasks/")
        self.assertEqual(res.status_code, 200)


class ExecutiveDashboardNeverShowsDonationsReceivedTests(TestCase):
    """
    'None of the executive dashboard should have access to receive
    gifts.' Since Personal Dashboard gives every executive the exact
    same _member_view an ordinary Community Member gets, this section
    must be genuinely absent for them there too — not just always
    empty, which would still look like the feature exists.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-exec-no-donations")
        self.admin = User.objects.create_user(username="exec_donations_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Exec Treasurer", gender="male", family=self.asona)
        self.treasurer = User.objects.create_user(username="exec_donations_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer, actor=self.admin)

        self.plain_member = member_services.register_member(community=self.bodi, full_name="Exec Plain Member", gender="male", family=self.asona)
        self.plain_member_user = User.objects.create_user(username="exec_donations_plain_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.plain_member, user=self.plain_member_user, actor=self.admin)

    def test_an_executive_on_personal_dashboard_has_no_donations_received_section_at_all(self):
        from accounts import services as account_services
        from dashboard.services import build_dashboard

        account_services.switch_dashboard_context(user=self.treasurer, context="personal")
        self.treasurer.refresh_from_db()
        result = build_dashboard(self.treasurer)
        self.assertIsNone(result["sections"]["member_overview"]["donations_received"])

    def test_an_ordinary_member_still_has_the_donations_received_section(self):
        """The fix is specific to executives — an ordinary member's own Personal Dashboard is completely unaffected."""
        from dashboard.services import build_dashboard

        result = build_dashboard(self.plain_member_user)
        self.assertIsNotNone(result["sections"]["member_overview"]["donations_received"])

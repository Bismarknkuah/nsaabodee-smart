from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from audit_log import services as audit_services
from audit_log.models import AuditLogEntry
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants import services as tenant_services
from tenants.models import Community


class CommunityLifecycleAuditTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(username="audit_platform_admin", password="x", role=Role.PLATFORM_ADMIN)

    def test_creating_a_community_records_an_audit_entry(self):
        community, admin = tenant_services.onboard_new_community(
            community_name="Audit Test Town", admin_username="audit_town_admin", admin_password="a-real-password-123",
            actor=self.platform_admin,
        )
        entry = AuditLogEntry.objects.get(category="community", action="community_created")
        self.assertEqual(entry.community_id, community.id)
        self.assertEqual(entry.actor_username, "audit_platform_admin")
        self.assertIn("Audit Test Town", entry.description)

    def test_deactivating_and_reactivating_a_community_records_both(self):
        community = Community.objects.create(name="Deactivate Me", slug="deactivate-me-audit")
        tenant_services.deactivate_community(community, actor=self.platform_admin)
        tenant_services.reactivate_community(community, actor=self.platform_admin)
        self.assertTrue(AuditLogEntry.objects.filter(community=community, action="community_deactivated").exists())
        self.assertTrue(AuditLogEntry.objects.filter(community=community, action="community_reactivated").exists())

    def test_extending_access_records_the_new_expiry_in_the_description(self):
        community = Community.objects.create(name="Extend Me", slug="extend-me-audit")
        tenant_services.set_community_access_expiration(community=community, days_from_now=5)
        tenant_services.extend_community_access(community=community, additional_days=30, actor=self.platform_admin)
        entry = AuditLogEntry.objects.get(community=community, action="community_access_extended")
        self.assertIn("30 day", entry.description)


class RoleAssignmentAuditTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-audit-role")
        self.admin = User.objects.create_user(username="audit_role_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Audit Test Member", gender="male", family=self.asona)

    def test_assigning_a_new_role_with_a_new_login_records_an_entry(self):
        member_services.assign_role_to_member(member=self.member, role="collector", actor=self.admin, username="audit_new_collector", password="a-real-password-123")
        entry = AuditLogEntry.objects.get(category="role", action="role_assigned")
        self.assertIn("collector", entry.description)
        self.assertEqual(entry.metadata["new_role"], "collector")

    def test_changing_an_existing_users_role_records_the_old_and_new_role(self):
        existing_user = User.objects.create_user(username="audit_existing_user", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=existing_user, actor=self.admin)
        member_services.assign_role_to_member(member=self.member, role="treasurer", actor=self.admin)
        entry = AuditLogEntry.objects.get(category="role", action="role_changed")
        self.assertEqual(entry.metadata["old_role"], "community_member")
        self.assertEqual(entry.metadata["new_role"], "treasurer")


class FuneralAndPaymentReversalAuditTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-audit-funeral",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="audit_funeral_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="audit_funeral_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="audit_funeral_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_a_funeral_opening_being_approved_into_active_records_an_entry(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Audit Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        # The requester (self.admin) can never be one of the approvers —
        # self-approval prevention correctly rejects that. Both real
        # approvals here come from people who didn't request it.
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.chairman)
        funeral_services.approve_funeral_opening(funeral=funeral, approver=self.secretary)
        entry = AuditLogEntry.objects.get(category="funeral_opening", action="funeral_opening_approved")
        self.assertEqual(entry.target_label, "Audit Deceased")

    def test_a_funeral_opening_being_rejected_records_an_entry_not_an_approval(self):
        funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Audit Rejected Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        funeral_services.reject_funeral_opening(funeral=funeral, actor=self.admin)
        self.assertTrue(AuditLogEntry.objects.filter(category="funeral_opening", action="funeral_opening_rejected").exists())
        self.assertFalse(AuditLogEntry.objects.filter(category="funeral_opening", action="funeral_opening_approved").exists())

    def test_a_payment_reversal_being_approved_records_who_requested_and_who_approved(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Audit Reversal Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        member = member_services.register_member(community=self.bodi, full_name="Reversal Payer", gender="male", family=self.asona)
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=member)
        payment = funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector=self.admin)

        reversal = funeral_services.request_payment_reversal(payment=payment, reason="Recorded against the wrong member", actor=self.secretary)
        funeral_services.approve_payment_reversal(reversal=reversal, actor=self.admin)

        entry = AuditLogEntry.objects.get(category="payment_reversal", action="payment_reversal_approved")
        self.assertIn("audit_funeral_secretary", entry.description)
        self.assertEqual(entry.actor_username, "audit_funeral_admin")


class AuditLogScopingTests(TestCase):
    """The safety-critical part — who can see what."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(username="audit_scope_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-audit-scope")
        self.other_community = Community.objects.create(name="Other Town", slug="other-audit-scope")
        self.bodi_admin = User.objects.create_user(username="audit_scope_bodi_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_admin = User.objects.create_user(username="audit_scope_other_admin", password="a-real-password-123", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        self.ordinary_member = User.objects.create_user(username="audit_scope_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)

        tenant_services.deactivate_community(self.bodi, actor=self.platform_admin)
        tenant_services.deactivate_community(self.other_community, actor=self.platform_admin)

    def test_platform_admin_sees_entries_from_every_community(self):
        entries = audit_services.list_audit_log(actor=self.platform_admin)
        communities_seen = {e.community_id for e in entries}
        self.assertIn(self.bodi.id, communities_seen)
        self.assertIn(self.other_community.id, communities_seen)

    def test_a_community_admin_sees_only_their_own_communitys_entries(self):
        entries = audit_services.list_audit_log(actor=self.bodi_admin)
        self.assertTrue(all(e.community_id == self.bodi.id for e in entries))
        self.assertTrue(len(entries) > 0)

    def test_a_community_admin_cannot_request_another_communitys_entries(self):
        with self.assertRaises(ValidationError):
            audit_services.list_audit_log(actor=self.bodi_admin, community=self.other_community)

    def test_an_ordinary_member_cannot_view_the_audit_log_at_all(self):
        with self.assertRaises(ValidationError):
            audit_services.list_audit_log(actor=self.ordinary_member)

    def test_full_http_round_trip_platform_admin_vs_community_admin(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "audit_scope_platform_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/audit-log/")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data), 2)

        client2 = APIClient()
        login2 = client2.post("/api/auth/login/", {"username": "audit_scope_bodi_admin", "password": "a-real-password-123"})
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {login2.data['access']}")
        res2 = client2.get("/api/audit-log/")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(all(e["community_name"] == "Bodi Anidasoɔ" for e in res2.data))

    def test_the_http_endpoint_rejects_an_ordinary_member_with_403_not_a_crash(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "audit_scope_member", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/audit-log/")
        self.assertEqual(res.status_code, 403)

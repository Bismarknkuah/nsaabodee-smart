from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts import services as account_services
from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class UserManagementUpgradeTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="umu-bodi")
        self.admin = User.objects.create_user(username="umu_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="umu_chair", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head = User.objects.create_user(username="umu_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        m = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        member_services.link_member_to_user(member=m, user=self.head, actor=self.admin)

    # --- rename role positions ---
    def test_admin_renames_a_position_and_the_label_follows(self):
        account_services.set_role_titles(community=self.bodi, titles={"chairman": "President", "family_head": "Abusuapanin"}, actor=self.admin)
        self.chairman.refresh_from_db(); self.head.refresh_from_db()
        self.assertEqual(account_services.role_label_for(self.chairman), "President")
        self.assertEqual(account_services.role_label_for(self.head), "Asona Abusuapanin")

    def test_an_empty_title_restores_the_default(self):
        account_services.set_role_titles(community=self.bodi, titles={"chairman": "President"}, actor=self.admin)
        account_services.set_role_titles(community=self.bodi, titles={"chairman": ""}, actor=self.admin)
        self.chairman.refresh_from_db()
        self.assertEqual(account_services.role_label_for(self.chairman), "Chairman")

    def test_only_the_admin_renames(self):
        with self.assertRaises(ValidationError):
            account_services.set_role_titles(community=self.bodi, titles={"chairman": "President"}, actor=self.chairman)

    # --- edit details / reset password ---
    def test_admin_edits_a_managed_users_details(self):
        account_services.update_user_details(actor=self.admin, target=self.head, email="head@example.com", phone_number="0244000001", full_name="Renamed Head")
        self.head.refresh_from_db()
        self.assertEqual(self.head.email, "head@example.com")
        self.assertEqual(self.head.member_profile.full_name, "Renamed Head")

    def test_reset_password_works_for_managed_users_and_is_audit_logged(self):
        from audit_log.models import AuditLogEntry
        account_services.admin_reset_password(actor=self.admin, target=self.head, new_password="a-brand-new-password")
        self.head.refresh_from_db()
        self.assertTrue(self.head.check_password("a-brand-new-password"))
        self.assertTrue(AuditLogEntry.objects.filter(action="password_reset_by_manager", target_id=self.head.id).exists())
        with self.assertRaises(ValidationError):
            account_services.admin_reset_password(actor=self.admin, target=self.admin, new_password="not-from-here")

    # --- the admin restricting themselves ---
    def test_admin_appears_in_their_own_manageable_list_and_can_restrict_themselves(self):
        ids = {u.id for u in account_services.list_manageable_users(actor=self.admin)}
        self.assertIn(self.admin.id, ids)
        account_services.set_disabled_features(target=self.admin, features=["/reports"], actor=self.admin)
        self.admin.refresh_from_db()
        self.assertIn("/reports", self.admin.disabled_features)

    def test_admin_can_never_lock_themselves_out_of_settings(self):
        with self.assertRaises(ValidationError):
            account_services.set_disabled_features(target=self.admin, features=["/system-settings"], actor=self.admin)
        with self.assertRaises(ValidationError):
            account_services.set_disabled_features(target=self.admin, features=["/user-management"], actor=self.admin)

    def test_a_chairman_still_cannot_restrict_themselves(self):
        with self.assertRaises(ValidationError):
            account_services.set_disabled_features(target=self.chairman, features=["/reports"], actor=self.chairman)

    def test_endpoints(self):
        c = APIClient(); c.force_authenticate(self.admin)
        self.assertEqual(c.patch("/api/accounts/role-titles/", {"titles": {"secretary": "Scribe"}}, format="json").status_code, 200)
        data = c.get("/api/accounts/manageable-users/").data
        self.assertEqual(data["role_titles"], {"secretary": "Scribe"})
        self.assertTrue(any(u["is_self"] for u in data["users"]))
        self.assertEqual(c.patch(f"/api/accounts/manageable-users/{self.head.id}/details/", {"email": "h2@example.com"}, format="json").status_code, 200)
        self.assertEqual(c.post(f"/api/accounts/manageable-users/{self.head.id}/reset-password/", {"new_password": "another-new-password"}).status_code, 200)
        ch = APIClient(); ch.force_authenticate(self.chairman)
        self.assertEqual(ch.patch("/api/accounts/role-titles/", {"titles": {"secretary": "X"}}, format="json").status_code, 403)

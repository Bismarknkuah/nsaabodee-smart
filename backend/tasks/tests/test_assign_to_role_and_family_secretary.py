from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts import services as account_services
from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tasks import services as task_services
from tasks.models import MemberTask
from tenants.models import Community


class AssignToRoleAndFamilySecretaryTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="atr-bodi")
        self.admin = User.objects.create_user(username="atr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        def make(username, role, family):
            user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
            member = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
            member_services.link_member_to_user(member=member, user=user, actor=self.admin)
            return user, member

        self.secretary, _ = make("atr_family_secretary", Role.FAMILY_SECRETARY, self.asona)
        self.asona_collector, self.asona_collector_member = make("atr_asona_collector", Role.COLLECTOR, self.asona)
        self.bretuo_collector, self.bretuo_collector_member = make("atr_bretuo_collector", Role.COLLECTOR, self.bretuo)
        self.asona_member, self.asona_member_member = make("atr_asona_member", Role.COMMUNITY_MEMBER, self.asona)

    # --- "assign specific tasks to each user role type" ---

    def test_admin_assigns_one_task_to_every_collector_in_the_community(self):
        result = task_services.assign_task_to_role(actor=self.admin, role="collector", title="Reconcile your tape")
        self.assertEqual(result["assigned_count"], 2)
        self.assertEqual(MemberTask.objects.filter(title="Reconcile your tape").count(), 2)

    def test_a_family_secretary_reaches_only_collectors_in_their_own_family(self):
        """'...should have options to assign tasks to family members only.'"""
        result = task_services.assign_task_to_role(actor=self.secretary, role="collector", title="Family reminder")
        self.assertEqual(result["assigned_count"], 1)
        self.assertEqual(MemberTask.objects.get(title="Family reminder").assigned_to_id, self.asona_collector_member.id)

    def test_a_family_secretary_cannot_assign_a_single_task_across_the_family_line(self):
        task_services.assign_task(community=self.bodi, assigned_to=self.asona_member_member, title="Ok", assigned_by=self.secretary)
        with self.assertRaises(ValidationError):
            task_services.assign_task(community=self.bodi, assigned_to=self.bretuo_collector_member, title="Not ok", assigned_by=self.secretary)

    def test_a_plain_member_cannot_bulk_assign(self):
        with self.assertRaises(ValidationError):
            task_services.assign_task_to_role(actor=self.asona_member, role="collector", title="Nope")

    def test_assign_to_role_endpoint(self):
        c = APIClient(); c.force_authenticate(self.admin)
        res = c.post("/api/tasks/assign-to-role/", {"role": "collector", "title": "Endpoint task"})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["assigned_count"], 2)

    # --- "each family secretary should also have these features to manage their family, but shouldn't have more options" ---

    def test_family_secretary_gets_the_family_subset_of_restrictable_features_not_the_full_catalogue(self):
        subset = account_services.restrictable_features_for(self.secretary)
        full = account_services.restrictable_features_for(self.admin)
        self.assertEqual(set(subset), set(account_services.FAMILY_HEAD_RESTRICTABLE_FEATURES))
        self.assertLess(len(subset), len(full))
        self.assertNotIn("/audit-log", subset)

    def test_family_secretary_can_restrict_a_member_of_their_own_family_but_not_another_familys(self):
        from accounts.permissions import can_restrict_features_for
        self.assertTrue(can_restrict_features_for(self.secretary, self.asona_member))
        self.assertFalse(can_restrict_features_for(self.secretary, self.bretuo_collector))

    def test_the_catalogue_now_includes_the_newer_pages_and_is_grouped(self):
        full = account_services.restrictable_features_for(self.admin)
        for href in ("/members/analytics", "/arrears-desk", "/arrears-corrections", "/user-management", "/defaulters"):
            self.assertIn(href, full)
        groups = account_services.feature_groups_for(full)
        self.assertIn("Finance & Oversight", groups)
        self.assertTrue(all(h in full for hrefs in groups.values() for h in hrefs))

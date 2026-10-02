from django.test import TestCase
from rest_framework.test import APIClient

from accounts import services as account_services
from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class FamilyQualifiedRoleLabelTests(TestCase):
    """'Instead of family head, let's make Asona family head; instead of family secretary, Asona secretary... Bretuo treasurer, Bretuo collector.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="frl-bodi")
        self.admin = User.objects.create_user(username="frl_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

    def _user(self, username, role, family=None):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
        if family is not None:
            member = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
            member_services.link_member_to_user(member=member, user=user, actor=self.admin)
        return user

    def test_every_family_role_carries_its_family_name(self):
        expected = {
            Role.FAMILY_HEAD: "Asona Family Head", Role.FAMILY_SECRETARY: "Asona Secretary", Role.FAMILY_TREASURER: "Asona Treasurer",
            Role.FAMILY_REGISTRATION_OFFICER: "Asona Registration Officer", Role.FAMILY_ARREARS_OFFICER: "Asona Arrears Officer",
        }
        for role, label in expected.items():
            self.assertEqual(account_services.role_label_for(self._user(f"frl_{role}", role, self.asona)), label)

    def test_the_same_role_in_another_family_reads_as_that_family(self):
        self.assertEqual(account_services.role_label_for(self._user("frl_b_sec", Role.FAMILY_SECRETARY, self.bretuo)), "Bretuo Secretary")

    def test_community_roles_stay_generic(self):
        self.assertEqual(account_services.role_label_for(self._user("frl_chair", Role.CHAIRMAN)), "Chairman")
        self.assertEqual(account_services.role_label_for(self._user("frl_ac", Role.ARREARS_COLLECTOR)), "Community Arrears Officer")
        self.assertEqual(account_services.role_label_for(self._user("frl_col", Role.COLLECTOR, self.asona)), "Collector")

    def test_a_family_nominated_collector_reads_as_that_familys_collector(self):
        user = self._user("frl_fam_col", Role.COMMUNITY_MEMBER, self.bretuo)
        head = self._user("frl_b_head", Role.FAMILY_HEAD, self.bretuo)
        nomination = member_services.nominate_collector(member=user.member_profile, collector_type="family", actor=head)
        from members.models import CollectorNomination
        CollectorNomination.objects.filter(id=nomination.id).update(status=CollectorNomination.Status.APPROVED)
        user.role = Role.COLLECTOR; user.save(update_fields=["role"])
        self.assertEqual(account_services.role_label_for(user), "Bretuo Collector")

    def test_the_label_reaches_me_and_the_user_management_list(self):
        sec = self._user("frl_me_sec", Role.FAMILY_SECRETARY, self.asona)
        c = APIClient(); c.force_authenticate(sec)
        self.assertEqual(c.get("/api/auth/me/").data["role_label"], "Asona Secretary")
        a = APIClient(); a.force_authenticate(self.admin)
        rows = {u["username"]: u for u in a.get("/api/accounts/manageable-users/").data["users"]}
        self.assertEqual(rows["frl_me_sec"]["role_label"], "Asona Secretary")

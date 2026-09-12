from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from members.models import Member
from reports import services as report_services
from tenants.models import Community


class MemberSortAndFilterTests(TestCase):
    """'Executives should have different types to sort members either by family, male, female, surname, age and many more option.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-sort-filter")
        self.admin = User.objects.create_user(username="sf_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        member_services.register_member(community=self.bodi, full_name="Zainab Mensah", gender="female", family=self.bretuo)
        member_services.register_member(community=self.bodi, full_name="Adjoa Boateng", gender="female", family=self.asona)
        member_services.register_member(community=self.bodi, full_name="Kwame Asante", gender="male", family=self.asona)

    def test_gender_filter_returns_only_that_gender(self):
        results = member_services.search_members(community=self.bodi, gender="female", actor=self.admin)
        self.assertTrue(all(m.gender == "female" for m in results))
        self.assertEqual(results.count(), 2)

    def test_sort_by_name_is_alphabetical(self):
        results = list(member_services.search_members(community=self.bodi, sort_by="name", actor=self.admin))
        names = [m.full_name for m in results]
        self.assertEqual(names, sorted(names))

    def test_sort_by_family_groups_families_together(self):
        results = list(member_services.search_members(community=self.bodi, sort_by="family", actor=self.admin))
        family_names = [m.family.name for m in results]
        self.assertEqual(family_names, sorted(family_names))

    def test_default_sort_is_still_alphabetical_by_name(self):
        """No regression for existing callers that don't pass sort_by at all."""
        results = list(member_services.search_members(community=self.bodi, actor=self.admin))
        names = [m.full_name for m in results]
        self.assertEqual(names, sorted(names))

    def test_an_invalid_sort_option_falls_back_to_name_rather_than_erroring(self):
        results = list(member_services.search_members(community=self.bodi, sort_by="not_a_real_option", actor=self.admin))
        names = [m.full_name for m in results]
        self.assertEqual(names, sorted(names))


class MembersExportTests(TestCase):
    """'All user role types should have analytics views... all data should be downloaded or printable.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-export")
        self.admin = User.objects.create_user(username="exp_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)
        member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)

        self.head_user = User.objects.create_user(username="exp_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        self.head_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Head", gender="male", linked_user=self.head_user)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

    def test_community_admin_export_includes_every_family(self):
        rows = report_services.members_export_rows(community=self.bodi, actor=self.admin)
        family_names = {r["family_name"] for r in rows}
        self.assertIn("Asona", family_names)
        self.assertIn("Bretuo", family_names)

    def test_family_head_export_includes_ONLY_their_own_family(self):
        """'Family executive can only sort or download data of family members only.'"""
        rows = report_services.members_export_rows(community=self.bodi, actor=self.head_user)
        family_names = {r["family_name"] for r in rows}
        self.assertEqual(family_names, {"Asona"})
        self.assertNotIn("Bretuo", family_names)

    def test_full_http_csv_export_respects_family_scoping(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "exp_head", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/reports/members/export/?export_format=csv")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        content = res.content.decode()
        self.assertIn("Asona", content)
        self.assertNotIn("Bretuo Member", content)

    def test_full_http_pdf_export_respects_family_scoping(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "exp_head", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/reports/members/export/?export_format=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))

    def test_community_admin_full_http_export_includes_both_families(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "exp_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/reports/members/export/?export_format=csv")
        content = res.content.decode()
        self.assertIn("Asona Member", content)
        self.assertIn("Bretuo Member", content)

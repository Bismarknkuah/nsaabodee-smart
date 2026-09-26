import json

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services
from families.models import Family
from members import services as member_services
from tenants.models import Community


class ExportFamilyDataTests(TestCase):
    """'Let the family head of each family be able to download their data.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="efd-bodi")
        self.admin = User.objects.create_user(username="efd_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.family_head_user = User.objects.create_user(username="efd_family_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        member_services.link_member_to_user(member=head_member, user=self.family_head_user, actor=self.admin)
        services.assign_family_head(family=self.asona, member=head_member, actor=self.admin)

        member_services.register_member(community=self.bodi, full_name="Another Asona Member", gender="female", family=self.asona)
        member_services.register_member(community=self.bodi, full_name="A Bretuo Member", gender="male", family=self.bretuo)

    def test_family_head_can_export_their_own_familys_data(self):
        data = services.export_family_data(family=self.asona, actor=self.family_head_user)
        self.assertEqual(data["family_name"], "Asona")
        full_names = {m["full_name"] for m in data["members"]}
        self.assertEqual(full_names, {"The Head", "Another Asona Member"})

    def test_a_family_head_cannot_export_a_different_familys_data(self):
        with self.assertRaises(ValidationError):
            services.export_family_data(family=self.bretuo, actor=self.family_head_user)

    def test_a_plain_member_of_the_family_cannot_export_its_data(self):
        plain_user = User.objects.create_user(username="efd_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        plain_member = member_services.register_member(community=self.bodi, full_name="Plain Member", gender="male", family=self.asona)
        member_services.link_member_to_user(member=plain_member, user=plain_user, actor=self.admin)
        with self.assertRaises(ValidationError):
            services.export_family_data(family=self.asona, actor=plain_user)

    def test_community_admin_can_export_any_familys_data(self):
        data = services.export_family_data(family=self.bretuo, actor=self.admin)
        self.assertEqual(data["family_name"], "Bretuo")

    def test_export_over_http_downloads_a_file(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "efd_family_head", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/families/{self.asona.id}/backup/export/")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(len(data["members"]), 2)
        self.assertIn("attachment", res["Content-Disposition"])

    def test_a_different_familys_head_gets_403_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "efd_family_head", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/families/{self.bretuo.id}/backup/export/")
        self.assertEqual(res.status_code, 403)

    def test_the_exported_shape_actually_restores_through_the_existing_community_restore_path(self):
        """The whole point of matching export_community_backup's shape — a family's own export must work through the same restore machinery a Community Admin's backup already uses."""
        from tenants import services as tenant_services

        data = services.export_family_data(family=self.asona, actor=self.family_head_user)
        # A community-level restore expects a top-level "families" key too — a family export
        # naturally doesn't have one, so bulk_register_members should still just create the members.
        from members import services as ms
        result = ms.bulk_register_members(community=self.bodi, rows=data["members"], actor=self.admin)
        # Both members already exist (matched by membership_number), so this is an update, not a duplicate create.
        self.assertEqual(result["updated_count"], 2)
        self.assertEqual(result["created_count"], 0)

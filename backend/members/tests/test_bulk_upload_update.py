from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class BulkUpdateViaUploadTests(TestCase):
    """'Each family should have access to their database and they can download it or upload to update it.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="buvu-bodi")
        self.admin = User.objects.create_user(username="buvu_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Original Name", gender="male", family=self.asona, phone="0200000000")

    def test_a_row_with_a_matching_membership_number_updates_the_existing_member(self):
        rows = [{"membership_number": self.member.membership_number, "phone": "0244444444", "hometown": "Kumasi"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(result["created_count"], 0)
        self.member.refresh_from_db()
        self.assertEqual(self.member.phone, "0244444444")
        self.assertEqual(self.member.hometown, "Kumasi")

    def test_a_row_with_no_membership_number_still_creates_a_new_member_as_before(self):
        rows = [{"full_name": "Brand New Person", "gender": "male", "family_name": "Asona"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["updated_count"], 0)

    def test_an_unknown_membership_number_is_reported_as_an_error_not_a_new_registration(self):
        rows = [{"membership_number": "NONEXISTENT-000", "phone": "0200000001"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["created_count"], 0)

    def test_a_family_heads_upload_can_only_update_their_own_familys_members(self):
        bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)
        head_user = User.objects.create_user(username="buvu_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        head_member = member_services.register_member(community=self.bodi, full_name="Head", gender="male", family=self.asona)
        member_services.link_member_to_user(member=head_member, user=head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=head_member, actor=self.admin)

        rows = [{"membership_number": bretuo_member.membership_number, "phone": "0299999999"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=head_user)
        self.assertEqual(result["error_count"], 1)
        bretuo_member.refresh_from_db()
        self.assertNotEqual(bretuo_member.phone, "0299999999")

    def test_a_row_with_only_the_membership_number_and_no_actual_changes_is_reported_but_not_an_error(self):
        rows = [{"membership_number": self.member.membership_number}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["updated_count"], 1)


class ExpandedExportFieldsTests(TestCase):
    """The exported CSV must carry enough fields to be a genuine round-trip working copy, not just a summary report."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="eef-bodi")
        self.admin = User.objects.create_user(username="eef_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        member_services.register_member(
            community=self.bodi, full_name="Full Record Member", gender="male", family=self.asona,
            mother_name="Mother Name", father_name="Father Name", hometown="Tamale",
        )

    def test_export_rows_include_the_new_background_fields(self):
        from reports.services import members_export_rows
        rows = members_export_rows(community=self.bodi, actor=self.admin)
        row = next(r for r in rows if r["full_name"] == "Full Record Member")
        self.assertEqual(row["mother_name"], "Mother Name")
        self.assertEqual(row["father_name"], "Father Name")
        self.assertEqual(row["hometown"], "Tamale")
        self.assertIn("membership_number", row)

    def test_full_http_csv_export_includes_the_new_columns(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "eef_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/reports/members/export/")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        self.assertIn("mother_name", content)
        self.assertIn("Mother Name", content)


class TraditionalLeaderCommunityWideExportTests(TestCase):
    """'Same as the community admin should have access to download the community database... same applies to the town leader.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tlce-bodi")
        self.admin = User.objects.create_user(username="tlce_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="tlce_chief", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)
        member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="male", family=self.bretuo)

    def test_the_traditional_leader_already_sees_the_full_community_wide_roster_not_just_elders(self):
        from reports.services import members_export_rows
        rows = members_export_rows(community=self.bodi, actor=self.chief)
        names = {r["full_name"] for r in rows}
        self.assertIn("Asona Member", names)
        self.assertIn("Bretuo Member", names)

    def test_the_traditional_leader_can_upload_to_update_a_member_in_any_family(self):
        bretuo_member = member_services.register_member(community=self.bodi, full_name="Update Target", gender="male", family=self.bretuo)
        rows = [{"membership_number": bretuo_member.membership_number, "hometown": "Sunyani"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.chief)
        self.assertEqual(result["updated_count"], 1)
        bretuo_member.refresh_from_db()
        self.assertEqual(bretuo_member.hometown, "Sunyani")

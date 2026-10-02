import io

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class BulkRegisterMembersServiceTests(TestCase):
    """'Executive should have access to upload data when necessary.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-bulk-upload")
        self.admin = User.objects.create_user(username="bu_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

    def test_community_admin_can_bulk_register_into_any_family(self):
        rows = [
            {"full_name": "Kwame Asante", "gender": "male", "family_name": "Asona"},
            {"full_name": "Ama Boateng", "gender": "female", "family_name": "Bretuo"},
        ]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["error_count"], 0)
        families = set(Member.objects.filter(community=self.bodi).values_list("family__name", flat=True))
        self.assertEqual(families, {"Asona", "Bretuo"})

    def test_a_row_with_missing_gender_fails_without_aborting_the_rest_of_the_batch(self):
        rows = [
            {"full_name": "Bad Row", "gender": ""},
            {"full_name": "Good Row", "gender": "male", "family_name": "Asona"},
        ]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["errors"][0]["row"], 1)
        self.assertTrue(Member.objects.filter(full_name="Good Row").exists())

    def test_an_unknown_family_name_is_reported_as_a_row_error(self):
        rows = [{"full_name": "Someone", "gender": "male", "family_name": "Nonexistent Family"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["error_count"], 1)
        self.assertIn("Nonexistent Family", result["errors"][0]["error"])

    def test_family_head_bulk_upload_is_now_blocked_the_same_way_a_single_registration_is(self):
        """
        'The family secretary will be responsible for all adding
        members.' Bulk upload calls the exact same register_member
        underneath, row by row — the same restriction that now blocks
        a single registration correctly blocks every row of a bulk
        upload too, reported as a per-row error rather than a crash.
        """
        head_user = User.objects.create_user(username="bu_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        head_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Head", gender="male", linked_user=head_user)
        family_services.assign_family_head(family=self.asona, member=head_member, actor=self.admin)

        rows = [{"full_name": "Sneaky Row", "gender": "male", "family_name": "Bretuo"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=head_user)
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["error_count"], 1)
        self.assertFalse(Member.objects.filter(full_name="Sneaky Row").exists())

    def test_family_secretary_bulk_upload_still_goes_into_their_own_family_regardless_of_csv_content(self):
        """The same own-family-only restriction Family Head used to be tested under — Family Secretary is the one who still has this authority now."""
        secretary_user = User.objects.create_user(username="bu_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        Member.objects.create(community=self.bodi, family=self.asona, full_name="The Secretary", gender="male", linked_user=secretary_user)

        rows = [{"full_name": "Sneaky Row", "gender": "male", "family_name": "Bretuo"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=secretary_user)
        self.assertEqual(result["created_count"], 1)
        created_member = Member.objects.get(full_name="Sneaky Row")
        self.assertEqual(created_member.family_id, self.asona.id)
        self.assertNotEqual(created_member.family_id, self.bretuo.id)

    def test_duplicate_detection_still_applies_per_row(self):
        member_services.register_member(community=self.bodi, full_name="Existing Person", gender="male", phone="0244000000", family=self.asona)
        rows = [{"full_name": "Existing Person", "gender": "male", "phone": "0244000000", "family_name": "Asona"}]
        result = member_services.bulk_register_members(community=self.bodi, rows=rows, actor=self.admin)
        self.assertEqual(result["error_count"], 1)


class BulkUploadHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-bulk-upload-http")
        self.admin = User.objects.create_user(username="buh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def _csv_file(self, content: str):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile("members.csv", content.encode("utf-8"), content_type="text/csv")

    def test_full_http_bulk_upload_round_trip(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "buh_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        csv_content = "full_name,gender,family_name\nKofi Mensah,male,Asona\n"
        res = client.post("/api/members/bulk-upload/", {"file": self._csv_file(csv_content)}, format="multipart")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["created_count"], 1)
        self.assertTrue(Member.objects.filter(full_name="Kofi Mensah").exists())

    def test_bulk_upload_with_no_file_returns_a_clear_error(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "buh_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post("/api/members/bulk-upload/", {}, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_a_plain_member_cannot_bulk_upload(self):
        plain_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Plain", gender="male")
        plain_user = User.objects.create_user(username="buh_plain", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        plain_member.linked_user = plain_user
        plain_member.save()

        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "buh_plain", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        csv_content = "full_name,gender\nShould Not Work,male\n"
        res = client.post("/api/members/bulk-upload/", {"file": self._csv_file(csv_content)}, format="multipart")
        self.assertEqual(res.status_code, 403)

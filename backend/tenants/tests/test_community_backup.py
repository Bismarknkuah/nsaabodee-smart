import json
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from families.models import Family
from members import services as member_services
from members.models import Member
from tenants import services
from tenants.models import Community, CommunityBackupRecord


class DriveLinkParsingTests(TestCase):
    """'Import a Google Drive link' — the handful of real shapes Drive's own Share button actually produces."""

    def test_a_standard_file_view_link_is_parsed_correctly(self):
        link = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567/view?usp=sharing"
        self.assertEqual(services._extract_google_drive_file_id(link), "1AbCdEfGhIjKlMnOpQrStUvWxYz1234567")

    def test_an_open_id_style_link_is_parsed_correctly(self):
        link = "https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQrStUvWxYz1234567"
        self.assertEqual(services._extract_google_drive_file_id(link), "1AbCdEfGhIjKlMnOpQrStUvWxYz1234567")

    def test_a_bare_file_id_is_accepted_directly(self):
        self.assertEqual(services._extract_google_drive_file_id("1AbCdEfGhIjKlMnOpQrStUvWxYz1234567"), "1AbCdEfGhIjKlMnOpQrStUvWxYz1234567")

    def test_a_completely_unrelated_url_is_rejected_with_a_clear_message(self):
        with self.assertRaises(ValidationError):
            services._extract_google_drive_file_id("https://example.com/not-a-drive-link")


class ExportCommunityBackupTests(TestCase):
    """'Each community admin will have a section... where they can back up their system data.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ecb-bodi")
        self.bodi_admin = User.objects.create_user(username="ecb_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_community = Community.objects.create(name="Other Town", slug="ecb-other")
        self.other_admin = User.objects.create_user(username="ecb_other_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.bodi_admin)
        member_services.register_member(
            community=self.bodi, full_name="Test Member", gender="male", family=self.asona,
            mother_name="Mother Name", hometown="Kumasi",
        )

    def test_export_includes_families_and_members_with_full_fields(self):
        data = services.export_community_backup(community=self.bodi, actor=self.bodi_admin)
        self.assertEqual(len(data["families"]), 1)
        self.assertEqual(data["families"][0]["name"], "Asona")
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["mother_name"], "Mother Name")
        self.assertEqual(data["members"][0]["hometown"], "Kumasi")

    def test_a_different_communitys_admin_cannot_export(self):
        with self.assertRaises(ValidationError):
            services.export_community_backup(community=self.bodi, actor=self.other_admin)

    def test_exporting_creates_a_backup_record(self):
        services.export_community_backup(community=self.bodi, actor=self.bodi_admin)
        record = CommunityBackupRecord.objects.get(community=self.bodi, kind="export")
        self.assertEqual(record.member_count, 1)
        self.assertEqual(record.family_count, 1)
        self.assertEqual(record.performed_by, self.bodi_admin)


class RestoreCommunityBackupTests(TestCase):
    """'Should also have options to retrieve them back.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="rcb-bodi")
        self.bodi_admin = User.objects.create_user(username="rcb_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_community = Community.objects.create(name="Other Town", slug="rcb-other")
        self.other_admin = User.objects.create_user(username="rcb_other_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)

        self.backup_payload = {
            "community_name": "Bodi Anidasoɔ", "exported_at": "2026-01-01T00:00:00",
            "families": [{"name": "Asona", "description": "", "status": "active"}],
            "members": [{"full_name": "Restored Member", "gender": "male", "family_name": "Asona"}],
        }
        self.drive_link = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567/view"

    def _mock_response(self, payload):
        mock_res = Mock()
        mock_res.raise_for_status = Mock()
        mock_res.json = Mock(return_value=payload)
        return mock_res

    def test_restoring_creates_the_family_and_member_from_the_backup(self):
        with patch("requests.get", return_value=self._mock_response(self.backup_payload)):
            result = services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.bodi_admin)
        self.assertEqual(result["families_restored"], 1)
        self.assertEqual(result["members_created"], 1)
        self.assertTrue(Family.objects.filter(community=self.bodi, name="Asona").exists())
        self.assertTrue(Member.objects.filter(community=self.bodi, full_name="Restored Member").exists())

    def test_restoring_twice_never_duplicates_the_family_or_member(self):
        with patch("requests.get", return_value=self._mock_response(self.backup_payload)):
            services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.bodi_admin)
            services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.bodi_admin)
        self.assertEqual(Family.objects.filter(community=self.bodi, name="Asona").count(), 1)
        self.assertEqual(Member.objects.filter(community=self.bodi, full_name="Restored Member").count(), 1)

    def test_restoring_an_existing_members_membership_number_updates_rather_than_duplicates(self):
        asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.bodi_admin)
        existing = member_services.register_member(community=self.bodi, full_name="Existing Member", gender="male", family=asona)
        payload = {"families": [], "members": [{"membership_number": existing.membership_number, "hometown": "Takoradi"}]}
        with patch("requests.get", return_value=self._mock_response(payload)):
            result = services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.bodi_admin)
        self.assertEqual(result["members_updated"], 1)
        existing.refresh_from_db()
        self.assertEqual(existing.hometown, "Takoradi")

    def test_a_different_communitys_admin_cannot_restore(self):
        with self.assertRaises(ValidationError):
            services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.other_admin)

    def test_a_network_failure_is_reported_clearly_not_as_a_500(self):
        import requests as http_requests
        with patch("requests.get", side_effect=http_requests.RequestException("connection failed")):
            with self.assertRaises(ValidationError):
                services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.bodi_admin)

    def test_a_non_json_file_is_reported_clearly(self):
        mock_res = Mock()
        mock_res.raise_for_status = Mock()
        mock_res.json = Mock(side_effect=json.JSONDecodeError("bad", "doc", 0))
        with patch("requests.get", return_value=mock_res):
            with self.assertRaises(ValidationError):
                services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.bodi_admin)

    def test_restoring_creates_a_backup_record_with_the_drive_link(self):
        with patch("requests.get", return_value=self._mock_response(self.backup_payload)):
            services.restore_community_backup_from_drive_link(community=self.bodi, drive_link=self.drive_link, actor=self.bodi_admin)
        record = CommunityBackupRecord.objects.get(community=self.bodi, kind="restore")
        self.assertEqual(record.drive_link, self.drive_link)


class BackupHttpEndpointTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bhe-bodi")
        self.bodi_admin = User.objects.create_user(username="bhe_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_community = Community.objects.create(name="Other Town", slug="bhe-other")
        self.other_admin = User.objects.create_user(username="bhe_other_admin", password="a-real-password-123", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.bodi_admin)
        member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_export_download_over_http(self):
        res = self._login("bhe_admin").get(f"/api/tenants/communities/{self.bodi.id}/backup/export/")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(len(data["members"]), 1)
        self.assertIn("attachment", res["Content-Disposition"])

    def test_a_different_communitys_admin_gets_403_on_export(self):
        res = self._login("bhe_other_admin").get(f"/api/tenants/communities/{self.bodi.id}/backup/export/")
        self.assertEqual(res.status_code, 403)

    def test_restore_over_http_with_mocked_drive_fetch(self):
        payload = {"families": [], "members": [{"full_name": "HTTP Restored", "gender": "female", "family_name": "Asona"}]}
        mock_res = Mock()
        mock_res.raise_for_status = Mock()
        mock_res.json = Mock(return_value=payload)
        with patch("requests.get", return_value=mock_res):
            res = self._login("bhe_admin").post(
                f"/api/tenants/communities/{self.bodi.id}/backup/restore/",
                {"drive_link": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567/view"},
                format="json",
            )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["members_created"], 1)

    def test_a_different_communitys_admin_gets_403_on_restore(self):
        res = self._login("bhe_other_admin").post(
            f"/api/tenants/communities/{self.bodi.id}/backup/restore/",
            {"drive_link": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567/view"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_backup_history_over_http(self):
        services.export_community_backup(community=self.bodi, actor=self.bodi_admin)
        res = self._login("bhe_admin").get(f"/api/tenants/communities/{self.bodi.id}/backup/history/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)


class MyCommunityBackupHttpTests(TestCase):
    """The 'my-community' shortcut endpoints, matching the existing self-service convention — the frontend never needs to know its own community's id."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="mcb-bodi")
        self.bodi_admin = User.objects.create_user(username="mcb_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.bodi_admin)
        member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mcb_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_my_community_export_over_http(self):
        res = self._login().get("/api/tenants/my-community/backup/export/")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(len(data["members"]), 1)

    def test_my_community_restore_over_http(self):
        payload = {"families": [], "members": [{"full_name": "My Community Restored", "gender": "female", "family_name": "Asona"}]}
        mock_res = Mock()
        mock_res.raise_for_status = Mock()
        mock_res.json = Mock(return_value=payload)
        with patch("requests.get", return_value=mock_res):
            res = self._login().post(
                "/api/tenants/my-community/backup/restore/",
                {"drive_link": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567/view"},
                format="json",
            )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["members_created"], 1)

    def test_my_community_history_over_http(self):
        services.export_community_backup(community=self.bodi, actor=self.bodi_admin)
        res = self._login().get("/api/tenants/my-community/backup/history/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_platform_admin_with_no_community_gets_a_clean_response_not_a_crash(self):
        platform_admin = User.objects.create_user(username="mcb_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mcb_platform_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/tenants/my-community/backup/export/")
        self.assertEqual(res.status_code, 400)


class RestoreFromUploadedFileTests(TestCase):
    """'Should also be able to upload from my computer to synchronize.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ruf-bodi")
        self.bodi_admin = User.objects.create_user(username="ruf_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_community = Community.objects.create(name="Other Town", slug="ruf-other")
        self.other_admin = User.objects.create_user(username="ruf_other_admin", password="a-real-password-123", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        self.backup_payload = {
            "families": [{"name": "Asona", "description": "", "status": "active"}],
            "members": [{"full_name": "Uploaded Member", "gender": "male", "family_name": "Asona"}],
        }

    def _uploaded_file(self, payload):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile("backup.json", json.dumps(payload).encode(), content_type="application/json")

    def test_restoring_from_an_uploaded_file_creates_the_family_and_member(self):
        result = services.restore_community_backup_from_uploaded_file(community=self.bodi, uploaded_file=self._uploaded_file(self.backup_payload), actor=self.bodi_admin)
        self.assertEqual(result["families_restored"], 1)
        self.assertEqual(result["members_created"], 1)
        self.assertTrue(Family.objects.filter(community=self.bodi, name="Asona").exists())
        self.assertTrue(Member.objects.filter(community=self.bodi, full_name="Uploaded Member").exists())

    def test_uploading_the_same_file_twice_never_duplicates(self):
        services.restore_community_backup_from_uploaded_file(community=self.bodi, uploaded_file=self._uploaded_file(self.backup_payload), actor=self.bodi_admin)
        services.restore_community_backup_from_uploaded_file(community=self.bodi, uploaded_file=self._uploaded_file(self.backup_payload), actor=self.bodi_admin)
        self.assertEqual(Member.objects.filter(community=self.bodi, full_name="Uploaded Member").count(), 1)

    def test_a_different_communitys_admin_cannot_restore_from_upload(self):
        with self.assertRaises(ValidationError):
            services.restore_community_backup_from_uploaded_file(community=self.bodi, uploaded_file=self._uploaded_file(self.backup_payload), actor=self.other_admin)

    def test_a_non_json_file_is_reported_clearly(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad_file = SimpleUploadedFile("backup.json", b"not valid json at all", content_type="application/json")
        with self.assertRaises(ValidationError):
            services.restore_community_backup_from_uploaded_file(community=self.bodi, uploaded_file=bad_file, actor=self.bodi_admin)

    def test_a_json_file_that_isnt_the_expected_shape_is_reported_clearly(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        wrong_shape = SimpleUploadedFile("backup.json", json.dumps([1, 2, 3]).encode(), content_type="application/json")
        with self.assertRaises(ValidationError):
            services.restore_community_backup_from_uploaded_file(community=self.bodi, uploaded_file=wrong_shape, actor=self.bodi_admin)

    def test_restore_from_upload_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "ruf_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            "/api/tenants/my-community/backup/restore-from-file/",
            {"file": self._uploaded_file(self.backup_payload)},
            format="multipart",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["members_created"], 1)

    def test_a_different_communitys_admin_restoring_via_my_community_only_ever_affects_their_own_community(self):
        """
        There's no community_id parameter on this 'my-community' endpoint at
        all — it always resolves to the acting user's own community, so a
        different community's admin can never even target self.bodi through
        it. Verifies that guarantee directly: their restore succeeds, but
        lands in THEIR OWN community, never bodi's.
        """
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "ruf_other_admin", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            "/api/tenants/my-community/backup/restore-from-file/",
            {"file": self._uploaded_file(self.backup_payload)},
            format="multipart",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(Member.objects.filter(community=self.other_community, full_name="Uploaded Member").exists())
        self.assertFalse(Member.objects.filter(community=self.bodi, full_name="Uploaded Member").exists())

    def test_the_full_export_then_upload_restore_round_trip_actually_works(self):
        """The realistic end-to-end path: export a real backup, then feed that exact file back in as an upload."""
        asona = family_services.create_family(community=self.bodi, name="Round Trip Family", actor=self.bodi_admin)
        member_services.register_member(community=self.bodi, full_name="Round Trip Member", gender="female", family=asona)

        exported = services.export_community_backup(community=self.bodi, actor=self.bodi_admin)
        from django.core.files.uploadedfile import SimpleUploadedFile
        exported_file = SimpleUploadedFile("backup.json", json.dumps(exported).encode(), content_type="application/json")

        fresh_community = Community.objects.create(name="Fresh Community", slug="ruf-fresh")
        fresh_admin = User.objects.create_user(username="ruf_fresh_admin", password="x", community=fresh_community, role=Role.COMMUNITY_ADMIN)
        result = services.restore_community_backup_from_uploaded_file(community=fresh_community, uploaded_file=exported_file, actor=fresh_admin)
        self.assertEqual(result["members_created"], 1)
        self.assertTrue(Member.objects.filter(community=fresh_community, full_name="Round Trip Member").exists())

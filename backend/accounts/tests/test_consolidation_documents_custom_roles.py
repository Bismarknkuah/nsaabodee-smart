from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
import tempfile

from accounts import services as account_services
from accounts.models import COMMUNITY_ROLE_TYPES, FAMILY_ROLE_TYPES, TOWN_ELDERS_ROLE_TYPES, VISIBLE_ROLES, Role, User, canonical_role
from families import services as family_services
from funerals import services as funeral_services
from funerals.jurisdiction import collector_grants
from members import services as member_services
from members.models import CollectorNomination
from tenants.models import Community

MEDIA_TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class ConsolidationDocumentsCustomRolesTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="cdc-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"))
        self.admin = User.objects.create_user(username="cdc_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

    def _user(self, username, role, family=None):
        user = User.objects.create_user(username=username, password="x", community=self.bodi, role=role)
        if family is not None:
            m = member_services.register_member(community=self.bodi, full_name=username, gender="male", family=family)
            member_services.link_member_to_user(member=m, user=user, actor=self.admin)
        return user

    # ---- consolidation ----
    def test_the_target_counts(self):
        """'Each community 5–6 user role types, the town elders 3, each family 5.'"""
        """Each ledger keeps its registration officer: the community's Town Registration Officer, and one Family Registration Officer per family; the few Town Elders are registered by the Admin and the community registrar."""
        self.assertEqual(COMMUNITY_ROLE_TYPES, ["community_admin", "chairman", "secretary", "financial_secretary", "town_registration_officer", "welfare_manager", "collector", "gift_collector"])
        self.assertEqual(TOWN_ELDERS_ROLE_TYPES, ["traditional_leader", "town_registration_officer", "collector"])
        self.assertEqual(FAMILY_ROLE_TYPES, ["family_head", "family_secretary", "family_treasurer", "family_registration_officer", "collector", "bereaved_rep"])
        self.assertIn("family_registration_officer", VISIBLE_ROLES)
        for legacy in ("arrears_collector", "family_arrears_officer", "town_elders_arrears_officer", "treasurer", "notification_officer", "community_registration_desk"):
            self.assertNotIn(legacy, VISIBLE_ROLES)
        # The Auditor is the one role NOT merged: it is read-only, and the Financial Secretary is not.
        from accounts.models import OPTIONAL_OVERSIGHT_ROLE_TYPES
        self.assertEqual(OPTIONAL_OVERSIGHT_ROLE_TYPES, ["auditor"])
        self.assertIn("auditor", VISIBLE_ROLES)
        self.assertEqual(canonical_role("auditor"), "auditor")
        self.assertEqual(canonical_role("arrears_collector"), "collector")
        self.assertEqual(canonical_role("treasurer"), "financial_secretary")

    def test_a_collector_at_each_level_now_takes_both_contributions_and_arrears_in_their_jurisdiction(self):
        """'The collectors at all levels should play the same role as arrears collector.'"""
        community = self._user("cdc_col", Role.COLLECTOR)
        kinds = {k for k, s in collector_grants(community) if s[0] == "community"}
        self.assertTrue({"contributions", "arrears"} <= kinds)
        fam = self._user("cdc_fam_col", Role.COLLECTOR, self.asona)
        CollectorNomination.objects.create(community=self.bodi, member=fam.member_profile, collector_type="family", scoped_family=self.asona, status=CollectorNomination.Status.APPROVED)
        fam_grants = {(k, s) for k, s in collector_grants(fam)}
        self.assertIn(("arrears", ("family", self.asona.id)), fam_grants)
        self.assertIn(("contributions", ("family", self.asona.id)), fam_grants)
        self.assertNotIn(("arrears", ("community", None)), fam_grants)

    # ---- documents ----
    def test_secretaries_and_financial_secretaries_upload_and_download_at_their_level(self):
        """'All financial secretaries and all secretaries at all levels should be able to upload or download files.'"""
        from documents import services as doc_services
        sec = self._user("cdc_sec", Role.SECRETARY)
        fin = self._user("cdc_fin", Role.FINANCIAL_SECRETARY)
        fam_sec = self._user("cdc_fam_sec", Role.FAMILY_SECRETARY, self.asona)
        bretuo_treasurer = self._user("cdc_b_treasurer", Role.FAMILY_TREASURER, self.bretuo)
        collector = self._user("cdc_col2", Role.COLLECTOR)
        pdf = SimpleUploadedFile("minutes.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        doc = doc_services.upload_document(user=sec, upload=pdf, title="AGM minutes", kind="minutes")
        xlsx = SimpleUploadedFile("asona.xlsx", b"PK\x03\x04 test", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        fam_doc = doc_services.upload_document(user=fam_sec, upload=xlsx, title="Asona ledger", kind="statement")
        self.assertEqual(fam_doc.family_id, self.asona.id)
        self.assertTrue(doc_services.can_download(fin, doc))          # community finance reads community records
        self.assertTrue(doc_services.can_download(fin, fam_doc))      # ...and every family's
        self.assertTrue(doc_services.can_download(fam_sec, fam_doc))
        self.assertFalse(doc_services.can_download(bretuo_treasurer, fam_doc))  # another family's treasurer cannot
        self.assertFalse(doc_services.can_download(collector, doc))   # a collector keeps no documents
        with self.assertRaises(ValidationError):
            doc_services.upload_document(user=collector, upload=SimpleUploadedFile("x.pdf", b"%PDF"), title="nope")
        with self.assertRaises(ValidationError):
            doc_services.upload_document(user=sec, upload=SimpleUploadedFile("virus.exe", b"MZ"), title="nope")

    def test_documents_endpoints(self):
        sec = self._user("cdc_sec2", Role.SECRETARY)
        c = APIClient(); c.force_authenticate(sec)
        res = c.post("/api/documents/", {"file": SimpleUploadedFile("report.pdf", b"%PDF-1.4"), "title": "Report", "kind": "statement"}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        listed = c.get("/api/documents/").data
        self.assertEqual(listed["level"], "community")
        self.assertEqual(len(listed["documents"]), 1)
        dl = c.get(f"/api/documents/{res.data['id']}/")
        self.assertEqual(dl.status_code, 200)
        col = APIClient(); col.force_authenticate(self._user("cdc_col3", Role.COLLECTOR))
        self.assertEqual(col.get("/api/documents/").status_code, 403)
        self.assertEqual(col.get(f"/api/documents/{res.data['id']}/").status_code, 403)

    # ---- custom roles ----
    def test_admin_creates_a_community_role_and_a_family_secretary_creates_a_family_role(self):
        """'The family secretary can create a new role for his family, same as the community admin can create roles for the community.'"""
        fam_sec = self._user("cdc_fam_sec2", Role.FAMILY_SECRETARY, self.asona)
        welfare = account_services.create_custom_role(actor=self.admin, name="Welfare Officer", base_role="secretary")
        youth = account_services.create_custom_role(actor=fam_sec, name="Youth Collector", base_role="collector")
        self.assertIsNone(welfare.family_id)
        self.assertEqual(youth.family_id, self.asona.id)
        # a family secretary cannot create a community role, nor use a community-only base
        with self.assertRaises(ValidationError):
            account_services.create_custom_role(actor=fam_sec, name="Chair", base_role="chairman")
        # a collector cannot create roles at all
        with self.assertRaises(ValidationError):
            account_services.create_custom_role(actor=self._user("cdc_col4", Role.COLLECTOR), name="X", base_role="collector")

    def test_assigning_a_custom_role_grants_its_base_roles_permissions_and_shows_its_name(self):
        welfare = account_services.create_custom_role(actor=self.admin, name="Welfare Officer", base_role="secretary")
        member = member_services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.asona)
        user = member_services.assign_role_to_member(member=member, role="", actor=self.admin, username="cdc_ama", password="a-real-password-123", custom_role=welfare)
        self.assertEqual(user.role, "secretary")
        self.assertEqual(user.custom_role_id, welfare.id)
        self.assertEqual(account_services.role_label_for(user), "Welfare Officer")
        fam_sec = self._user("cdc_fam_sec3", Role.FAMILY_SECRETARY, self.asona)
        youth = account_services.create_custom_role(actor=fam_sec, name="Youth Collector", base_role="collector")
        m2 = member_services.register_member(community=self.bodi, full_name="Kofi", gender="male", family=self.asona)
        u2 = member_services.assign_role_to_member(member=m2, role="", actor=self.admin, username="cdc_kofi", password="a-real-password-123", custom_role=youth)
        self.assertEqual(account_services.role_label_for(u2), "Asona Youth Collector")
        bretuo_member = member_services.register_member(community=self.bodi, full_name="Yaw", gender="male", family=self.bretuo)
        with self.assertRaises(ValidationError):
            member_services.assign_role_to_member(member=bretuo_member, role="", actor=self.admin, username="cdc_yaw", password="a-real-password-123", custom_role=youth)

    def test_custom_role_endpoints(self):
        c = APIClient(); c.force_authenticate(self.admin)
        res = c.post("/api/accounts/custom-roles/", {"name": "Welfare Officer", "base_role": "secretary"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(c.get("/api/accounts/custom-roles/").data["scope"], "community")
        self.assertEqual(c.delete(f"/api/accounts/custom-roles/{res.data['id']}/").status_code, 204)

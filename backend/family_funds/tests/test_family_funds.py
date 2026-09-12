from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from family_funds import services as fund_services
from members import services as member_services
from tenants.models import Community


class FamilyFundIsolationTests(TestCase):
    """'One family head shouldn't get access to other families' activities.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.asona_head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        self.asona_head_user = User.objects.create_user(username="asona_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.asona_head_member, user=self.asona_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.asona_head_member, actor=self.admin)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.bretuo_head_member = member_services.register_member(community=self.bodi, full_name="Bretuo Head", gender="male", family=self.bretuo)
        self.bretuo_head_user = User.objects.create_user(username="bretuo_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.bretuo_head_member, user=self.bretuo_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=self.bretuo_head_member, actor=self.admin)

        self.bretuo_fund = fund_services.create_family_fund(family=self.bretuo, name="Bretuo Building Fund", actor=self.bretuo_head_user)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_asona_head_cannot_see_bretuos_fund(self):
        client = self._login("asona_head")
        res = client.get(f"/api/families/{self.bretuo.id}/funds/")
        self.assertEqual(res.status_code, 403)

    def test_bretuo_head_can_see_own_fund(self):
        client = self._login("bretuo_head")
        res = client.get(f"/api/families/{self.bretuo.id}/funds/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["name"], "Bretuo Building Fund")

    def test_ordinary_treasurer_committee_role_still_cannot_see_a_family_fund(self):
        """The funeral committee has no special access to a family's private fund either."""
        treasurer = User.objects.create_user(username="treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        client = self._login("treasurer")
        res = client.get(f"/api/families/{self.bretuo.id}/funds/")
        self.assertEqual(res.status_code, 403)

    def test_community_admin_retains_oversight(self):
        client = self._login("admin")
        res = client.get(f"/api/families/{self.bretuo.id}/funds/")
        self.assertEqual(res.status_code, 200)


class FamilyOfficerAssignmentTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Treasurer Member", gender="female", family=self.asona)
        self.treasurer_user = User.objects.create_user(username="asona_treasurer", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer_user, actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_family_head_can_assign_a_treasurer_from_his_own_members(self):
        client = self._login("abusuapanin")
        res = client.post(f"/api/families/{self.asona.id}/assign-officer/", {
            "member_id": str(self.treasurer_member.id), "officer_role": "treasurer",
        })
        self.assertEqual(res.status_code, 200)
        self.asona.refresh_from_db()
        self.assertEqual(self.asona.family_treasurer_id, self.treasurer_member.id)

    def test_assigned_treasurer_immediately_gets_fund_access_no_role_change_needed(self):
        family_services.assign_family_officer(family=self.asona, member=self.treasurer_member, officer_role="treasurer", actor=self.head_user)
        # Still an ordinary COMMUNITY_MEMBER by platform role — access comes purely from the Family FK.
        self.treasurer_user.refresh_from_db()
        self.assertEqual(self.treasurer_user.role, Role.COMMUNITY_MEMBER)

        client = self._login("asona_treasurer")
        res = client.get(f"/api/families/{self.asona.id}/funds/")
        self.assertEqual(res.status_code, 200)

    def test_random_member_cannot_assign_officers_for_a_family_they_dont_head(self):
        rando = User.objects.create_user(username="rando", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        client = self._login("rando")
        res = client.post(f"/api/families/{self.asona.id}/assign-officer/", {
            "member_id": str(self.treasurer_member.id), "officer_role": "treasurer",
        })
        self.assertEqual(res.status_code, 403)


class FundContributionWorkflowTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        self.contributor = member_services.register_member(community=self.bodi, full_name="A Contributor", gender="female", family=self.asona)
        self.fund = fund_services.create_family_fund(family=self.asona, name="School Fees Fund", actor=self.head_user)

    def test_member_can_contribute_any_amount(self):
        c1 = fund_services.record_fund_contribution(fund=self.fund, member=self.contributor, amount=Decimal("7.50"))
        c2 = fund_services.record_fund_contribution(fund=self.fund, member=self.contributor, amount=Decimal("500"))
        self.assertIsNotNone(c1.receipt_number)
        self.assertIsNotNone(c2.receipt_number)
        self.assertNotEqual(c1.receipt_number, c2.receipt_number)

    def test_contribution_from_a_different_family_is_rejected(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        outsider = member_services.register_member(community=self.bodi, full_name="Outsider", gender="male", family=bretuo)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            fund_services.record_fund_contribution(fund=self.fund, member=outsider, amount=Decimal("50"))

    def test_fund_summary_totals_are_correct(self):
        fund_services.record_fund_contribution(fund=self.fund, member=self.contributor, amount=Decimal("100"))
        fund_services.record_fund_contribution(fund=self.fund, member=self.contributor, amount=Decimal("50"))
        summary = fund_services.fund_summary(self.fund)
        self.assertEqual(Decimal(summary["total_collected"]), Decimal("150"))
        self.assertEqual(summary["contribution_count"], 2)
        self.assertEqual(summary["contributor_count"], 1)

    def test_full_http_workflow(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "abusuapanin", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post(f"/api/families/{self.asona.id}/funds/{self.fund.id}/contributions/", {
            "member_id": str(self.contributor.id), "amount": "42.50", "payment_method": "mobile_money",
        })
        self.assertEqual(res.status_code, 201)
        self.assertIsNotNone(res.data["receipt_number"])

        summary_res = client.get(f"/api/families/{self.asona.id}/funds/{self.fund.id}/summary/")
        self.assertEqual(Decimal(summary_res.data["total_collected"]), Decimal("42.50"))


class FundContributionReceiptTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        self.contributor = member_services.register_member(community=self.bodi, full_name="A Contributor", gender="female", family=self.asona)
        self.fund = fund_services.create_family_fund(family=self.asona, name="School Fees Fund", actor=self.head_user)
        self.contribution = fund_services.record_fund_contribution(fund=self.fund, member=self.contributor, amount=Decimal("42.50"))

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_receipt_text_mentions_fund_and_amount(self):
        client = self._login("abusuapanin")
        res = client.get(f"/api/families/{self.asona.id}/funds/{self.fund.id}/contributions/{self.contribution.id}/receipt/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("School Fees Fund", res.data["text"])
        self.assertIn("42.50", res.data["text"])
        self.assertIn("community ledger", res.data["text"].lower())

    def test_receipt_pdf_downloads(self):
        client = self._login("abusuapanin")
        res = client.get(f"/api/families/{self.asona.id}/funds/{self.fund.id}/contributions/{self.contribution.id}/receipt/?export=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF-"))

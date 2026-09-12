from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


def _login(username):
    client = APIClient()
    login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
    assert login.status_code == 200, login.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client


class TownElderPerTitleRatesHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tepr-bodi")
        self.chief = User.objects.create_user(username="tepr_chief", password="a-real-password-123", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.admin = User.objects.create_user(username="tepr_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_the_chief_can_set_per_title_rates(self):
        res = _login("tepr_chief").post(
            "/api/contribution-rules/town-elder-per-title-rates/",
            {"chief_amount": "500", "queen_mother_amount": "300"}, format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["default_town_elder_chief_amount"], "500.00")
        self.assertEqual(res.data["default_town_elder_queen_mother_amount"], "300.00")
        self.assertIsNone(res.data["default_town_elder_linguist_amount"])

    def test_a_community_admin_cannot_set_per_title_rates(self):
        res = _login("tepr_admin").post("/api/contribution-rules/town-elder-per-title-rates/", {"chief_amount": "500"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_omitting_a_title_leaves_it_untouched(self):
        client = _login("tepr_chief")
        client.post("/api/contribution-rules/town-elder-per-title-rates/", {"chief_amount": "500"}, format="json")
        res = client.post("/api/contribution-rules/town-elder-per-title-rates/", {"linguist_amount": "200"}, format="json")
        self.assertEqual(res.data["default_town_elder_chief_amount"], "500.00")
        self.assertEqual(res.data["default_town_elder_linguist_amount"], "200.00")


class FamilyPositionRatesHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fprh-bodi")
        self.admin = User.objects.create_user(username="fprh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.member_user = User.objects.create_user(username="fprh_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_setting_and_then_listing_a_position_rate(self):
        client = _login("fprh_admin")
        set_res = client.post("/api/contribution-rules/family-position-rates/", {"position": "uncle", "amount": "150"}, format="json")
        self.assertEqual(set_res.status_code, 200, set_res.data)
        self.assertEqual(set_res.data["uncle"], "150.00")

        list_res = client.get("/api/contribution-rules/family-position-rates/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.data["uncle"], "150.00")

    def test_an_invalid_position_is_rejected(self):
        res = _login("fprh_admin").post("/api/contribution-rules/family-position-rates/", {"position": "not_a_real_position", "amount": "150"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_a_plain_member_cannot_set_a_position_rate(self):
        res = _login("fprh_member").post("/api/contribution-rules/family-position-rates/", {"position": "uncle", "amount": "150"}, format="json")
        self.assertEqual(res.status_code, 403)


class AgeReviewReportHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="arrh-bodi")
        self.admin = User.objects.create_user(username="arrh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        from datetime import date
        self.turning_20 = member_services.register_member(community=self.bodi, full_name="Turning 20", gender="male", family=self.asona)
        self.turning_20.date_of_birth = date(date.today().year - 20, date.today().month, min(date.today().day, 28))
        self.turning_20.save(update_fields=["date_of_birth"])

        self.no_dob = member_services.register_member(community=self.bodi, full_name="No DOB", gender="male", family=self.asona)

    def test_members_needing_age_review_endpoint(self):
        res = _login("arrh_admin").get("/api/contribution-rules/members-needing-age-review/")
        self.assertEqual(res.status_code, 200)
        names = [m["full_name"] for m in res.data]
        self.assertIn("Turning 20", names)
        self.assertNotIn("No DOB", names)

    def test_members_missing_birth_date_endpoint(self):
        res = _login("arrh_admin").get("/api/contribution-rules/members-missing-birth-date/")
        self.assertEqual(res.status_code, 200)
        names = [m["full_name"] for m in res.data]
        self.assertIn("No DOB", names)
        self.assertNotIn("Turning 20", names)

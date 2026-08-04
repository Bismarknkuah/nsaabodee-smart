from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from members import services as member_services
from reports import receipts
from tenants.models import Community


class DonorListAndRelationshipTests(TestCase):
    """
    'The relationship between the gifter and the one he's donating the
    money to' plus 'when printing or generating list of those who paid:
    the name, phone contact, where the gifter resides, the amount the
    gifter paid.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.adwoa = member_services.register_member(community=self.bodi, full_name="Adwoa", gender="female", family=self.asona)
        self.yaw = member_services.register_member(community=self.bodi, full_name="Yaw Owusu", gender="male", family=self.asona)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Donor List Rel Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="donor_list_rel_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.adwoa, actor=self.head_user)
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.yaw, actor=self.head_user)

    def test_relationship_to_recipient_is_recorded(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Friend", amount_cash=Decimal("30"),
            received_by_member=self.adwoa, relationship_to_recipient="Childhood friend",
        )
        self.assertEqual(donation.relationship_to_recipient, "Childhood friend")

    def test_donations_to_adwoa_only_show_up_in_adwoas_own_list(self):
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Donor A", donor_phone="0244000001", donor_hometown="Kumasi",
            amount_cash=Decimal("30"), received_by_member=self.adwoa,
        )
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Donor B", donor_phone="0244000002", donor_hometown="Accra",
            amount_cash=Decimal("50"), received_by_member=self.yaw,
        )

        adwoa_received = gift_services.donations_received_by_member(self.adwoa)
        self.assertEqual(adwoa_received["donation_count"], 1)
        self.assertEqual(adwoa_received["entries"][0]["donor_name"], "Donor A")
        self.assertEqual(adwoa_received["entries"][0]["donor_phone"], "0244000001")
        self.assertEqual(adwoa_received["entries"][0]["donor_hometown"], "Kumasi")

        yaw_received = gift_services.donations_received_by_member(self.yaw)
        self.assertEqual(yaw_received["donation_count"], 1)
        self.assertEqual(yaw_received["entries"][0]["donor_name"], "Donor B")
        # Adwoa's donor never leaks into Yaw's list, and vice versa.
        self.assertNotIn("Donor A", [e["donor_name"] for e in yaw_received["entries"]])
        self.assertNotIn("Donor B", [e["donor_name"] for e in adwoa_received["entries"]])

    def test_entries_include_deceased_name_and_date_of_death(self):
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Donor A", amount_cash=Decimal("30"), received_by_member=self.adwoa,
        )
        received = gift_services.donations_received_by_member(self.adwoa)
        entry = received["entries"][0]
        self.assertEqual(entry["deceased_name"], "Yaw Asona")
        self.assertEqual(entry["date_of_death"], "2026-07-01")

    def test_all_receivers_donation_lists_keeps_receivers_separate(self):
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="Donor A", amount_cash=Decimal("30"), received_by_member=self.adwoa)
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="Donor B", amount_cash=Decimal("50"), received_by_member=self.yaw)

        all_receivers = gift_services.all_receivers_donation_lists(self.funeral)
        by_name = {r["member_name"]: r for r in all_receivers}
        self.assertEqual(by_name["Adwoa"]["donation_count"], 1)
        self.assertEqual(by_name["Yaw Owusu"]["donation_count"], 1)
        self.assertEqual(Decimal(by_name["Adwoa"]["total_received"]), Decimal("30"))
        self.assertEqual(Decimal(by_name["Yaw Owusu"]["total_received"]), Decimal("50"))


class DonorListHttpAndPdfTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin2", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="treasurer2", password="x", community=self.bodi, role=Role.TREASURER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.adwoa_member = member_services.register_member(community=self.bodi, full_name="Adwoa", gender="female", family=self.asona)
        self.adwoa_user = User.objects.create_user(username="adwoa_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.adwoa_member, user=self.adwoa_user, actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Donor List Http Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="donor_list_http_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.adwoa_member, actor=self.head_user)
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Donor A", donor_phone="0244000001", donor_hometown="Kumasi",
            amount_cash=Decimal("30"), received_by_member=self.adwoa_member,
        )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_adwoa_sees_her_own_donations_via_my_donations_received(self):
        client = self._login("adwoa_login")
        res = client.get("/api/my-donations-received/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["donation_count"], 1)
        self.assertEqual(res.data["entries"][0]["donor_name"], "Donor A")

    def test_adwoa_can_download_her_own_donations_as_pdf(self):
        client = self._login("adwoa_login")
        res = client.get("/api/my-donations-received/?export=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        content = res.content
        self.assertTrue(content.startswith(b"%PDF-"))

    def test_treasurer_can_still_record_but_admin_sees_all_receivers_statement(self):
        client = self._login("admin2")
        res = client.get(f"/api/funerals/{self.funeral.id}/donation-accounts/all-receivers-statement/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["member_name"], "Adwoa")
        self.assertEqual(res.data[0]["entries"][0]["donor_name"], "Donor A")

    def test_treasurer_cannot_see_all_receivers_statement(self):
        client = self._login("treasurer2")
        res = client.get(f"/api/funerals/{self.funeral.id}/donation-accounts/all-receivers-statement/")
        self.assertEqual(res.status_code, 403)

    def test_all_receivers_statement_pdf_downloads(self):
        client = self._login("admin2")
        res = client.get(f"/api/funerals/{self.funeral.id}/donation-accounts/all-receivers-statement/?export=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF-"))


class GiftReceiptAppreciationMessageTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin3", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            deceased_date_of_birth="1950-03-15",
        )
        self.adwoa = member_services.register_member(community=self.bodi, full_name="Adwoa", gender="female", family=self.asona)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Donor Lists Asona Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="donor_lists_asona_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.adwoa, actor=self.head_user)

    def test_receipt_data_includes_deceased_date_of_birth(self):
        donation = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Donor", amount_cash=Decimal("20"))
        data = receipts.gift_receipt_data(donation)
        self.assertEqual(data["deceased_date_of_birth"], "1950-03-15")

    def test_appreciation_message_names_the_actual_receiver(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Kwame", amount_cash=Decimal("20"), received_by_member=self.adwoa,
        )
        data = receipts.gift_receipt_data(donation)
        self.assertIn("Kwame", data["appreciation_message"])
        self.assertIn("Adwoa", data["appreciation_message"])
        self.assertIn("Yaw Asona", data["appreciation_message"])

    def test_receipt_text_shows_receiver_and_relationship(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Kwame", amount_cash=Decimal("20"),
            received_by_member=self.adwoa, relationship_to_recipient="Cousin",
        )
        text = receipts.gift_receipt_text(donation, self.bodi.name)
        self.assertIn("Adwoa", text)
        self.assertIn("Cousin", text)
        self.assertIn("Date of birth", text)
        self.assertIn("1950-03-15", text)

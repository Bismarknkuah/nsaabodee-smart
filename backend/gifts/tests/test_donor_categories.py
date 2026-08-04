from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from gifts.models import GiftDonation
from members import services as member_services
from tenants.models import Community


class DonorCategoryTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_donor_with_no_member_record_defaults_to_guest(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Visiting Sympathizer", amount_cash=Decimal("20")
        )
        self.assertEqual(donation.donor_category, GiftDonation.DonorCategory.GUEST)

    def test_donor_who_is_a_registered_member_defaults_to_other(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Kojo Mensah", donor_member=self.member, amount_cash=Decimal("20")
        )
        self.assertEqual(donation.donor_category, GiftDonation.DonorCategory.OTHER)

    def test_category_can_be_explicitly_set_to_town_leader(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Nana the Chief", amount_cash=Decimal("200"),
            donor_category=GiftDonation.DonorCategory.TOWN_LEADER,
        )
        self.assertEqual(donation.donor_category, GiftDonation.DonorCategory.TOWN_LEADER)

    def test_guest_hometown_and_connected_relative_are_recorded(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Ama Boateng", amount_cash=Decimal("30"),
            donor_hometown="Kumasi", connected_relative_name="Kwame Mensah",
        )
        self.assertEqual(donation.donor_hometown, "Kumasi")
        self.assertEqual(donation.connected_relative_name, "Kwame Mensah")

    def test_donations_by_category_breaks_down_correctly(self):
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="Guest A", amount_cash=Decimal("20"))
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="Guest B", amount_cash=Decimal("30"))
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Chief Nana", amount_cash=Decimal("200"),
            donor_category=GiftDonation.DonorCategory.TOWN_LEADER,
        )
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Kojo Mensah", donor_member=self.member, amount_cash=Decimal("15"),
        )

        breakdown = gift_services.donations_by_category(self.funeral)["by_category"]
        self.assertEqual(breakdown["guest"]["donor_count"], 2)
        self.assertEqual(Decimal(breakdown["guest"]["total_value"]), Decimal("50"))
        self.assertEqual(breakdown["town_leader"]["donor_count"], 1)
        self.assertEqual(Decimal(breakdown["town_leader"]["total_value"]), Decimal("200"))
        self.assertEqual(breakdown["other"]["donor_count"], 1)
        self.assertEqual(Decimal(breakdown["other"]["total_value"]), Decimal("15"))

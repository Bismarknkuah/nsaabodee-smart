from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from gifts.models import GiftDonation
from tenants.models import Community


class GuestDelegationTests(TestCase):
    """
    'Town A sends 15 people to the funeral. One representative may
    present a contribution on behalf of Town A... the system should be
    able to record: funeral, guest town, representative, number of
    guests, contribution... without necessarily creating 15 separate
    financial obligations.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="gd-bodi")
        self.admin = User.objects.create_user(username="gd_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_a_delegation_gift_is_recorded_as_a_single_row_with_the_headcount(self):
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Kofi (Town A's representative)", donor_hometown="Town A",
            amount_cash=Decimal("500"), delegation_size=15,
        )
        self.assertEqual(donation.delegation_size, 15)
        # Exactly one row — never fanned out into 15 separate financial obligations.
        self.assertEqual(GiftDonation.objects.filter(funeral_event=self.funeral).count(), 1)

    def test_an_ordinary_individual_gift_has_no_delegation_size(self):
        donation = gift_services.record_gift_donation(funeral=self.funeral, donor_name="Ama", amount_cash=Decimal("50"))
        self.assertIsNone(donation.delegation_size)

    def test_a_delegation_size_of_zero_is_rejected(self):
        with self.assertRaises(ValidationError):
            gift_services.record_gift_donation(funeral=self.funeral, donor_name="Kofi", amount_cash=Decimal("500"), delegation_size=0)

    def test_a_negative_delegation_size_is_rejected(self):
        with self.assertRaises(ValidationError):
            gift_services.record_gift_donation(funeral=self.funeral, donor_name="Kofi", amount_cash=Decimal("500"), delegation_size=-3)

    def test_full_http_recording_of_a_delegation_gift(self):
        User.objects.create_user(username="gd_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "gd_collector", "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = client.post(
            f"/api/funerals/{self.funeral.id}/gifts/",
            {
                "donor_name": "Kofi (Town A's representative)", "donor_hometown": "Town A",
                "amount_cash": "500", "delegation_size": 15, "collector_name": "Collector",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["delegation_size"], 15)

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from gifts import services
from gifts.models import GiftDonation
from members import services as member_services
from tenants.models import Community


class GiftDonationTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.donor_member = member_services.register_member(
            community=self.bodi, full_name="Kwabena Donor", gender="male", family=self.asona
        )
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )

    def test_record_cash_only_gift(self):
        donation = services.record_gift_donation(
            funeral=self.funeral, donor_name="Ama Boateng", amount_cash=Decimal("100"),
            payment_method="mobile_money", collected_by=self.admin,
        )
        self.assertEqual(donation.recipient_family_id, self.asona.id)
        self.assertEqual(donation.total_value, Decimal("100"))
        self.assertTrue(donation.receipt_number.startswith("BODI-GIFT-"))

    def test_record_item_only_gift_requires_estimated_value(self):
        with self.assertRaises(ValidationError):
            services.record_gift_donation(funeral=self.funeral, donor_name="Kojo", gift_item="A cow")

        donation = services.record_gift_donation(
            funeral=self.funeral, donor_name="Kojo", gift_item="A cow", estimated_item_value=Decimal("800"),
        )
        self.assertEqual(donation.total_value, Decimal("800"))

    def test_donation_needs_cash_or_item(self):
        with self.assertRaises(ValidationError):
            services.record_gift_donation(funeral=self.funeral, donor_name="Nobody Gave Anything")

    def test_mixed_cash_and_item_donation(self):
        donation = services.record_gift_donation(
            funeral=self.funeral, donor_name="Efua", amount_cash=Decimal("50"),
            gift_item="2 bags of rice", estimated_item_value=Decimal("120"),
        )
        self.assertEqual(donation.total_value, Decimal("170"))

    def test_donor_can_optionally_be_a_known_member(self):
        donation = services.record_gift_donation(
            funeral=self.funeral, donor_name=self.donor_member.full_name, donor_member=self.donor_member,
            amount_cash=Decimal("20"),
        )
        self.assertEqual(donation.donor_member_id, self.donor_member.id)

    def test_duplicate_offline_gift_is_idempotent_on_client_op_id(self):
        op_id = "22222222-2222-2222-2222-222222222222"
        d1 = services.record_gift_donation(funeral=self.funeral, donor_name="Ama", amount_cash=Decimal("30"), client_op_id=op_id)
        d2 = services.record_gift_donation(funeral=self.funeral, donor_name="Ama", amount_cash=Decimal("30"), client_op_id=op_id)
        self.assertEqual(d1.id, d2.id)
        self.assertEqual(GiftDonation.objects.filter(funeral_event=self.funeral).count(), 1)

    def test_gift_summary_totals(self):
        services.record_gift_donation(funeral=self.funeral, donor_name="A", amount_cash=Decimal("100"))
        services.record_gift_donation(funeral=self.funeral, donor_name="B", gift_item="Goat", estimated_item_value=Decimal("300"))
        summary = services.gift_summary(self.funeral)
        self.assertEqual(summary["donation_count"], 2)
        self.assertEqual(Decimal(summary["total_cash"]), Decimal("100"))
        self.assertEqual(Decimal(summary["total_estimated_item_value"]), Decimal("300"))
        self.assertEqual(Decimal(summary["total_combined_value"]), Decimal("400"))

    def test_gifts_never_touch_the_mandatory_contribution_ledger(self):
        """
        The core requirement: recording gift donations must have zero
        effect on Ledger 1. This checks obligations before and after
        several gift donations and confirms nothing changed at all.
        """
        obligations_before = list(
            ContributionObligation.objects.filter(funeral_event=self.funeral)
            .values_list("id", "expected_amount", "amount_paid")
        )

        services.record_gift_donation(funeral=self.funeral, donor_name="Big Donor", amount_cash=Decimal("5000"))
        services.record_gift_donation(funeral=self.funeral, donor_name="Another Donor", gift_item="A car", estimated_item_value=Decimal("50000"))

        obligations_after = list(
            ContributionObligation.objects.filter(funeral_event=self.funeral)
            .values_list("id", "expected_amount", "amount_paid")
        )
        self.assertEqual(obligations_before, obligations_after)
        # And no obligation was ever created FOR a donor who isn't otherwise a member.
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=self.funeral).count(), len(obligations_before))

    def test_donor_member_from_another_community_rejected(self):
        other = Community.objects.create(name="Other", slug="other")
        outsider = member_services.register_member(community=other, full_name="Stranger", gender="male")
        with self.assertRaises(ValidationError):
            services.record_gift_donation(funeral=self.funeral, donor_name="Stranger", donor_member=outsider, amount_cash=Decimal("10"))

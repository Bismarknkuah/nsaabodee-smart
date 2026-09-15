from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from tenants.models import Community


class TownElderPerTitleRateTests(TestCase):
    """
    'Do not assume that every town elder has the same contribution
    amount... the expected contribution may differ according to the
    elder's official position.' (funeral-contribution-rules §10-11)
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="teptr-bodi",
            default_town_leader_amount=Decimal("100"),
            default_town_elder_chief_amount=Decimal("500"),
            default_town_elder_queen_mother_amount=Decimal("300"),
            default_town_elder_linguist_amount=Decimal("200"),
            # default_town_elder_other_amount left unset deliberately —
            # must fall back to the flat default_town_leader_amount.
        )
        self.admin = User.objects.create_user(username="teptr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.chief = member_services.register_member(community=self.bodi, full_name="The Chief", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.chief, title="chief", actor=self.admin)
        self.queen_mother = member_services.register_member(community=self.bodi, full_name="The Queen Mother", gender="female", family=self.asona)
        member_services.transfer_to_town_elder(member=self.queen_mother, title="queen_mother", actor=self.admin)
        self.linguist = member_services.register_member(community=self.bodi, full_name="The Linguist", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.linguist, title="linguist", actor=self.admin)
        self.other_elder = member_services.register_member(community=self.bodi, full_name="Other Elder", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.other_elder, title="other", actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _expected_amount(self, member):
        return ContributionObligation.objects.get(funeral_event=self.funeral, member=member).expected_amount

    def test_the_chief_pays_the_chief_specific_rate(self):
        self.assertEqual(self._expected_amount(self.chief), Decimal("500"))

    def test_the_queen_mother_pays_a_different_rate_from_the_chief(self):
        self.assertEqual(self._expected_amount(self.queen_mother), Decimal("300"))

    def test_the_linguist_pays_yet_another_distinct_rate(self):
        self.assertEqual(self._expected_amount(self.linguist), Decimal("200"))

    def test_an_other_title_elder_falls_back_to_the_flat_default_when_no_specific_rate_is_configured(self):
        self.assertEqual(self._expected_amount(self.other_elder), Decimal("100"))

    def test_every_title_genuinely_pays_a_different_amount_not_one_universal_figure(self):
        amounts = {self._expected_amount(m) for m in (self.chief, self.queen_mother, self.linguist, self.other_elder)}
        self.assertEqual(len(amounts), 4)

    def test_rate_type_is_still_town_elder_for_every_title_not_general_or_own_family(self):
        for m in (self.chief, self.queen_mother, self.linguist, self.other_elder):
            obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=m)
            self.assertEqual(obligation.rate_type, "town_elder")


class TownElderIndividualOverrideTests(TestCase):
    """'Town elder contribution can also be individual... Elder A -> GHS X, Elder B -> GHS Y.' (funeral-contribution-rules §11)"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="teio-bodi",
            default_town_leader_amount=Decimal("100"),
            default_town_elder_chief_amount=Decimal("500"),
        )
        self.admin = User.objects.create_user(username="teio_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.chief_a = member_services.register_member(community=self.bodi, full_name="Chief A", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.chief_a, title="chief", actor=self.admin)
        self.chief_a.town_elder_individual_rate = Decimal("750")
        self.chief_a.save(update_fields=["town_elder_individual_rate"])

        self.chief_b = member_services.register_member(community=self.bodi, full_name="Chief B (no override)", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.chief_b, title="chief", actor=self.admin)

    def test_an_individual_override_takes_priority_over_the_per_title_rate(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        overridden = ContributionObligation.objects.get(funeral_event=funeral, member=self.chief_a)
        self.assertEqual(overridden.expected_amount, Decimal("750"))

    def test_two_elders_with_the_same_title_can_genuinely_pay_different_amounts(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        amount_a = ContributionObligation.objects.get(funeral_event=funeral, member=self.chief_a).expected_amount
        amount_b = ContributionObligation.objects.get(funeral_event=funeral, member=self.chief_b).expected_amount
        self.assertEqual(amount_a, Decimal("750"))
        self.assertEqual(amount_b, Decimal("500"))
        self.assertNotEqual(amount_a, amount_b)

    def test_the_override_is_standing_and_applies_across_multiple_funerals(self):
        """A community-wide figure for this person, not scoped to one funeral."""
        funeral_1 = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="First Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        funeral_2 = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Second Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-08-01", collection_start_date="2026-08-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        for f in (funeral_1, funeral_2):
            self.assertEqual(ContributionObligation.objects.get(funeral_event=f, member=self.chief_a).expected_amount, Decimal("750"))


class TownElderPerFuneralSnapshotTests(TestCase):
    """Confirms per-title rates snapshot onto the funeral at creation, matching the existing pattern for every other rate field."""

    def test_changing_the_community_default_after_a_funeral_is_created_never_rewrites_that_funerals_own_snapshot(self):
        bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="tepfs-bodi",
            default_town_elder_chief_amount=Decimal("500"),
        )
        admin = User.objects.create_user(username="tepfs_admin", password="x", community=bodi, role=Role.COMMUNITY_ADMIN)
        asona = family_services.create_family(community=bodi, name="Asona", actor=admin)
        chief = member_services.register_member(community=bodi, full_name="The Chief", gender="male", family=asona)
        member_services.transfer_to_town_elder(member=chief, title="chief", actor=admin)

        funeral = funeral_services.create_funeral_event(
            community=bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=admin, own_family_amount=Decimal("50"),
        )

        bodi.default_town_elder_chief_amount = Decimal("900")
        bodi.save(update_fields=["default_town_elder_chief_amount"])

        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=chief)
        self.assertEqual(obligation.expected_amount, Decimal("500"))

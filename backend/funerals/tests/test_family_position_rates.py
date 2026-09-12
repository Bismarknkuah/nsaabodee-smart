from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from contribution_rules import services as contribution_rules_services
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from members.models import Member
from tenants.models import Community


class FamilyPositionRateTests(TestCase):
    """
    'Family contributions are not uniform... do not implement the
    Family Ledger as every family member pays GHS X. The system must
    allow contribution differences based on family position and
    configured family rules.' (funeral-contribution-rules, family
    position taxonomy)
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fpr-bodi")
        self.admin = User.objects.create_user(username="fpr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        contribution_rules_services.set_family_position_rate(community=self.bodi, position="uncle", amount=Decimal("150"), actor=self.admin)
        contribution_rules_services.set_family_position_rate(community=self.bodi, position="nephew", amount=Decimal("60"), actor=self.admin)
        # Deliberately never configuring a rate for "cousin"-equivalent
        # positions like OTHER — must fall back to the coarser tier.

        self.uncle = member_services.register_member(community=self.bodi, full_name="The Uncle", gender="male", family=self.asona)
        self.uncle.family_position = Member.FamilyPosition.UNCLE
        self.uncle.save(update_fields=["family_position"])

        self.nephew = member_services.register_member(community=self.bodi, full_name="The Nephew", gender="male", family=self.asona)
        self.nephew.family_position = Member.FamilyPosition.NEPHEW
        self.nephew.save(update_fields=["family_position"])

        self.other_member = member_services.register_member(community=self.bodi, full_name="Other Position Member", gender="male", family=self.asona)
        self.other_member.family_position = Member.FamilyPosition.OTHER
        self.other_member.save(update_fields=["family_position"])

        self.no_position_member = member_services.register_member(community=self.bodi, full_name="No Position Set", gender="male", family=self.asona)
        # family_position deliberately left unset — must behave exactly as before this feature existed.

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _expected_amount(self, member):
        return ContributionObligation.objects.get(funeral_event=self.funeral, member=member).expected_amount

    def test_a_member_with_a_configured_position_pays_that_positions_own_rate(self):
        self.assertEqual(self._expected_amount(self.uncle), Decimal("150"))

    def test_a_different_position_genuinely_pays_a_different_amount(self):
        self.assertEqual(self._expected_amount(self.nephew), Decimal("60"))
        self.assertNotEqual(self._expected_amount(self.uncle), self._expected_amount(self.nephew))

    def test_a_position_with_no_configured_rate_falls_back_to_the_coarser_gender_seniority_tier(self):
        """OTHER has no rate configured — must fall back to the original family_seniority-based logic, never error."""
        self.other_member.family_seniority = Member.FamilySeniority.JUNIOR
        self.other_member.save(update_fields=["family_seniority"])
        self.assertEqual(self._expected_amount(self.other_member), Decimal("50"))  # community's default_family_junior_amount fallback path

    def test_a_member_with_no_family_position_set_at_all_behaves_exactly_as_before(self):
        """The core backward-compatibility guarantee — every existing member without this field set is completely unaffected."""
        self.assertIsNone(self.no_position_member.family_position)
        self.assertEqual(self._expected_amount(self.no_position_member), Decimal("50"))

    def test_rate_type_is_still_own_family_regardless_of_which_position_tier_applies(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.uncle)
        self.assertEqual(obligation.rate_type, "own_family")

    def test_the_family_head_is_never_driven_by_family_position_even_if_one_is_set(self):
        """Family.family_head alone decides the Head's rate — family_position is documented as never read for the Head."""
        head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        head_member.family_position = Member.FamilyPosition.FAMILY_HEAD
        head_member.save(update_fields=["family_position"])
        family_services.assign_family_head(family=self.asona, member=head_member, actor=self.admin)

        new_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Second Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-08-01", collection_start_date="2026-08-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        head_obligation = ContributionObligation.objects.get(funeral_event=new_funeral, member=head_member)
        # Even though FAMILY_HEAD is a real, no-rate-configured position, the Head's own community-configured head rate applies.
        self.assertEqual(head_obligation.expected_amount, self.bodi.default_family_head_amount)

    def test_setting_a_zero_or_negative_position_rate_is_rejected(self):
        with self.assertRaises(ValidationError):
            contribution_rules_services.set_family_position_rate(community=self.bodi, position="aunt", amount=Decimal("0"), actor=self.admin)

    def test_re_setting_a_position_rate_updates_it_rather_than_creating_a_duplicate(self):
        from contribution_rules.models import FamilyPositionRate
        contribution_rules_services.set_family_position_rate(community=self.bodi, position="uncle", amount=Decimal("200"), actor=self.admin)
        self.assertEqual(FamilyPositionRate.objects.filter(community=self.bodi, position="uncle").count(), 1)
        self.assertEqual(contribution_rules_services.family_position_rate_for(self.bodi, "uncle"), Decimal("200"))

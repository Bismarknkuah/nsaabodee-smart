from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from families.models import Family
from funerals import services
from funerals.models import ContributionObligation, ContributionPayment, FuneralEvent
from members.models import Member
from tenants.models import Community


class FuneralLedgerTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(
            username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN
        )
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        # Give Asona an approved own-family rate of GH₵50, as in the master brief.
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        # Members: 2 in Asona (the deceased's family), 2 in Bretuo (outside family).
        self.asona_male = Member.objects.create(community=self.bodi, family=self.asona, full_name="Kojo", gender="male")
        self.asona_female = Member.objects.create(community=self.bodi, family=self.asona, full_name="Adjoa", gender="female")
        self.other_male = Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Kwame", gender="male")
        self.other_female = Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Akosua", gender="female")

    def _obligation_for(self, funeral, member):
        return ContributionObligation.objects.get(funeral_event=funeral, member=member)

    def test_funeral_requires_approved_family_rate_unless_overridden(self):
        with self.assertRaises(ValidationError):
            services.create_funeral_event(
                community=self.bodi, deceased_name="Yaw", deceased_gender="male",
                deceased_family=self.bretuo,  # Bretuo has no approved rate yet
                date_of_death="2026-07-01", collection_start_date="2026-07-01",
            )
        # Providing an explicit one-off amount is allowed even with no standing rate.
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw", deceased_gender="male",
            deceased_family=self.bretuo, own_family_amount=Decimal("40"),
            date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.assertEqual(funeral.own_family_amount, Decimal("40"))

    def test_every_active_member_is_automatically_obligated(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )
        # Nobody signs up — all 4 pre-existing active members are already on the ledger.
        self.assertEqual(ContributionObligation.objects.filter(funeral_event=funeral).count(), 4)

    def test_own_family_members_pay_family_rate_others_pay_general_rate_by_gender(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )
        # Neither asona_male nor asona_female is the family head, so they
        # get the tiered rates: an ordinary male defaults to the junior
        # ("nephew") tier, and a woman always gets the family's woman
        # rate — these are the community's own default tiers (50/40),
        # not the GH₵50 standing_family_rate set above, which no longer
        # directly drives individual obligations (see FuneralEvent.rate_for).
        self.assertEqual(self._obligation_for(funeral, self.asona_male).expected_amount, Decimal("50"))  # junior tier default
        self.assertEqual(self._obligation_for(funeral, self.asona_female).expected_amount, Decimal("40"))  # woman tier
        self.assertEqual(self._obligation_for(funeral, self.other_male).expected_amount, Decimal("5"))
        self.assertEqual(self._obligation_for(funeral, self.other_female).expected_amount, Decimal("3"))

        self.assertEqual(self._obligation_for(funeral, self.asona_male).rate_type, "own_family")
        self.assertEqual(self._obligation_for(funeral, self.other_male).rate_type, "general")

    def test_new_member_is_auto_enrolled_into_currently_open_funerals(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )
        newcomer = Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Abena", gender="female")
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=newcomer)
        self.assertEqual(obligation.expected_amount, Decimal("3"))  # general female rate

    def test_four_concurrent_funerals_keep_independent_ledgers(self):
        family_services.recommend_family_rate(family=self.bretuo, amount=Decimal("30"), actor=self.admin)
        family_services.approve_family_rate(family=self.bretuo, actor=self.admin)

        f1 = services.create_funeral_event(
            community=self.bodi, deceased_name="A", deceased_gender="male", deceased_family=self.asona,
            date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        f2 = services.create_funeral_event(
            community=self.bodi, deceased_name="B", deceased_gender="female", deceased_family=self.bretuo,
            date_of_death="2026-07-02", collection_start_date="2026-07-02",
        )
        f3 = services.create_funeral_event(
            community=self.bodi, deceased_name="C", deceased_gender="male", deceased_family=self.asona,
            date_of_death="2026-07-03", collection_start_date="2026-07-03",
        )
        f4 = services.create_funeral_event(
            community=self.bodi, deceased_name="D", deceased_gender="female", deceased_family=self.bretuo,
            date_of_death="2026-07-04", collection_start_date="2026-07-04",
        )
        self.assertEqual(FuneralEvent.objects.filter(community=self.bodi, status="active").count(), 4)

        # asona_male is "own family" for f1/f3, "general" for f2/f4 — each ledger independent.
        self.assertEqual(self._obligation_for(f1, self.asona_male).rate_type, "own_family")
        self.assertEqual(self._obligation_for(f2, self.asona_male).rate_type, "general")
        self.assertEqual(self._obligation_for(f3, self.asona_male).rate_type, "own_family")
        self.assertEqual(self._obligation_for(f4, self.asona_male).rate_type, "general")

    def test_record_payment_updates_running_total_and_status(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        obligation = self._obligation_for(funeral, self.asona_male)
        self.assertEqual(obligation.payment_status, "unpaid")

        services.record_payment(obligation=obligation, amount=Decimal("20"), method="cash", collector=self.admin)
        obligation.refresh_from_db()
        self.assertEqual(obligation.payment_status, "partial")
        self.assertEqual(obligation.balance, Decimal("30"))

        services.record_payment(obligation=obligation, amount=Decimal("30"), method="mobile_money", collector=self.admin)
        obligation.refresh_from_db()
        self.assertEqual(obligation.payment_status, "paid")
        self.assertEqual(ContributionPayment.objects.filter(obligation=obligation).count(), 2)

    def test_paying_more_than_the_required_amount_is_accepted_not_blocked(self):
        """
        The general/family rate is a required MINIMUM, not a ceiling —
        someone can choose to give more, and the system accepts it. What
        it tracks separately is how much was over the requirement.
        """
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        obligation = self._obligation_for(funeral, self.other_male)  # owes 5
        services.record_payment(obligation=obligation, amount=Decimal("100"), method="cash")
        obligation.refresh_from_db()

        self.assertEqual(obligation.amount_paid, Decimal("100"))
        self.assertEqual(obligation.payment_status, "paid")
        self.assertEqual(obligation.balance, Decimal("0"))  # never negative
        self.assertEqual(obligation.overpaid_amount, Decimal("95"))  # 100 - 5 required

    def test_duplicate_offline_payment_is_idempotent_on_client_op_id(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        obligation = self._obligation_for(funeral, self.asona_male)
        op_id = "11111111-1111-1111-1111-111111111111"

        p1 = services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", client_op_id=op_id)
        p2 = services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", client_op_id=op_id)

        self.assertEqual(p1.id, p2.id)
        obligation.refresh_from_db()
        self.assertEqual(obligation.amount_paid, Decimal("50"))  # not double-counted

    def test_member_transferred_into_deceased_family_switches_to_family_rate_mid_collection(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.assertEqual(self._obligation_for(funeral, self.other_male).rate_type, "general")

        family_services.transfer_members(member_ids=[self.other_male.id], target_family=self.asona, actor=self.admin)

        obligation = self._obligation_for(funeral, self.other_male)
        self.assertEqual(obligation.rate_type, "own_family")
        self.assertEqual(obligation.expected_amount, Decimal("50"))

    def test_summary_breaks_down_own_family_vs_general(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        services.record_payment(
            obligation=self._obligation_for(funeral, self.asona_male), amount=Decimal("50"), method="cash"
        )
        summary = services.funeral_summary(funeral)
        self.assertEqual(summary["own_family"]["member_count"], 2)
        # asona_male (junior tier, 50) + asona_female (woman tier, 40) = 90 — see rate_for()'s tiering, not one flat rate.
        self.assertEqual(summary["own_family"]["expected_total"], Decimal("90"))
        self.assertEqual(summary["own_family"]["collected_total"], Decimal("50"))
        self.assertEqual(summary["general"]["member_count"], 2)
        self.assertEqual(summary["general"]["expected_total"], Decimal("8"))


class OverpaymentTests(TestCase):
    """
    The community/general rate (and the own-family rate) is a required
    MINIMUM, not a ceiling — someone can choose to give more than what's
    required, and the system must accept it rather than rejecting the
    payment as "exceeding the balance."
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
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.outsider = Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Kwame", gender="male")
        self.funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_paying_more_than_the_general_rate_is_accepted_not_rejected(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.outsider)
        self.assertEqual(obligation.expected_amount, Decimal("5"))  # general male rate

        services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        obligation.refresh_from_db()

        self.assertEqual(obligation.amount_paid, Decimal("50"))
        self.assertEqual(obligation.payment_status, "paid")
        self.assertEqual(obligation.balance, Decimal("0"))  # floored at zero, never negative
        self.assertEqual(obligation.overpaid_amount, Decimal("45"))

    def test_further_generous_payment_still_accepted_after_already_fully_paid(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.outsider)
        services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash")
        obligation.refresh_from_db()
        self.assertEqual(obligation.payment_status, "paid")

        services.record_payment(obligation=obligation, amount=Decimal("20"), method="cash")
        obligation.refresh_from_db()
        self.assertEqual(obligation.amount_paid, Decimal("25"))
        self.assertEqual(obligation.overpaid_amount, Decimal("20"))

    def test_partial_underpayment_is_still_supported_unchanged(self):
        """Overpayment being allowed must not break the existing, intentional partial-payment support."""
        from funerals.models import ContributionObligation as CO
        obligation = CO.objects.get(funeral_event=self.funeral, member=self.outsider)
        services.record_payment(obligation=obligation, amount=Decimal("2"), method="cash")
        obligation.refresh_from_db()
        self.assertEqual(obligation.payment_status, "partial")
        self.assertEqual(obligation.balance, Decimal("3"))


class TieredFamilyRateTests(TestCase):
    """
    'Family heads pay 200, uncle pays 100, nephew pays 50, women pay
    40... town leaders pay about 100 cedis each.' The concrete pricing
    model, resolved via FuneralEvent.rate_for()'s priority order.
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
            default_family_head_amount=Decimal("200"), default_family_senior_amount=Decimal("100"),
            default_family_junior_amount=Decimal("50"), default_family_woman_amount=Decimal("40"),
            default_town_leader_amount=Decimal("100"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("999"), actor=self.admin)  # deliberately irrelevant now
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.head_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Head", gender="male")
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.uncle_member = Member.objects.create(
            community=self.bodi, family=self.asona, full_name="The Uncle", gender="male",
            family_seniority=Member.FamilySeniority.SENIOR,
        )
        self.nephew_member = Member.objects.create(
            community=self.bodi, family=self.asona, full_name="The Nephew", gender="male",
            family_seniority=Member.FamilySeniority.JUNIOR,
        )
        self.woman_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="A Woman", gender="female")

        self.other_family = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.town_leader = Member.objects.create(
            community=self.bodi, family=self.other_family, full_name="The Chief", gender="male", is_town_leader=True,
        )
        self.ordinary_outsider = Member.objects.create(community=self.bodi, family=self.other_family, full_name="Ordinary Person", gender="male")

    def _obligation_for(self, funeral, member):
        return ContributionObligation.objects.get(funeral_event=funeral, member=member)

    def test_the_full_tiered_pricing_model(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )
        self.assertEqual(self._obligation_for(funeral, self.head_member).expected_amount, Decimal("200"))
        self.assertEqual(self._obligation_for(funeral, self.uncle_member).expected_amount, Decimal("100"))
        self.assertEqual(self._obligation_for(funeral, self.nephew_member).expected_amount, Decimal("50"))
        self.assertEqual(self._obligation_for(funeral, self.woman_member).expected_amount, Decimal("40"))
        self.assertEqual(self._obligation_for(funeral, self.town_leader).expected_amount, Decimal("100"))
        self.assertEqual(self._obligation_for(funeral, self.ordinary_outsider).expected_amount, Decimal("5"))

        self.assertEqual(self._obligation_for(funeral, self.head_member).rate_type, "own_family")
        self.assertEqual(self._obligation_for(funeral, self.town_leader).rate_type, "general")

    def test_town_leader_status_overrides_being_in_the_deceased_family_too(self):
        """A town leader who happens to BE in the deceased's own family still pays the flat town-leader rate, not a family tier."""
        town_leader_in_family = Member.objects.create(
            community=self.bodi, family=self.asona, full_name="Elder In Family", gender="male", is_town_leader=True,
        )
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )
        obligation = self._obligation_for(funeral, town_leader_in_family)
        self.assertEqual(obligation.expected_amount, Decimal("100"))

    def test_rates_are_snapshotted_so_a_later_community_default_change_never_rewrites_this_funeral(self):
        funeral = services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin,
        )
        self.bodi.default_family_head_amount = Decimal("500")
        self.bodi.save()
        funeral.refresh_from_db()
        self.assertEqual(funeral.family_head_amount, Decimal("200"))  # unchanged, snapshotted at creation

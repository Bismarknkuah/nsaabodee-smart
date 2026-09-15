from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from members.models import Member
from reports.services import funeral_daily_breakdown
from tenants.models import Community


class DailyCombinedLedgerTests(TestCase):
    """'After each day of every funeral the system should be able to calculate all money received from the town elders ledger, the community ledger and sum them together.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="dcl-bodi",
            default_general_male_amount=Decimal("5"), default_town_leader_amount=Decimal("100"),
        )
        self.admin = User.objects.create_user(username="dcl_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.outsider = member_services.register_member(community=self.bodi, full_name="Outsider Member", gender="male", family=self.bretuo)
        self.elder = member_services.register_member(community=self.bodi, full_name="Town Elder", gender="male", family=self.bretuo)
        member_services.transfer_to_town_elder(member=self.elder, title="chief", actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-03", collection_start_date="2026-07-03",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_a_days_totals_break_out_town_elder_and_community_ledger_separately_and_combined(self):
        from datetime import date
        general_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.outsider)
        elder_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.elder)
        funeral_services.record_payment(obligation=general_obligation, amount=Decimal("5"), method="cash", collector_name="Collector")
        funeral_services.record_payment(obligation=elder_obligation, amount=Decimal("100"), method="cash", collector_name="Collector")

        breakdown = funeral_daily_breakdown(self.funeral)
        today_entry = next(d for d in breakdown["days"] if d["date"] == date.today().isoformat())
        self.assertEqual(today_entry["community_ledger_total"], "5")
        self.assertEqual(today_entry["town_elders_ledger_total"], "100")
        self.assertEqual(today_entry["town_elders_and_community_combined_total"], "105")

    def test_the_combined_total_never_includes_own_family_money(self):
        """The family's own ledger is a separate thing entirely — must not leak into this specific combined figure."""
        from datetime import date
        family_member = member_services.register_member(community=self.bodi, full_name="Asona's Own Member", gender="male", family=self.asona)
        family_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=family_member)
        funeral_services.record_payment(obligation=family_obligation, amount=Decimal("50"), method="cash", collector_name="Collector")

        breakdown = funeral_daily_breakdown(self.funeral)
        today_entry = next(d for d in breakdown["days"] if d["date"] == date.today().isoformat())
        self.assertEqual(today_entry["town_elders_and_community_combined_total"], "0")

    def test_the_grand_total_sums_the_combined_figure_across_every_day(self):
        general_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.outsider)
        funeral_services.record_payment(obligation=general_obligation, amount=Decimal("5"), method="cash", collector_name="Collector")
        breakdown = funeral_daily_breakdown(self.funeral)
        self.assertEqual(breakdown["town_elders_and_community_grand_total"], "5")


class NoDoublePaymentTests(TestCase):
    """'One person is not allowed to pay twice of each funeral, but can decide to pay more than the required amount.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ndp-bodi", default_general_male_amount=Decimal("5"))
        self.admin = User.objects.create_user(username="ndp_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.bretuo)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _obligation(self):
        return ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)

    def test_paying_exactly_the_required_amount_then_paying_again_is_rejected(self):
        obligation = self._obligation()
        funeral_services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash", collector_name="Collector")
        with self.assertRaises(ValidationError):
            funeral_services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash", collector_name="Collector")

    def test_overpaying_in_a_single_payment_then_trying_to_pay_again_is_rejected(self):
        obligation = self._obligation()
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector_name="Collector")
        with self.assertRaises(ValidationError):
            funeral_services.record_payment(obligation=obligation, amount=Decimal("1"), method="cash", collector_name="Collector")

    def test_a_genuine_idempotent_retry_of_the_same_payment_still_succeeds(self):
        """The double-payment guard must never break a legitimate offline-sync retry of the SAME payment."""
        import uuid
        obligation = self._obligation()
        retry_op_id = uuid.uuid4()
        payment1 = funeral_services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash", collector_name="Collector", client_op_id=retry_op_id)
        payment2 = funeral_services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash", collector_name="Collector", client_op_id=retry_op_id)
        self.assertEqual(payment1.id, payment2.id)


class TownElderUniformRateTests(TestCase):
    """'For the town elders, every family pay the same.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="teu-bodi", default_town_leader_amount=Decimal("100"))
        self.admin = User.objects.create_user(username="teu_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.elder_in_asona = member_services.register_member(community=self.bodi, full_name="Elder In Asona", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.elder_in_asona, title="chief", actor=self.admin)
        self.elder_in_bretuo = member_services.register_member(community=self.bodi, full_name="Elder In Bretuo", gender="male", family=self.bretuo)
        member_services.transfer_to_town_elder(member=self.elder_in_bretuo, title="queen_mother", actor=self.admin)

    def test_elders_from_different_families_pay_the_exact_same_rate(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        asona_elder_obligation = ContributionObligation.objects.get(funeral_event=funeral, member=self.elder_in_asona)
        bretuo_elder_obligation = ContributionObligation.objects.get(funeral_event=funeral, member=self.elder_in_bretuo)
        self.assertEqual(asona_elder_obligation.expected_amount, bretuo_elder_obligation.expected_amount)
        self.assertEqual(asona_elder_obligation.expected_amount, Decimal("100"))


class PerFuneralTownElderRateOverrideTests(TestCase):
    """'When a king or queen or anyone from the town elders dies, the community price can be set again.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="pfr-bodi", default_town_leader_amount=Decimal("100"))
        self.admin = User.objects.create_user(username="pfr_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_an_explicit_town_leader_amount_overrides_the_community_default_for_this_funeral_only(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="The Chief Himself", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"), town_leader_amount=Decimal("500"),
        )
        self.assertEqual(funeral.town_leader_amount, Decimal("500"))
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.default_town_leader_amount, Decimal("100"))  # the community default is untouched

    def test_omitting_the_override_still_falls_back_to_the_community_default(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="An Ordinary Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.assertEqual(funeral.town_leader_amount, Decimal("100"))


class MultiFamilyMultiFuneralPayingTests(TestCase):
    """'In one funeral day they can have two or more funerals at the same time... if the two deceased is from different families, after paying your family contribution you have to go and pay the community contribution for the other family.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="mfmf-bodi",
            default_general_male_amount=Decimal("5"),
        )
        self.admin = User.objects.create_user(username="mfmf_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Asona's Own Member", gender="male", family=self.asona)

    def test_a_member_pays_own_family_rate_on_their_own_familys_funeral_and_general_rate_on_the_other(self):
        asona_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Asona Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        bretuo_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Bretuo Deceased", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("60"),
        )
        own_family_obligation = ContributionObligation.objects.get(funeral_event=asona_funeral, member=self.member)
        outsider_obligation = ContributionObligation.objects.get(funeral_event=bretuo_funeral, member=self.member)
        self.assertEqual(own_family_obligation.rate_type, "own_family")
        self.assertEqual(outsider_obligation.rate_type, "general")
        self.assertEqual(outsider_obligation.expected_amount, Decimal("5"))  # the general rate, not the other family's own-family rate

    def test_the_batch_pay_all_feature_settles_both_funerals_own_family_and_general_in_one_call(self):
        """Re-confirms the earlier multi-funeral efficiency feature genuinely covers this exact scenario."""
        asona_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Asona Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Bretuo Deceased", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-07-02", collection_start_date="2026-07-02",
            actor=self.admin, own_family_amount=Decimal("60"),
        )
        payments = funeral_services.record_payments_across_active_funerals(member=self.member, method="cash", collector_name="Collector")
        self.assertEqual(len(payments), 2)
        total_paid = sum(p.amount for p in payments)
        self.assertEqual(total_paid, Decimal("55"))  # 50 (own family) + 5 (general, on the other funeral)

from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from contribution_rules import services as contribution_rules_services
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from tenants.models import Community


def _years_ago(years, extra_days=0):
    """Test helper — a real calendar date exactly `years` years and `extra_days` days before today."""
    today = date.today()
    try:
        d = today.replace(year=today.year - years)
    except ValueError:
        d = today.replace(year=today.year - years, day=28)
    from datetime import timedelta
    return d - timedelta(days=extra_days)


class AgeEligibilityTests(TestCase):
    """
    'Once a community member gets to 20 years and he's not schooling
    or an apprentice he has to mandatory pay for contribution...
    note that even if the person is a student or an apprentice and
    more than 25 years should still have to pay for the contribution.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ae-bodi", default_general_male_amount=Decimal("5"))
        self.admin = User.objects.create_user(username="ae_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def _register(self, name, age_years, occupation_status="none", age_extra_days=0):
        member = member_services.register_member(community=self.bodi, full_name=name, gender="male", family=self.asona)
        member.date_of_birth = _years_ago(age_years, age_extra_days)
        member.occupation_status = occupation_status
        member.save(update_fields=["date_of_birth", "occupation_status"])
        return member

    def test_a_member_under_20_is_exempt_regardless_of_occupation_status(self):
        member = self._register("Under 20", 19)
        self.assertNotIn(member, contribution_rules_services.eligible_members_queryset(self.bodi))
        self.assertFalse(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_a_member_exactly_20_and_not_a_student_or_apprentice_is_mandatory(self):
        member = self._register("Exactly 20, working", 20, occupation_status="none")
        self.assertIn(member, contribution_rules_services.eligible_members_queryset(self.bodi))
        self.assertTrue(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_a_20_year_old_student_is_exempt(self):
        member = self._register("20yo student", 20, occupation_status="student")
        self.assertNotIn(member, contribution_rules_services.eligible_members_queryset(self.bodi))

    def test_a_20_year_old_apprentice_is_exempt(self):
        member = self._register("20yo apprentice", 20, occupation_status="apprentice")
        self.assertNotIn(member, contribution_rules_services.eligible_members_queryset(self.bodi))

    def test_a_24_year_old_student_is_still_exempt(self):
        member = self._register("24yo student", 24)
        member.occupation_status = "student"
        member.save(update_fields=["occupation_status"])
        self.assertNotIn(member, contribution_rules_services.eligible_members_queryset(self.bodi))

    def test_a_25_year_old_student_must_pay_regardless(self):
        """The explicit override — exactly the scenario the document calls out by name."""
        member = self._register("25yo student", 25, occupation_status="student")
        self.assertIn(member, contribution_rules_services.eligible_members_queryset(self.bodi))
        self.assertTrue(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_a_25_year_old_apprentice_must_pay_regardless(self):
        member = self._register("25yo apprentice", 25, occupation_status="apprentice")
        self.assertTrue(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_a_30_year_old_ordinary_member_is_mandatory(self):
        member = self._register("30yo ordinary", 30)
        self.assertTrue(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_a_member_with_no_recorded_birth_date_is_never_silently_exempted(self):
        """The critical safe-default: missing data must never quietly shrink an existing community's obligated membership."""
        member = member_services.register_member(community=self.bodi, full_name="No DOB Recorded", gender="male", family=self.asona)
        self.assertIsNone(member.date_of_birth)
        self.assertIn(member, contribution_rules_services.eligible_members_queryset(self.bodi))
        self.assertTrue(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_one_day_before_the_20th_birthday_is_still_exempt(self):
        member = self._register("Almost 20", 20, age_extra_days=-1)  # birthday is tomorrow — still 19 today
        self.assertFalse(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_one_day_after_the_25th_birthday_a_student_must_pay(self):
        member = self._register("Just turned 25, student", 25, occupation_status="student", age_extra_days=1)  # birthday was yesterday — already 25
        self.assertTrue(contribution_rules_services.is_contribution_eligible_by_age(member))

    def test_age_exemption_actually_prevents_a_real_obligation_from_being_generated(self):
        """End-to-end proof, not just the queryset helper in isolation — a genuine funeral's own generate_obligations must respect this."""
        exempt_student = self._register("Exempt Student", 20, occupation_status="student")
        obligated_adult = self._register("Obligated Adult", 20, occupation_status="none")

        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.assertFalse(ContributionObligation.objects.filter(funeral_event=funeral, member=exempt_student).exists())
        self.assertTrue(ContributionObligation.objects.filter(funeral_event=funeral, member=obligated_adult).exists())


class MembersNeedingAgeReviewTests(TestCase):
    """'Once the community member gets to 20 years the system should fetch them out for each family executive to update their data.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="mnar-bodi")
        self.admin = User.objects.create_user(username="mnar_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def _register(self, name, age_years, occupation_status="none"):
        member = member_services.register_member(community=self.bodi, full_name=name, gender="male", family=self.asona)
        member.date_of_birth = _years_ago(age_years)
        member.occupation_status = occupation_status
        member.save(update_fields=["date_of_birth", "occupation_status"])
        return member

    def test_a_member_who_just_turned_20_is_surfaced_for_review(self):
        member = self._register("Just Turned 20", 20)
        self.assertIn(member, contribution_rules_services.members_needing_age_review(self.bodi))

    def test_a_20_to_24_year_old_student_is_surfaced_for_periodic_review(self):
        member = self._register("22yo Student", 22, occupation_status="student")
        self.assertIn(member, contribution_rules_services.members_needing_age_review(self.bodi))

    def test_a_member_who_just_turned_25_while_still_a_student_is_surfaced(self):
        member = self._register("Just Turned 25 Student", 25, occupation_status="student")
        self.assertIn(member, contribution_rules_services.members_needing_age_review(self.bodi))

    def test_an_ordinary_30_year_old_with_no_special_status_is_not_surfaced(self):
        """No genuine review need — already obligated, nothing time-limited or newly-crossed about their situation."""
        member = self._register("Ordinary 30yo", 30)
        self.assertNotIn(member, contribution_rules_services.members_needing_age_review(self.bodi))

    def test_a_member_under_20_is_not_surfaced(self):
        member = self._register("Under 20", 15)
        self.assertNotIn(member, contribution_rules_services.members_needing_age_review(self.bodi))

    def test_a_member_with_no_birth_date_is_not_surfaced_here_but_is_flagged_separately(self):
        member = member_services.register_member(community=self.bodi, full_name="No DOB", gender="male", family=self.asona)
        self.assertNotIn(member, contribution_rules_services.members_needing_age_review(self.bodi))
        self.assertIn(member, contribution_rules_services.members_missing_birth_date(self.bodi))

from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from members.models import Member
from tenants.models import Community


class ExecutiveDashboardNeverBillableTests(TestCase):
    """
    'Since those who have executive role still have community member
    dashboard, no executive dashboard should be billed or should be
    available for the collector or for any activities... those
    dashboards are special and have to be treated as special.'

    This platform already keeps a User (a login, an "executive
    dashboard") and a Member (a resident profile, the only thing a
    funeral obligation is ever recorded against) as two genuinely
    separate models — this file proves that guarantee directly rather
    than assuming it. A person's EXECUTIVE STANDING is a fact about
    their User account; what they owe toward a funeral is a fact about
    their Member profile, and those two things never conflate.
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="edn-bodi",
            default_general_male_amount=Decimal("5"),
        )
        self.admin = User.objects.create_user(username="edn_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.treasurer_user = User.objects.create_user(username="edn_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.treasurer_member = Member.objects.create(
            community=self.bodi, family=self.asona, full_name="The Treasurer", gender="male", linked_user=self.treasurer_user,
        )

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_contribution_obligations_are_never_recorded_against_a_user_only_ever_a_member(self):
        """The direct, structural proof — the model itself has no path from an obligation to a User at all."""
        field_names = {f.name for f in ContributionObligation._meta.get_fields()}
        self.assertIn("member", field_names)
        self.assertNotIn("user", field_names)
        self.assertNotIn("linked_user", field_names)

    def test_an_executive_still_owes_and_pays_through_their_member_profile_exactly_like_anyone_else(self):
        """The Treasurer's own contribution obligation exists — proving their executive standing changes nothing about how they're billed."""
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.treasurer_member)
        self.assertEqual(obligation.member_id, self.treasurer_member.id)
        # The obligation's own member row carries no trace of "treasurer"
        # anywhere — a collector recording this payment sees a resident
        # profile, never an executive dashboard.
        self.assertFalse(hasattr(obligation, "user"))

    def test_a_collectors_member_search_returns_member_profiles_never_user_accounts(self):
        """The collector's own search surface (search_members) returns Member rows — the actual thing a front-desk collector works from."""
        results = member_services.search_members(community=self.bodi, query="Treasurer", actor=self.admin)
        self.assertTrue(all(isinstance(r, Member) for r in results))
        found = [m for m in results if m.id == self.treasurer_member.id]
        self.assertEqual(len(found), 1)

    def test_deleting_the_executives_login_account_leaves_their_billing_history_completely_intact(self):
        """The clearest proof of separation: removing the 'executive dashboard' entirely doesn't touch a single obligation."""
        self.treasurer_user.delete()
        self.treasurer_member.refresh_from_db()
        self.assertIsNone(self.treasurer_member.linked_user_id)
        # The obligation is untouched — billing history belongs to the
        # Member, never to the login/dashboard that happened to be
        # linked to them.
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.treasurer_member)
        self.assertIsNotNone(obligation)

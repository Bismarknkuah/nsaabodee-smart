from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from contribution_rules import services as rule_services
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class TownElderTransferTests(TestCase):
    """
    'They should also be registered as town elders which consist of
    the chief, queen mother, linguist, and other town executive...
    since you become a town elder the community admin or community
    executive should be able to transfer you.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tet-bodi")
        self.admin = User.objects.create_user(username="tet_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="tet_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.collector = User.objects.create_user(username="tet_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Future Elder", gender="male", family=self.asona)

    def test_community_admin_can_transfer_a_member_to_town_elder(self):
        member_services.transfer_to_town_elder(member=self.member, title="chief", actor=self.admin)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_town_leader)
        self.assertEqual(self.member.town_elder_title, "chief")

    def test_chairman_can_also_transfer(self):
        member_services.transfer_to_town_elder(member=self.member, title="queen_mother", actor=self.chairman)
        self.member.refresh_from_db()
        self.assertEqual(self.member.town_elder_title, "queen_mother")

    def test_a_collector_cannot_transfer_a_member_to_town_elder(self):
        with self.assertRaises(ValidationError):
            member_services.transfer_to_town_elder(member=self.member, title="linguist", actor=self.collector)

    def test_every_recognized_title_is_accepted(self):
        for title in ("chief", "queen_mother", "linguist", "other"):
            m = member_services.register_member(community=self.bodi, full_name=f"Elder {title}", gender="male", family=self.asona)
            member_services.transfer_to_town_elder(member=m, title=title, actor=self.admin)
            m.refresh_from_db()
            self.assertEqual(m.town_elder_title, title)

    def test_an_unrecognized_title_is_rejected(self):
        with self.assertRaises(ValidationError):
            member_services.transfer_to_town_elder(member=self.member, title="not_a_real_title", actor=self.admin)


class TownEldersLedgerSeparationTests(TestCase):
    """'The community ledger is for all community members excluding town elders who have their own ledger and they pay higher than all the member.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="tels-bodi",
            default_general_male_amount=Decimal("5"), default_town_leader_amount=Decimal("100"),
        )
        self.admin = User.objects.create_user(username="tels_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary Member", gender="male", family=self.bretuo)
        self.elder = member_services.register_member(community=self.bodi, full_name="The Chief", gender="male", family=self.bretuo)
        member_services.transfer_to_town_elder(member=self.elder, title="chief", actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _obligation_for(self, member):
        from funerals.models import ContributionObligation
        return ContributionObligation.objects.get(funeral_event=self.funeral, member=member)

    def test_a_town_elder_gets_the_town_elder_rate_type_not_general(self):
        self.assertEqual(self._obligation_for(self.elder).rate_type, "town_elder")

    def test_an_ordinary_member_still_gets_general(self):
        self.assertEqual(self._obligation_for(self.ordinary_member).rate_type, "general")

    def test_town_elder_pays_more_than_an_ordinary_general_member(self):
        """'They pay higher than all the member.'"""
        elder_amount = self._obligation_for(self.elder).expected_amount
        ordinary_amount = self._obligation_for(self.ordinary_member).expected_amount
        self.assertGreater(elder_amount, ordinary_amount)

    def test_family_statement_excludes_town_elder_contributions_from_the_general_bucket(self):
        """The community ledger's own family-level rollup must not quietly include Town Elder money in the ordinary "general" figure."""
        from reports.services import family_statement
        statement = family_statement(self.bretuo)
        # Only the ordinary member's contribution should appear in the
        # "as outsider" general bucket — the elder's own, higher
        # contribution belongs to a separate ledger entirely.
        self.assertEqual(statement["members_as_outsiders_elsewhere"]["obligation_count"], 1)

    def test_family_ledger_itself_is_unaffected_and_still_correct_for_ordinary_members(self):
        """'Don't forget each family also have a family ledger' — the pre-existing family_ledger bucket must keep working exactly as before."""
        from reports.services import family_statement
        asona_member = member_services.register_member(community=self.bodi, full_name="Asona's Own Member", gender="male", family=self.asona)
        statement = family_statement(self.asona)
        self.assertIn("family_ledger", statement)
        self.assertEqual(statement["family_ledger"]["obligation_count"], 1)

    def test_family_ledger_excludes_a_town_elder_even_if_they_belong_to_this_same_family(self):
        """A Town Elder who happens to be part of the deceased's own family still pays the elder rate, never the family rate — so their contribution correctly never counts toward the family's own ledger."""
        from reports.services import family_statement
        # Close the setUp funeral first — otherwise a newly-registered
        # Asona member would auto-enroll into it as "own_family" BEFORE
        # the transfer below happens (transfers are never retroactive),
        # leaving a stale obligation that would wrongly inflate
        # family_ledger regardless of what this test actually checks.
        funeral_services.close_funeral_event(funeral=self.funeral, actor=self.admin)
        elder_in_deceased_family = member_services.register_member(community=self.bodi, full_name="Elder In Asona", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=elder_in_deceased_family, title="linguist", actor=self.admin)
        new_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Another Asona Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-08-01", collection_start_date="2026-08-01", actor=self.admin, own_family_amount=Decimal("50"),
        )
        statement = family_statement(self.asona)
        self.assertEqual(statement["family_ledger"]["obligation_count"], 0)

    def test_funeral_summary_reports_town_elder_as_its_own_distinct_bucket(self):
        summary = funeral_services.funeral_summary(self.funeral)
        self.assertIn("town_elder", summary)
        self.assertEqual(summary["town_elder"]["member_count"], 1)
        self.assertEqual(summary["general"]["member_count"], 1)


class TownElderRateSettingTests(TestCase):
    """'It is being managed by the king and he set price for each for them, so the town leader/king is the head of the community's elders ledger.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ters-bodi", default_town_leader_amount=Decimal("100"))
        self.chief = User.objects.create_user(username="ters_chief", password="a-real-password-123", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.admin = User.objects.create_user(username="ters_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

    def test_the_chief_can_set_the_town_elder_rate(self):
        rule_services.set_town_elder_rate(community=self.bodi, amount=Decimal("250"), actor=self.chief)
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.default_town_leader_amount, Decimal("250"))

    def test_community_admin_cannot_set_the_town_elder_rate(self):
        """This is deliberately the chief's own, separate authority — not folded into the Admin/Chairman/Secretary's shared rate-setting."""
        with self.assertRaises(ValidationError):
            rule_services.set_town_elder_rate(community=self.bodi, amount=Decimal("250"), actor=self.admin)

    def test_a_zero_or_negative_rate_is_rejected(self):
        with self.assertRaises(ValidationError):
            rule_services.set_town_elder_rate(community=self.bodi, amount=Decimal("0"), actor=self.chief)

    def test_the_new_rate_applies_to_a_newly_opened_funeral_not_retroactively(self):
        from families import services as family_services
        from funerals import services as funeral_services

        asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        elder = member_services.register_member(community=self.bodi, full_name="An Elder", gender="male", family=asona)
        member_services.transfer_to_town_elder(member=elder, title="linguist", actor=self.admin)

        old_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Old Funeral Deceased", deceased_gender="male",
            deceased_family=asona, date_of_death="2026-06-01", collection_start_date="2026-06-01", actor=self.admin, own_family_amount=Decimal("50"),
        )
        rule_services.set_town_elder_rate(community=self.bodi, amount=Decimal("300"), actor=self.chief)
        new_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="New Funeral Deceased", deceased_gender="male",
            deceased_family=asona, date_of_death="2026-07-01", collection_start_date="2026-07-01", actor=self.admin, own_family_amount=Decimal("50"),
        )

        from funerals.models import ContributionObligation
        old_obligation = ContributionObligation.objects.get(funeral_event=old_funeral, member=elder)
        new_obligation = ContributionObligation.objects.get(funeral_event=new_funeral, member=elder)
        self.assertEqual(old_obligation.expected_amount, Decimal("100"))
        self.assertEqual(new_obligation.expected_amount, Decimal("300"))


class TownElderHttpEndpointTests(TestCase):
    """HTTP-level round trips for the three new Town Elder endpoints — never trust an endpoint works without an actual request through it."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="teh-bodi",
            default_general_male_amount=Decimal("5"), default_town_leader_amount=Decimal("100"),
        )
        self.admin = User.objects.create_user(username="teh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="teh_chief", password="a-real-password-123", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="HTTP Future Elder", gender="male", family=self.asona)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_transfer_to_town_elder(self):
        client = self._login("teh_admin")
        res = client.post(f"/api/members/{self.member.id}/transfer-to-town-elder/", {"title": "chief"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_town_leader)
        self.assertEqual(self.member.town_elder_title, "chief")

    def test_full_http_set_town_elder_rate(self):
        client = self._login("teh_chief")
        res = client.post("/api/contribution-rules/town-elder-rate/", {"amount": "500"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.bodi.refresh_from_db()
        self.assertEqual(self.bodi.default_town_leader_amount, Decimal("500"))

    def test_full_http_set_town_elder_rate_rejects_community_admin(self):
        client = self._login("teh_admin")
        res = client.post("/api/contribution-rules/town-elder-rate/", {"amount": "500"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_full_http_town_elders_ledger_report(self):
        member_services.transfer_to_town_elder(member=self.member, title="chief", actor=self.admin)
        funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Someone Else", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        client = self._login("teh_chief")
        res = client.get("/api/reports/town-elders-ledger/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["town_elder_count"], 1)
        self.assertEqual(res.data["members"][0]["title"], "chief")

    def test_a_collector_cannot_view_the_town_elders_ledger_report(self):
        User.objects.create_user(username="teh_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        client = self._login("teh_collector")
        res = client.get("/api/reports/town-elders-ledger/")
        self.assertEqual(res.status_code, 403)


class TownElderRemovalAndChiefManagementTests(TestCase):
    """'The town leader should also have user management and system settings to manage the town elders ledger.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="term-bodi")
        self.admin = User.objects.create_user(username="term_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="term_chief", password="a-real-password-123", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.collector = User.objects.create_user(username="term_collector", password="x", community=self.bodi, role=Role.COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="An Elder", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=self.member, title="linguist", actor=self.admin)

    def test_the_chief_can_now_also_transfer_a_member_to_town_elder(self):
        """'The town leader/king is the head of the community's elders ledger' — extended to actually managing membership, not just the rate."""
        other_member = member_services.register_member(community=self.bodi, full_name="Another Future Elder", gender="male", family=self.asona)
        member_services.transfer_to_town_elder(member=other_member, title="queen_mother", actor=self.chief)
        other_member.refresh_from_db()
        self.assertTrue(other_member.is_town_leader)

    def test_the_chief_can_remove_a_member_from_town_elder_status(self):
        member_services.remove_from_town_elder(member=self.member, actor=self.chief)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_town_leader)
        self.assertIsNone(self.member.town_elder_title)

    def test_a_collector_cannot_remove_someone_from_town_elder_status(self):
        with self.assertRaises(ValidationError):
            member_services.remove_from_town_elder(member=self.member, actor=self.collector)

    def test_removing_someone_not_currently_an_elder_is_rejected(self):
        ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary Member", gender="male", family=self.asona)
        with self.assertRaises(ValidationError):
            member_services.remove_from_town_elder(member=ordinary_member, actor=self.chief)

    def test_removal_is_never_retroactive_for_an_already_open_funeral(self):
        old_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Old Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"), town_leader_amount=Decimal("100"),
        )
        member_services.remove_from_town_elder(member=self.member, actor=self.chief)
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=old_funeral, member=self.member)
        self.assertEqual(obligation.rate_type, "town_elder")

    def test_full_http_removal_round_trip(self):
        from rest_framework.test import APIClient
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "term_chief", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(f"/api/members/{self.member.id}/remove-from-town-elder/")
        self.assertEqual(res.status_code, 200)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_town_leader)

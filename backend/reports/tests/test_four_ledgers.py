from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from gifts.models import GiftDonation
from members import services as member_services
from reports import services
from tenants.models import Community


class FourLedgerFamilyStatementTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.asona_member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.outsider_member = member_services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.bretuo)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_family_member_pays_family_ledger_not_community_ledger(self):
        """The exact rule described: a deceased family's own members pay the family ledger, never the community ledger, for their own funeral."""
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.asona_member)
        self.assertEqual(obligation.rate_type, "own_family")

        statement = services.family_statement(self.asona)
        self.assertEqual(Decimal(statement["family_ledger"]["expected_total"]), Decimal("50"))

    def test_outsider_member_payment_shows_up_in_community_ledger_for_this_family(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.outsider_member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("3"), method="cash")

        statement = services.family_statement(self.asona)
        self.assertEqual(Decimal(statement["community_ledger"]["collected_total"]), Decimal("3"))
        # And this must NOT show up in the family ledger — the two never mix.
        self.assertEqual(Decimal(statement["family_ledger"]["collected_total"]), Decimal("0"))

    def test_guest_and_town_leader_ledgers_appear_separately_in_family_statement(self):
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("40"))
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="The Chief", amount_cash=Decimal("500"),
            donor_category=GiftDonation.DonorCategory.TOWN_LEADER,
        )

        statement = services.family_statement(self.asona)
        self.assertEqual(Decimal(statement["guest_ledger"]["total_value"]), Decimal("40"))
        self.assertEqual(Decimal(statement["town_leaders_ledger"]["total_value"]), Decimal("500"))

    def test_funeral_full_ledger_breakdown_combines_all_four(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.asona_member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("40"))
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="The Chief", amount_cash=Decimal("500"),
            donor_category=GiftDonation.DonorCategory.TOWN_LEADER,
        )

        breakdown = services.funeral_full_ledger_breakdown(self.funeral)
        self.assertEqual(Decimal(breakdown["family_ledger"]["collected_total"]), Decimal("50"))
        self.assertEqual(Decimal(breakdown["guest_ledger"]["total_value"]), Decimal("40"))
        self.assertEqual(Decimal(breakdown["town_leaders_ledger"]["total_value"]), Decimal("500"))


class FamilyHeadAccessTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.random_user = User.objects.create_user(username="rando", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_family_head_can_view_his_own_family_statement(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "abusuapanin", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/reports/families/{self.asona.id}/statement/")
        self.assertEqual(res.status_code, 200)

    def test_family_head_can_download_pdf(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "abusuapanin", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/reports/families/{self.asona.id}/statement/?export=pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")

    def test_ordinary_community_member_cannot_view_a_family_statement_that_isnt_theirs(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "rando", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/reports/families/{self.asona.id}/statement/")
        self.assertEqual(res.status_code, 403)


class CommitteeDonationStrippingHttpTests(TestCase):
    """The same restriction, checked at the actual HTTP/view layer for both endpoints that expose it."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin2", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="treasurer2", password="x", community=self.bodi, role=Role.TREASURER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("40"))

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_treasurer_sees_family_statement_without_donation_fields(self):
        client = self._login("treasurer2")
        res = client.get(f"/api/reports/families/{self.asona.id}/statement/")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("guest_ledger", res.data)
        self.assertNotIn("town_leaders_ledger", res.data)
        self.assertIn("family_ledger", res.data)  # mandatory ledgers still visible

    def test_community_admin_sees_family_statement_with_donation_fields(self):
        client = self._login("admin2")
        res = client.get(f"/api/reports/families/{self.asona.id}/statement/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("guest_ledger", res.data)
        self.assertEqual(Decimal(res.data["guest_ledger"]["total_value"]), Decimal("40"))

    def test_treasurer_sees_funeral_ledger_breakdown_without_donation_fields(self):
        client = self._login("treasurer2")
        res = client.get(f"/api/reports/funerals/{self.funeral.id}/ledger-breakdown/")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("guest_ledger", res.data)
        self.assertIn("family_ledger", res.data)

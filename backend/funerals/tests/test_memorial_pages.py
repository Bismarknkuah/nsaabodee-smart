from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import MemorialTribute
from gifts import services as gift_services
from members import services as member_services
from tenants.models import Community


class MemorialPageServiceTests(TestCase):
    """
    'A dignified public page for the funeral, event details, donor
    tributes, and a lasting place to remember your loved one.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="the_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        other_head_member = member_services.register_member(community=self.bodi, full_name="Other Head", gender="male", family=self.bretuo)
        self.other_head_user = User.objects.create_user(username="other_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=other_head_member, user=self.other_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=other_head_member, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_the_deceased_familys_own_head_can_create_the_memorial_page(self):
        page = funeral_services.create_or_update_memorial_page(
            funeral=self.funeral, actor=self.head_user, tribute_message="In loving memory of Yaw."
        )
        self.assertEqual(page.tribute_message, "In loving memory of Yaw.")

    def test_a_different_familys_head_cannot_create_this_funerals_memorial_page(self):
        with self.assertRaises(ValidationError):
            funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.other_head_user, tribute_message="Not my family's page")

    def test_community_admin_can_create_the_page_for_any_family(self):
        page = funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="Community admin wrote this")
        self.assertIsNotNone(page)

    def test_a_funeral_with_no_memorial_page_returns_none_publicly(self):
        self.assertIsNone(funeral_services.get_public_memorial_page(self.funeral))

    def test_an_unpublished_page_returns_none_publicly(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="Draft", is_published=False)
        self.assertIsNone(funeral_services.get_public_memorial_page(self.funeral))

    def test_a_published_page_returns_real_data_publicly(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="In loving memory")
        data = funeral_services.get_public_memorial_page(self.funeral)
        self.assertEqual(data["deceased_name"], "Yaw Asona")
        self.assertEqual(data["tribute_message"], "In loving memory")
        self.assertEqual(data["tributes"], [])

    def test_the_public_page_never_includes_a_contribution_total_unless_opted_in(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x")
        data = funeral_services.get_public_memorial_page(self.funeral)
        self.assertNotIn("contribution_total", data)

    def test_opting_in_shows_only_an_aggregate_total_never_individual_donor_detail(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x", show_contribution_total=True)
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("20"))
        data = funeral_services.get_public_memorial_page(self.funeral)
        self.assertIn("contribution_total", data)
        self.assertEqual(Decimal(data["contribution_total"]), Decimal("20"))
        # The whole point of the safeguard: no donor names, no per-person breakdown, anywhere in the public payload.
        self.assertNotIn("donor_name", str(data))
        self.assertNotIn("A Guest", str(data))

    def test_submitting_a_tribute_is_unapproved_by_default_and_invisible_publicly(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x")
        tribute = funeral_services.submit_tribute(funeral=self.funeral, author_name="A Friend", message="Rest well.")
        self.assertFalse(tribute.is_approved)
        data = funeral_services.get_public_memorial_page(self.funeral)
        self.assertEqual(data["tributes"], [])

    def test_an_approved_tribute_shows_up_publicly(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x")
        tribute = funeral_services.submit_tribute(funeral=self.funeral, author_name="A Friend", message="Rest well.")
        funeral_services.approve_tribute(tribute=tribute, actor=self.admin)
        data = funeral_services.get_public_memorial_page(self.funeral)
        self.assertEqual(len(data["tributes"]), 1)
        self.assertEqual(data["tributes"][0]["author_name"], "A Friend")

    def test_cannot_submit_a_tribute_without_a_name_or_message(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x")
        with self.assertRaises(ValidationError):
            funeral_services.submit_tribute(funeral=self.funeral, author_name="", message="Rest well.")
        with self.assertRaises(ValidationError):
            funeral_services.submit_tribute(funeral=self.funeral, author_name="A Friend", message="")

    def test_only_a_family_officer_or_admin_can_approve_a_tribute(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x")
        tribute = funeral_services.submit_tribute(funeral=self.funeral, author_name="A Friend", message="Rest well.")
        with self.assertRaises(ValidationError):
            funeral_services.approve_tribute(tribute=tribute, actor=self.other_head_user)

    def test_rejecting_a_tribute_deletes_it(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x")
        tribute = funeral_services.submit_tribute(funeral=self.funeral, author_name="Spam", message="inappropriate")
        funeral_services.reject_tribute(tribute=tribute, actor=self.admin)
        self.assertFalse(MemorialTribute.objects.filter(id=tribute.id).exists())

    def test_management_listing_includes_pending_tributes_not_just_approved(self):
        funeral_services.create_or_update_memorial_page(funeral=self.funeral, actor=self.admin, tribute_message="x")
        funeral_services.submit_tribute(funeral=self.funeral, author_name="Pending Friend", message="hi")
        approved = funeral_services.submit_tribute(funeral=self.funeral, author_name="Approved Friend", message="hi")
        funeral_services.approve_tribute(tribute=approved, actor=self.admin)
        tributes = funeral_services.list_all_tributes_for_management(funeral=self.funeral, actor=self.admin)
        self.assertEqual(len(tributes), 2)


class MemorialPageHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin2", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _login(self, username="admin2"):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_viewing_the_memorial_page_requires_no_login_at_all(self):
        client = APIClient()  # deliberately no credentials
        self._login().post(f"/api/funerals/{self.funeral.id}/memorial/manage/", {"tribute_message": "In memory", "is_published": True})
        res = client.get(f"/api/funerals/{self.funeral.id}/memorial/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["deceased_name"], "Yaw Asona")

    def test_a_funeral_with_no_page_returns_404_publicly(self):
        client = APIClient()
        res = client.get(f"/api/funerals/{self.funeral.id}/memorial/")
        self.assertEqual(res.status_code, 404)

    def test_submitting_a_tribute_requires_no_login_either(self):
        self._login().post(f"/api/funerals/{self.funeral.id}/memorial/manage/", {"tribute_message": "In memory", "is_published": True})
        client = APIClient()
        res = client.post(f"/api/funerals/{self.funeral.id}/memorial/tributes/", {"author_name": "A Friend", "message": "Rest well"})
        self.assertEqual(res.status_code, 201)

    def test_managing_the_page_requires_login_and_permission(self):
        client = APIClient()
        res = client.post(f"/api/funerals/{self.funeral.id}/memorial/manage/", {"tribute_message": "hi"})
        self.assertEqual(res.status_code, 401)

    def test_full_moderation_flow_via_http(self):
        admin_client = self._login()
        admin_client.post(f"/api/funerals/{self.funeral.id}/memorial/manage/", {"tribute_message": "In memory", "is_published": True})

        public_client = APIClient()
        public_client.post(f"/api/funerals/{self.funeral.id}/memorial/tributes/", {"author_name": "A Friend", "message": "Rest well"})

        pending = admin_client.get(f"/api/funerals/{self.funeral.id}/memorial/tributes/manage/")
        self.assertEqual(len(pending.data), 1)
        self.assertFalse(pending.data[0]["is_approved"])
        tribute_id = pending.data[0]["id"]

        approve_res = admin_client.post(f"/api/funerals/{self.funeral.id}/memorial/tributes/{tribute_id}/approve/")
        self.assertEqual(approve_res.status_code, 200)

        public_view = public_client.get(f"/api/funerals/{self.funeral.id}/memorial/")
        self.assertEqual(len(public_view.data["tributes"]), 1)

    def test_the_public_memorial_page_shows_active_payout_accounts_so_guests_know_how_to_contribute(self):
        """'Guests to use to donate their gift or contribute' — a guest scanning the QR code needs to actually see HOW to send money, not just a tribute wall."""
        from tenants import services as tenant_services
        tenant_services.add_payout_account(
            community=self.bodi, actor=self.admin, account_type="mobile_money",
            provider_name="MTN Mobile Money", account_number="0244000000", account_holder_name="Bodi Anidasoɔ Welfare",
        )
        admin_client = self._login()
        admin_client.post(f"/api/funerals/{self.funeral.id}/memorial/manage/", {"tribute_message": "In memory", "is_published": True})

        public_client = APIClient()
        res = public_client.get(f"/api/funerals/{self.funeral.id}/memorial/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["payout_accounts"]), 1)
        self.assertEqual(res.data["payout_accounts"][0]["provider_name"], "MTN Mobile Money")

    def test_an_inactive_payout_account_never_shows_on_the_public_memorial_page(self):
        from tenants import services as tenant_services
        account = tenant_services.add_payout_account(
            community=self.bodi, actor=self.admin, account_type="bank",
            provider_name="GCB Bank", account_number="123456", account_holder_name="Bodi Anidasoɔ",
        )
        tenant_services.deactivate_payout_account(account=account, actor=self.admin)
        admin_client = self._login()
        admin_client.post(f"/api/funerals/{self.funeral.id}/memorial/manage/", {"tribute_message": "In memory", "is_published": True})

        public_client = APIClient()
        res = public_client.get(f"/api/funerals/{self.funeral.id}/memorial/")
        self.assertEqual(res.data["payout_accounts"], [])

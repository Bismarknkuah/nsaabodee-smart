from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from gifts.models import DonationAccountRegistration, GiftDonation
from members import services as member_services
from tenants.models import Community


class DonationAccountRegistrationTests(TestCase):
    """
    'No executive user role should have the button to receive
    donations, should be available for only members and it should be
    activated when the family heads approve it.'
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

        self.receiver1 = member_services.register_member(community=self.bodi, full_name="Receiver One", gender="male", family=self.asona)
        self.receiver2 = member_services.register_member(community=self.bodi, full_name="Receiver Two", gender="female", family=self.asona)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="asona_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.chairman = User.objects.create_user(username="donation_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_a_gift_cannot_be_attributed_to_an_unregistered_member(self):
        with self.assertRaises(ValidationError):
            gift_services.record_gift_donation(
                funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("50"),
                received_by_member=self.receiver1,
            )

    def test_when_the_family_head_registers_a_member_it_is_immediately_active(self):
        registration = gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.head_user)
        self.assertTrue(registration.is_active)

    def test_once_the_family_head_registers_them_a_gift_can_be_attributed(self):
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.head_user)
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("50"),
            received_by_member=self.receiver1,
        )
        self.assertEqual(donation.received_by_member_id, self.receiver1.id)

    def test_when_someone_other_than_the_family_head_registers_it_starts_inactive(self):
        """'It should be activated when the family heads approve it' — anyone else's registration is a pending request, not an immediate capability."""
        registration = gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.chairman)
        self.assertFalse(registration.is_active)

    def test_a_gift_cannot_be_attributed_to_a_pending_not_yet_approved_registration(self):
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.chairman)
        with self.assertRaises(ValidationError):
            gift_services.record_gift_donation(
                funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("50"),
                received_by_member=self.receiver1,
            )

    def test_the_family_head_approving_a_pending_registration_activates_it(self):
        registration = gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.chairman)
        gift_services.approve_donation_account_registration(registration=registration, actor=self.head_user)
        registration.refresh_from_db()
        self.assertTrue(registration.is_active)
        donation = gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("50"),
            received_by_member=self.receiver1,
        )
        self.assertEqual(donation.received_by_member_id, self.receiver1.id)

    def test_someone_who_is_not_this_familys_head_cannot_approve(self):
        registration = gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.chairman)
        with self.assertRaises(ValidationError):
            gift_services.approve_donation_account_registration(registration=registration, actor=self.chairman)

    def test_an_executive_role_cannot_be_registered_to_receive_donations(self):
        with self.assertRaises(ValidationError):
            gift_services.register_donation_account_holder(funeral=self.funeral, member=self.head_member, actor=self.head_user)

    def test_an_ordinary_member_with_no_linked_account_can_still_be_registered(self):
        """Most members never get a login at all — the executive-role check only applies when there's actually a linked account to check."""
        registration = gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver2, actor=self.head_user)
        self.assertTrue(registration.is_active)

    def test_more_than_one_person_can_register_for_the_same_funeral(self):
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.head_user)
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver2, actor=self.head_user)
        holders = gift_services.list_donation_account_holders(self.funeral)
        self.assertEqual(holders.count(), 2)

    def test_deregistering_prevents_further_attribution(self):
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.head_user)
        gift_services.deregister_donation_account_holder(funeral=self.funeral, member=self.receiver1)

        with self.assertRaises(ValidationError):
            gift_services.record_gift_donation(
                funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("50"),
                received_by_member=self.receiver1,
            )

    def test_gift_without_a_receiver_specified_still_works_as_before(self):
        """Formal donation-account attribution is optional — a smaller funeral can skip it entirely."""
        donation = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("50"))
        self.assertIsNone(donation.received_by_member)

    def test_donations_received_by_member_aggregates_correctly_including_momo(self):
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver1, actor=self.head_user)
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Cash Guest", amount_cash=Decimal("30"),
            received_by_member=self.receiver1, payment_method="cash",
        )
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="MoMo Guest", amount_cash=Decimal("70"),
            received_by_member=self.receiver1, payment_method="mobile_money",
        )
        # A gift NOT attributed to receiver1 must not count toward their total.
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="Unattributed Guest", amount_cash=Decimal("999"))

        result = gift_services.donations_received_by_member(self.receiver1)
        self.assertEqual(Decimal(result["total_received"]), Decimal("100"))
        self.assertEqual(result["donation_count"], 2)


class DonationAccountApprovalHttpTests(TestCase):
    """Full round-trip HTTP tests for the family-head approval workflow."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-donation-approval-http",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="donation_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.collector = User.objects.create_user(username="donation_http_collector", password="a-real-password-123", community=self.bodi, role=Role.COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.receiver = member_services.register_member(community=self.bodi, full_name="HTTP Receiver", gender="male", family=self.asona)

        self.head_member = member_services.register_member(community=self.bodi, full_name="HTTP Asona Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="donation_http_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="HTTP Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_flow_register_pending_appears_in_queue_then_approved(self):
        collector_client = self._login("donation_http_collector")
        reg_res = collector_client.post(f"/api/funerals/{self.funeral.id}/donation-accounts/", {"member_id": str(self.receiver.id)})
        self.assertEqual(reg_res.status_code, 201)
        self.assertFalse(reg_res.data["is_active"])
        registration_id = reg_res.data["id"]

        head_client = self._login("donation_http_head")
        pending_res = head_client.get("/api/donation-accounts/pending/")
        self.assertEqual(pending_res.status_code, 200)
        self.assertEqual(len(pending_res.data), 1)

        approve_res = head_client.post(f"/api/donation-accounts/{registration_id}/approve/")
        self.assertEqual(approve_res.status_code, 200)
        self.assertTrue(approve_res.data["is_active"])

    def test_a_non_family_head_has_no_pending_queue_at_all(self):
        client = self._login("donation_http_admin")
        res = client.get("/api/donation-accounts/pending/")
        self.assertEqual(res.status_code, 403)


class DonationVisibilityPermissionTests(TestCase):
    """'The funeral committee should have access to all the money paid except the donations.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="abusuapanin", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("50"))

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_treasurer_cannot_view_the_gift_ledger(self):
        client = self._login("treasurer")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        self.assertEqual(res.status_code, 403)

    def test_chairman_cannot_view_the_gift_ledger(self):
        client = self._login("chairman")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        self.assertEqual(res.status_code, 403)

    def test_the_family_head_himself_can_view_his_familys_gift_ledger(self):
        client = self._login("abusuapanin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        self.assertEqual(res.status_code, 200)

    def test_community_admin_retains_oversight_access(self):
        client = self._login("admin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        self.assertEqual(res.status_code, 200)

    def test_treasurer_can_still_view_mandatory_contribution_reports(self):
        """The exclusion is specifically about donations — Ledger 1 access for the committee is untouched."""
        client = self._login("treasurer")
        res = client.get("/api/reports/collections/daily/")
        self.assertEqual(res.status_code, 200)

    def test_donor_names_list_for_registration_is_visible_to_everyone(self):
        """Who's registered to receive is just a name list, not money — no reason to hide it from the committee."""
        client = self._login("treasurer")
        res = client.get(f"/api/funerals/{self.funeral.id}/donation-accounts/")
        self.assertEqual(res.status_code, 200)


class DashboardReflectsDonationsReceivedTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="Dashboard Asona Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="dashboard_asona_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.receiver_member = member_services.register_member(community=self.bodi, full_name="Receiver", gender="male", family=self.asona)
        self.receiver_user = User.objects.create_user(username="receiver_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.receiver_member, user=self.receiver_user, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver_member, actor=self.head_user)
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("75"), received_by_member=self.receiver_member,
        )

    def test_dashboard_reflects_donations_received_for_a_registered_receiver(self):
        from dashboard.services import build_dashboard
        result = build_dashboard(self.receiver_user)
        donations = result["sections"]["member_overview"]["donations_received"]
        self.assertEqual(Decimal(donations["total_received"]), Decimal("75"))

    def test_my_donations_received_endpoint(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "receiver_login", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/my-donations-received/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Decimal(res.data["total_received"]), Decimal("75"))

    def test_family_head_statement_shows_donation_receivers_breakdown(self):
        from reports.services import family_statement
        statement = family_statement(self.asona)
        receivers = {r["member_name"]: r["total_received"] for r in statement["donation_receivers"]}
        self.assertEqual(Decimal(receivers["Receiver"]), Decimal("75"))

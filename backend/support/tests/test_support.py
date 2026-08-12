from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from support import services
from support.models import SupportTicket
from tenants.models import Community


class SupportTicketServiceTests(TestCase):
    """
    'Only the community and temporary support should be moved or
    reported to the platform admin, all other members or executives
    support should be reported to their community admin as their
    community admin should have those reports.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-support")
        self.other_community = Community.objects.create(name="Other Town", slug="other-town-support")
        self.member = User.objects.create_user(username="support_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.chairman = User.objects.create_user(username="support_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.guest = User.objects.create_user(username="support_guest", password="x", role=Role.GUEST)
        self.platform_admin = User.objects.create_user(username="support_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.other_member = User.objects.create_user(username="support_other_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.community_admin = User.objects.create_user(username="support_community_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_community_admin = User.objects.create_user(username="support_other_community_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)

    def test_any_signed_in_user_can_submit_a_ticket_including_a_guest_with_no_community(self):
        ticket = services.submit_ticket(submitted_by=self.guest, subject="Can't see my receipts", description="The page shows nothing.")
        self.assertEqual(ticket.submitted_by_id, self.guest.id)
        self.assertIsNone(ticket.community)

    def test_a_community_members_ticket_is_attributed_to_their_community(self):
        ticket = services.submit_ticket(submitted_by=self.member, subject="Billing question", description="Why was our community charged twice?")
        self.assertEqual(ticket.community_id, self.bodi.id)

    def test_an_empty_subject_or_description_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.submit_ticket(submitted_by=self.member, subject="  ", description="Something")
        with self.assertRaises(ValidationError):
            services.submit_ticket(submitted_by=self.member, subject="Something", description="  ")

    def test_a_user_only_sees_their_own_tickets(self):
        services.submit_ticket(submitted_by=self.member, subject="Mine", description="My own issue")
        services.submit_ticket(submitted_by=self.other_member, subject="Not mine", description="Someone else's issue")
        my_tickets = services.list_my_tickets(user=self.member)
        self.assertEqual(len(my_tickets), 1)
        self.assertEqual(my_tickets[0].subject, "Mine")

    def test_a_community_admins_own_ticket_goes_to_the_platform_admins_queue(self):
        services.submit_ticket(submitted_by=self.community_admin, subject="Billing dispute", description="Our monthly charge looks wrong.")
        platform_queue = services.list_all_tickets(actor=self.platform_admin)
        self.assertEqual(len(platform_queue), 1)
        self.assertEqual(platform_queue[0].submitted_by_id, self.community_admin.id)

    def test_an_ordinary_members_ticket_never_appears_in_the_platform_admins_queue(self):
        services.submit_ticket(submitted_by=self.member, subject="Can't log in", description="Password reset isn't working.")
        platform_queue = services.list_all_tickets(actor=self.platform_admin)
        self.assertEqual(len(platform_queue), 0)

    def test_an_ordinary_members_ticket_appears_in_their_own_community_admins_queue(self):
        services.submit_ticket(submitted_by=self.member, subject="Can't log in", description="Password reset isn't working.")
        admin_queue = services.list_all_tickets(actor=self.community_admin)
        self.assertEqual(len(admin_queue), 1)
        self.assertEqual(admin_queue[0].submitted_by_id, self.member.id)

    def test_an_executives_ticket_also_routes_to_their_own_community_admin(self):
        services.submit_ticket(submitted_by=self.chairman, subject="Task assignment broken", description="Can't assign a task to a collector.")
        admin_queue = services.list_all_tickets(actor=self.community_admin)
        self.assertEqual(len(admin_queue), 1)
        self.assertEqual(admin_queue[0].submitted_by_id, self.chairman.id)

    def test_a_community_admins_own_queue_never_shows_a_fellow_community_admins_ticket(self):
        """A Community Admin's escalation is Platform Admin's business, not another Community Admin's."""
        services.submit_ticket(submitted_by=self.community_admin, subject="Billing dispute", description="Our monthly charge looks wrong.")
        admin_queue = services.list_all_tickets(actor=self.community_admin)
        self.assertEqual(len(admin_queue), 0)

    def test_a_community_admin_never_sees_another_communitys_tickets(self):
        services.submit_ticket(submitted_by=self.member, subject="Issue", description="Something in Bodi Anidasoɔ.")
        other_admin_queue = services.list_all_tickets(actor=self.other_community_admin)
        self.assertEqual(len(other_admin_queue), 0)

    def test_an_ordinary_member_cannot_list_any_ticket_queue(self):
        with self.assertRaises(ValidationError):
            services.list_all_tickets(actor=self.member)

    def test_a_community_admin_can_change_status_on_their_own_members_ticket(self):
        ticket = services.submit_ticket(submitted_by=self.member, subject="Issue", description="Description")
        services.update_ticket_status(ticket=ticket, status="resolved", actor=self.community_admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "resolved")
        self.assertIsNotNone(ticket.resolved_at)

    def test_a_community_admin_cannot_change_status_on_another_communitys_ticket(self):
        ticket = services.submit_ticket(submitted_by=self.member, subject="Issue", description="Description")
        with self.assertRaises(ValidationError):
            services.update_ticket_status(ticket=ticket, status="resolved", actor=self.other_community_admin)

    def test_only_the_platform_admin_can_change_status_on_a_community_admins_own_ticket(self):
        ticket = services.submit_ticket(submitted_by=self.community_admin, subject="Billing dispute", description="Description")
        with self.assertRaises(ValidationError):
            services.update_ticket_status(ticket=ticket, status="resolved", actor=self.other_community_admin)
        services.update_ticket_status(ticket=ticket, status="resolved", actor=self.platform_admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "resolved")

    def test_the_submitter_cannot_change_their_own_tickets_status(self):
        ticket = services.submit_ticket(submitted_by=self.member, subject="Issue", description="Description")
        with self.assertRaises(ValidationError):
            services.update_ticket_status(ticket=ticket, status="resolved", actor=self.member)

    def test_the_submitter_and_the_routed_community_admin_can_message_a_ticket_but_a_stranger_cannot(self):
        ticket = services.submit_ticket(submitted_by=self.member, subject="Issue", description="Description")
        services.post_ticket_message(ticket=ticket, sender=self.member, content="Any update?")
        services.post_ticket_message(ticket=ticket, sender=self.community_admin, content="Looking into it.")
        with self.assertRaises(ValidationError):
            services.post_ticket_message(ticket=ticket, sender=self.other_member, content="Let me in on this")
        with self.assertRaises(ValidationError):
            services.post_ticket_message(ticket=ticket, sender=self.platform_admin, content="This isn't mine to handle")

        messages = services.list_ticket_messages(ticket=ticket, actor=self.member)
        self.assertEqual(len(messages), 2)
        with self.assertRaises(ValidationError):
            services.list_ticket_messages(ticket=ticket, actor=self.other_member)


class SupportTicketHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-support-http")
        self.member = User.objects.create_user(username="support_http_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.community_admin = User.objects.create_user(username="support_http_community_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.platform_admin = User.objects.create_user(username="support_http_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_round_trip_an_ordinary_members_ticket_routes_to_their_community_admin(self):
        member_client = self._login("support_http_member")
        submit_res = member_client.post("/api/support/tickets/", {"subject": "Login issue", "description": "Can't sign in on mobile.", "priority": "high"})
        self.assertEqual(submit_res.status_code, 201)
        ticket_id = submit_res.data["id"]

        my_tickets_res = member_client.get("/api/support/tickets/")
        self.assertEqual(len(my_tickets_res.data), 1)

        admin_client = self._login("support_http_community_admin")
        all_res = admin_client.get("/api/support/tickets/all/")
        self.assertEqual(len(all_res.data), 1)

        reply_res = admin_client.post(f"/api/support/tickets/{ticket_id}/messages/", {"content": "Could you try again now?"})
        self.assertEqual(reply_res.status_code, 201)

        resolve_res = admin_client.post(f"/api/support/tickets/{ticket_id}/status/", {"status": "resolved"})
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.data["status"], "resolved")

    def test_a_community_admins_own_ticket_never_shows_in_their_own_queue_over_http(self):
        admin_client = self._login("support_http_community_admin")
        admin_client.post("/api/support/tickets/", {"subject": "Billing dispute", "description": "Charged twice this month."})
        all_res = admin_client.get("/api/support/tickets/all/")
        self.assertEqual(len(all_res.data), 0)

    def test_a_community_admins_own_ticket_appears_in_the_platform_admins_queue_over_http(self):
        admin_client = self._login("support_http_community_admin")
        admin_client.post("/api/support/tickets/", {"subject": "Billing dispute", "description": "Charged twice this month."})
        platform_client = self._login("support_http_platform_admin")
        all_res = platform_client.get("/api/support/tickets/all/")
        self.assertEqual(len(all_res.data), 1)

    def test_an_ordinary_member_cannot_view_any_ticket_queue(self):
        client = self._login("support_http_member")
        res = client.get("/api/support/tickets/all/")
        self.assertEqual(res.status_code, 403)

    def test_an_ordinary_member_cannot_change_a_tickets_status(self):
        member_client = self._login("support_http_member")
        submit_res = member_client.post("/api/support/tickets/", {"subject": "Issue", "description": "Description here"})
        res = member_client.post(f"/api/support/tickets/{submit_res.data['id']}/status/", {"status": "closed"})
        self.assertEqual(res.status_code, 403)

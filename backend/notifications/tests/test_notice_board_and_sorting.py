from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from notifications.models import Notification
from tenants import services as tenant_services
from tenants.models import Announcement, Community


class NoticeBoardNotificationTests(TestCase):
    """'Members notification should have features where they can see what has been posted on the notice board.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="nbn-bodi")
        self.bodi_admin = User.objects.create_user(username="nbn_bodi_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.platform_admin = User.objects.create_user(username="nbn_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.bodi_admin)

        self.member = member_services.register_member(community=self.bodi, full_name="Test Member", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(username="nbn_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.bodi_admin)

    def test_approving_an_announcement_notifies_every_linked_member(self):
        announcement = tenant_services.submit_announcement(community=self.bodi, title="Meeting Sunday", content="Details", actor=self.bodi_admin)
        tenant_services.approve_announcement(announcement=announcement, actor=self.platform_admin)
        self.assertTrue(Notification.objects.filter(recipient_user=self.member_user, category="notice_board_post").exists())

    def test_the_notification_message_names_the_actual_announcement(self):
        announcement = tenant_services.submit_announcement(community=self.bodi, title="Very Specific Title", content="Details", actor=self.bodi_admin)
        tenant_services.approve_announcement(announcement=announcement, actor=self.platform_admin)
        notification = Notification.objects.get(recipient_user=self.member_user, category="notice_board_post")
        self.assertIn("Very Specific Title", notification.message)

    def test_submitting_but_never_approving_notifies_nobody(self):
        """Still-pending is not yet 'posted' — no notification until a Platform Admin actually approves it."""
        tenant_services.submit_announcement(community=self.bodi, title="Still Pending", content="Details", actor=self.bodi_admin)
        self.assertFalse(Notification.objects.filter(category="notice_board_post").exists())

    def test_rejecting_an_announcement_notifies_nobody(self):
        announcement = tenant_services.submit_announcement(community=self.bodi, title="Will Be Rejected", content="Details", actor=self.bodi_admin)
        tenant_services.reject_announcement(announcement=announcement, actor=self.platform_admin, reason="Not appropriate")
        self.assertFalse(Notification.objects.filter(category="notice_board_post").exists())

    def test_a_member_with_no_linked_login_is_skipped_not_an_error(self):
        member_services.register_member(community=self.bodi, full_name="Unlinked Member", gender="male", family=self.asona)
        announcement = tenant_services.submit_announcement(community=self.bodi, title="Test", content="Details", actor=self.bodi_admin)
        # Should not raise, even though this member has no linked_user.
        tenant_services.approve_announcement(announcement=announcement, actor=self.platform_admin)

    def test_a_different_communitys_member_is_never_notified(self):
        other_community = Community.objects.create(name="Other Town", slug="nbn-other")
        other_admin = User.objects.create_user(username="nbn_other_admin", password="x", community=other_community, role=Role.COMMUNITY_ADMIN)
        other_family = family_services.create_family(community=other_community, name="Bretuo", actor=other_admin)
        other_member = member_services.register_member(community=other_community, full_name="Other Member", gender="male", family=other_family)
        other_member_user = User.objects.create_user(username="nbn_other_member", password="x", community=other_community, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=other_member, user=other_member_user, actor=other_admin)

        announcement = tenant_services.submit_announcement(community=self.bodi, title="Bodi-only announcement", content="Details", actor=self.bodi_admin)
        tenant_services.approve_announcement(announcement=announcement, actor=self.platform_admin)
        self.assertFalse(Notification.objects.filter(recipient_user=other_member_user, category="notice_board_post").exists())


class NotificationSortFilterTests(TestCase):
    """'Community members should have option where they can set or sort the notifications.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="nsf-bodi")
        self.member_user = User.objects.create_user(username="nsf_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)

        self.notice = Notification.objects.create(community=self.bodi, category="notice_board_post", message="A notice", recipient_user=self.member_user)
        self.birthday = Notification.objects.create(community=self.bodi, category="birthday", message="Happy birthday!", recipient_user=self.member_user, is_read=True)

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "nsf_member", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_filtering_by_category_returns_only_that_category(self):
        res = self._login().get("/api/notifications/?category=notice_board_post")
        self.assertEqual(res.status_code, 200)
        ids = [n["id"] for n in res.data["results"]]
        self.assertIn(str(self.notice.id), ids)
        self.assertNotIn(str(self.birthday.id), ids)

    def test_filtering_by_is_read_true_returns_only_read_notifications(self):
        res = self._login().get("/api/notifications/?is_read=true")
        ids = [n["id"] for n in res.data["results"]]
        self.assertIn(str(self.birthday.id), ids)
        self.assertNotIn(str(self.notice.id), ids)

    def test_filtering_by_is_read_false_returns_only_unread_notifications(self):
        res = self._login().get("/api/notifications/?is_read=false")
        ids = [n["id"] for n in res.data["results"]]
        self.assertIn(str(self.notice.id), ids)
        self.assertNotIn(str(self.birthday.id), ids)

    def test_default_ordering_is_newest_first(self):
        res = self._login().get("/api/notifications/")
        ids = [n["id"] for n in res.data["results"]]
        self.assertEqual(ids[0], str(self.birthday.id))  # created second, so newest

    def test_ordering_oldest_reverses_the_default(self):
        res = self._login().get("/api/notifications/?ordering=oldest")
        ids = [n["id"] for n in res.data["results"]]
        self.assertEqual(ids[0], str(self.notice.id))  # created first

    def test_category_and_is_read_filters_combine_correctly(self):
        """Verifies the |-combined base queryset still correctly ANDs with further filters, not just ORs everything together."""
        res = self._login().get("/api/notifications/?category=birthday&is_read=false")
        self.assertEqual(len(res.data["results"]), 0)  # the only birthday notification IS read

    def test_a_different_communitys_member_never_sees_these_notifications_regardless_of_filters(self):
        other_community = Community.objects.create(name="Other Town", slug="nsf-other")
        User.objects.create_user(username="nsf_other_member", password="a-real-password-123", community=other_community, role=Role.COMMUNITY_MEMBER)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "nsf_other_member", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get("/api/notifications/?category=notice_board_post")
        self.assertEqual(len(res.data["results"]), 0)

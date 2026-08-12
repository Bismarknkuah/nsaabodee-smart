from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants import services
from tenants.models import Announcement, AnnouncementReviewLog, Community


class AnnouncementServiceTests(TestCase):
    """
    'Any community who wants to post announcement on the notice board...
    has to be submitted by the community admin and the super admin has
    to approve it before... and the super admin can edit the content or
    reject it with reasons for the community admin to edit and resend
    again.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-announce")
        self.other_community = Community.objects.create(name="Other Town", slug="other-announce")
        self.bodi_admin = User.objects.create_user(username="announce_bodi_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_admin = User.objects.create_user(username="announce_other_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        self.platform_admin = User.objects.create_user(username="announce_platform_admin", password="x", role=Role.PLATFORM_ADMIN)

    def test_a_community_admin_can_submit_an_announcement_for_their_own_community(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="Meeting on Sunday", actor=self.bodi_admin)
        self.assertEqual(announcement.status, Announcement.Status.PENDING)
        self.assertEqual(AnnouncementReviewLog.objects.filter(announcement=announcement, action="submitted").count(), 1)

    def test_a_different_communitys_admin_cannot_submit_for_this_community(self):
        with self.assertRaises(ValidationError):
            services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.other_admin)

    def test_platform_admin_can_approve_as_submitted(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="Original content", actor=self.bodi_admin)
        updated = services.approve_announcement(announcement=announcement, actor=self.platform_admin)
        self.assertEqual(updated.status, Announcement.Status.APPROVED)
        self.assertEqual(updated.content, "Original content")
        self.assertFalse(updated.was_edited_by_reviewer)

    def test_platform_admin_can_edit_the_content_while_approving(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="Original content", actor=self.bodi_admin)
        updated = services.approve_announcement(announcement=announcement, actor=self.platform_admin, edited_content="Corrected content")
        self.assertEqual(updated.status, Announcement.Status.APPROVED)
        self.assertEqual(updated.content, "Corrected content")
        self.assertTrue(updated.was_edited_by_reviewer)
        self.assertEqual(AnnouncementReviewLog.objects.filter(announcement=announcement, action="edited_and_approved").count(), 1)

    def test_a_community_admin_cannot_approve_their_own_announcement(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.bodi_admin)
        with self.assertRaises(ValidationError):
            services.approve_announcement(announcement=announcement, actor=self.bodi_admin)

    def test_rejecting_requires_a_reason(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.bodi_admin)
        with self.assertRaises(ValidationError):
            services.reject_announcement(announcement=announcement, actor=self.platform_admin, reason="   ")

    def test_rejecting_with_a_reason_works_and_is_logged(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.bodi_admin)
        updated = services.reject_announcement(announcement=announcement, actor=self.platform_admin, reason="Please add the exact time.")
        self.assertEqual(updated.status, Announcement.Status.REJECTED)
        self.assertEqual(updated.rejection_reason, "Please add the exact time.")
        log = AnnouncementReviewLog.objects.get(announcement=announcement, action="rejected")
        self.assertEqual(log.notes, "Please add the exact time.")

    def test_the_original_community_admin_can_resubmit_after_rejection(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.bodi_admin)
        services.reject_announcement(announcement=announcement, actor=self.platform_admin, reason="Add the time.")
        updated = services.resubmit_announcement(announcement=announcement, actor=self.bodi_admin, content="Meeting on Sunday at 3pm")
        self.assertEqual(updated.status, Announcement.Status.PENDING)
        self.assertEqual(updated.content, "Meeting on Sunday at 3pm")
        self.assertEqual(updated.rejection_reason, "")

    def test_cannot_resubmit_something_that_was_never_rejected(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.bodi_admin)
        with self.assertRaises(ValidationError):
            services.resubmit_announcement(announcement=announcement, actor=self.bodi_admin, content="Edited")

    def test_a_different_communitys_admin_cannot_resubmit_this_announcement(self):
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.bodi_admin)
        services.reject_announcement(announcement=announcement, actor=self.platform_admin, reason="Fix it.")
        with self.assertRaises(ValidationError):
            services.resubmit_announcement(announcement=announcement, actor=self.other_admin, content="Trying to hijack this")

    def test_full_review_log_survives_a_full_reject_then_resubmit_then_approve_cycle(self):
        """The complete audit trail — every step, in order, permanently."""
        announcement = services.submit_announcement(community=self.bodi, title="Meeting", content="Draft", actor=self.bodi_admin)
        services.reject_announcement(announcement=announcement, actor=self.platform_admin, reason="Needs more detail.")
        services.resubmit_announcement(announcement=announcement, actor=self.bodi_admin, content="Final version with detail")
        services.approve_announcement(announcement=announcement, actor=self.platform_admin)

        actions = list(announcement.review_log.values_list("action", flat=True))
        self.assertEqual(actions, ["submitted", "rejected", "resubmitted", "approved"])

    def test_notice_board_only_shows_approved_announcements_from_any_community(self):
        approved = services.submit_announcement(community=self.bodi, title="Approved One", content="x", actor=self.bodi_admin)
        services.approve_announcement(announcement=approved, actor=self.platform_admin)
        services.submit_announcement(community=self.bodi, title="Still Pending", content="x", actor=self.bodi_admin)
        other_approved = services.submit_announcement(community=self.other_community, title="From Another Community", content="x", actor=self.other_admin)
        services.approve_announcement(announcement=other_approved, actor=self.platform_admin)

        board = services.list_public_notice_board()
        titles = {a.title for a in board}
        self.assertEqual(titles, {"Approved One", "From Another Community"})

    def test_only_platform_admin_can_view_the_pending_review_queue(self):
        services.submit_announcement(community=self.bodi, title="Meeting", content="x", actor=self.bodi_admin)
        with self.assertRaises(ValidationError):
            services.list_pending_announcements_for_review(actor=self.bodi_admin)
        self.assertEqual(len(services.list_pending_announcements_for_review(actor=self.platform_admin)), 1)


class AnnouncementHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-announce-http")
        self.bodi_admin = User.objects.create_user(username="announce_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.platform_admin = User.objects.create_user(username="announce_http_platform", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_submit_reject_resubmit_approve_flow_via_http(self):
        admin_client = self._login("announce_http_admin")
        submit_res = admin_client.post(f"/api/tenants/communities/{self.bodi.id}/announcements/submit/", {
            "title": "Community Meeting", "content": "Join us Sunday",
        })
        self.assertEqual(submit_res.status_code, 201)
        announcement_id = submit_res.data["id"]

        platform_client = self._login("announce_http_platform")
        reject_res = platform_client.post(f"/api/tenants/announcements/{announcement_id}/reject/", {"reason": "Please add a time."})
        self.assertEqual(reject_res.status_code, 200)
        self.assertEqual(reject_res.data["status"], "rejected")

        resubmit_res = admin_client.post(f"/api/tenants/announcements/{announcement_id}/resubmit/", {"content": "Join us Sunday at 3pm"})
        self.assertEqual(resubmit_res.status_code, 200)
        self.assertEqual(resubmit_res.data["status"], "pending")

        approve_res = platform_client.post(f"/api/tenants/announcements/{announcement_id}/approve/", {})
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.data["status"], "approved")

        board_res = platform_client.get("/api/tenants/notice-board/")
        self.assertEqual(board_res.status_code, 200)
        self.assertEqual(len(board_res.data), 1)

    def test_notice_board_requires_login(self):
        client = APIClient()
        res = client.get("/api/tenants/notice-board/")
        self.assertEqual(res.status_code, 401)

    def test_a_community_admin_cannot_reach_the_pending_review_queue(self):
        client = self._login("announce_http_admin")
        res = client.get("/api/tenants/announcements/pending-review/")
        self.assertEqual(res.status_code, 403)


class HomepageFeatureRequestTests(TestCase):
    """'When it needs it on the homepage he has to send a request to the platform admin.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-homepage-feature")
        self.bodi_admin = User.objects.create_user(username="homepage_feature_bodi_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.platform_admin = User.objects.create_user(username="homepage_feature_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def test_a_community_admin_can_request_homepage_placement_when_submitting(self):
        announcement = services.submit_announcement(
            community=self.bodi, title="Big Event", content="x", actor=self.bodi_admin, homepage_feature_requested=True,
        )
        self.assertTrue(announcement.homepage_feature_requested)
        self.assertFalse(announcement.featured_on_homepage)  # not granted until approved

    def test_approving_grants_homepage_placement_by_default_when_it_was_requested(self):
        announcement = services.submit_announcement(
            community=self.bodi, title="Big Event", content="x", actor=self.bodi_admin, homepage_feature_requested=True,
        )
        updated = services.approve_announcement(announcement=announcement, actor=self.platform_admin)
        self.assertTrue(updated.featured_on_homepage)

    def test_the_platform_admin_can_override_and_decline_the_homepage_request(self):
        """The community admin requests it; the platform admin still has the final say."""
        announcement = services.submit_announcement(
            community=self.bodi, title="Big Event", content="x", actor=self.bodi_admin, homepage_feature_requested=True,
        )
        updated = services.approve_announcement(announcement=announcement, actor=self.platform_admin, feature_on_homepage=False)
        self.assertFalse(updated.featured_on_homepage)

    def test_no_homepage_request_means_no_homepage_placement_even_once_approved(self):
        announcement = services.submit_announcement(community=self.bodi, title="Ordinary Notice", content="x", actor=self.bodi_admin)
        updated = services.approve_announcement(announcement=announcement, actor=self.platform_admin)
        self.assertFalse(updated.featured_on_homepage)

    def test_the_public_homepage_feed_only_shows_featured_ones_not_every_approved_announcement(self):
        featured = services.submit_announcement(community=self.bodi, title="Featured", content="x", actor=self.bodi_admin, homepage_feature_requested=True)
        services.approve_announcement(announcement=featured, actor=self.platform_admin)

        not_featured = services.submit_announcement(community=self.bodi, title="Not Featured", content="x", actor=self.bodi_admin)
        services.approve_announcement(announcement=not_featured, actor=self.platform_admin)

        homepage_feed = services.list_homepage_featured_announcements()
        titles = {a.title for a in homepage_feed}
        self.assertEqual(titles, {"Featured"})

        # Still both show on the internal Notice Board regardless.
        notice_board = services.list_public_notice_board()
        self.assertEqual({a.title for a in notice_board}, {"Featured", "Not Featured"})

    def test_a_still_pending_announcement_never_appears_on_the_homepage_even_if_requested(self):
        services.submit_announcement(community=self.bodi, title="Still Pending", content="x", actor=self.bodi_admin, homepage_feature_requested=True)
        homepage_feed = services.list_homepage_featured_announcements()
        self.assertEqual(len(homepage_feed), 0)


class HomepageFeaturedAnnouncementsHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-homepage-http")
        self.bodi_admin = User.objects.create_user(username="homepage_http_bodi_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.platform_admin = User.objects.create_user(username="homepage_http_platform_admin", password="a-real-password-123", role=Role.PLATFORM_ADMIN)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_flow_via_http_requires_no_login_to_view_the_homepage_feed(self):
        admin_client = self._login("homepage_http_bodi_admin")
        submit_res = admin_client.post(f"/api/tenants/communities/{self.bodi.id}/announcements/submit/", {
            "title": "Big Event", "content": "Join us", "homepage_feature_requested": "true",
        })
        self.assertEqual(submit_res.status_code, 201)
        announcement_id = submit_res.data["id"]

        platform_client = self._login("homepage_http_platform_admin")
        approve_res = platform_client.post(f"/api/tenants/announcements/{announcement_id}/approve/", {})
        self.assertEqual(approve_res.status_code, 200)
        self.assertTrue(approve_res.data["featured_on_homepage"])

        public_client = APIClient()  # deliberately no credentials
        homepage_res = public_client.get("/api/tenants/notice-board/homepage-featured/")
        self.assertEqual(homepage_res.status_code, 200)
        self.assertEqual(len(homepage_res.data), 1)
        self.assertEqual(homepage_res.data[0]["title"], "Big Event")

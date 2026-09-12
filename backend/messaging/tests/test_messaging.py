from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from messaging import services
from messaging.models import Channel
from tenants.models import Community


class ChannelHierarchyTests(TestCase):
    """'Add message channel to all user types and should be a channel from top to down.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-messaging")
        self.other_community = Community.objects.create(name="Other Town", slug="other-messaging")
        self.platform_admin = User.objects.create_user(username="msg_platform_admin", password="x", role=Role.PLATFORM_ADMIN)
        self.community_admin = User.objects.create_user(username="msg_community_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_admin = User.objects.create_user(username="msg_other_admin", password="x", community=self.other_community, role=Role.COMMUNITY_ADMIN)
        self.member_user = User.objects.create_user(username="msg_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.community_admin)
        self.asona_member = member_services.register_member(community=self.bodi, full_name="Asona Member", gender="male", family=self.asona)
        self.asona_user = User.objects.create_user(username="msg_asona_user", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.asona_member, user=self.asona_user, actor=self.community_admin)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.community_admin)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Member", gender="female", family=self.bretuo)
        self.bretuo_user = User.objects.create_user(username="msg_bretuo_user", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.bretuo_member, user=self.bretuo_user, actor=self.community_admin)

    def test_a_platform_admin_can_access_the_platform_channel(self):
        channel = services.get_or_create_platform_channel()
        self.assertTrue(services.can_access_channel(user=self.platform_admin, channel=channel))

    def test_a_community_admin_of_any_community_can_access_the_platform_channel(self):
        """The one channel that deliberately crosses community boundaries — it's how the platform reaches every community's leadership."""
        channel = services.get_or_create_platform_channel()
        self.assertTrue(services.can_access_channel(user=self.community_admin, channel=channel))
        self.assertTrue(services.can_access_channel(user=self.other_admin, channel=channel))

    def test_an_ordinary_member_cannot_access_the_platform_channel(self):
        channel = services.get_or_create_platform_channel()
        self.assertFalse(services.can_access_channel(user=self.member_user, channel=channel))

    def test_any_member_of_a_community_can_access_that_communitys_channel(self):
        channel = services.get_or_create_community_channel(self.bodi)
        self.assertTrue(services.can_access_channel(user=self.community_admin, channel=channel))
        self.assertTrue(services.can_access_channel(user=self.member_user, channel=channel))
        self.assertTrue(services.can_access_channel(user=self.asona_user, channel=channel))

    def test_a_different_communitys_member_cannot_access_this_communitys_channel(self):
        channel = services.get_or_create_community_channel(self.bodi)
        self.assertFalse(services.can_access_channel(user=self.other_admin, channel=channel))

    def test_only_members_of_that_specific_family_can_access_its_family_channel(self):
        channel = services.get_or_create_family_channel(self.asona)
        self.assertTrue(services.can_access_channel(user=self.asona_user, channel=channel))
        self.assertFalse(services.can_access_channel(user=self.bretuo_user, channel=channel))

    def test_a_user_with_no_linked_member_profile_cannot_access_any_family_channel(self):
        channel = services.get_or_create_family_channel(self.asona)
        self.assertFalse(services.can_access_channel(user=self.member_user, channel=channel))

    def test_list_my_channels_gives_a_community_admin_both_platform_and_community_channels(self):
        channels = services.list_my_channels(user=self.community_admin)
        types = {c.channel_type for c in channels}
        self.assertEqual(types, {"platform", "community"})

    def test_list_my_channels_gives_a_family_member_both_community_and_family_channels(self):
        channels = services.list_my_channels(user=self.asona_user)
        types = {c.channel_type for c in channels}
        self.assertEqual(types, {"community", "family"})

    def test_list_my_channels_never_duplicates_the_platform_channel(self):
        """A Community Admin qualifies for the platform channel through two separate rules in list_my_channels — must still only appear once."""
        channels = services.list_my_channels(user=self.community_admin)
        platform_channels = [c for c in channels if c.channel_type == "platform"]
        self.assertEqual(len(platform_channels), 1)

    def test_posting_to_a_channel_you_do_not_belong_to_is_rejected(self):
        channel = services.get_or_create_family_channel(self.bretuo)
        with self.assertRaises(ValidationError):
            services.post_message(channel=channel, sender=self.asona_user, content="Sneaky message")

    def test_an_empty_message_is_rejected(self):
        channel = services.get_or_create_community_channel(self.bodi)
        with self.assertRaises(ValidationError):
            services.post_message(channel=channel, sender=self.community_admin, content="   ")

    def test_a_genuine_message_is_persisted_and_listed_in_order(self):
        channel = services.get_or_create_community_channel(self.bodi)
        services.post_message(channel=channel, sender=self.community_admin, content="First")
        services.post_message(channel=channel, sender=self.member_user, content="Second")
        messages = services.list_messages(channel=channel, actor=self.member_user)
        self.assertEqual([m.content for m in messages], ["First", "Second"])

    def test_cannot_list_messages_from_a_channel_you_do_not_belong_to(self):
        channel = services.get_or_create_community_channel(self.bodi)
        with self.assertRaises(ValidationError):
            services.list_messages(channel=channel, actor=self.other_admin)


class MessagingHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-messaging-http")
        self.community_admin = User.objects.create_user(username="msg_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.member_user = User.objects.create_user(username="msg_http_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_my_channels_endpoint_requires_login(self):
        client = APIClient()
        res = client.get("/api/messaging/channels/")
        self.assertEqual(res.status_code, 401)

    def test_full_post_and_read_round_trip_via_http(self):
        admin_client = self._login("msg_http_admin")
        channels_res = admin_client.get("/api/messaging/channels/")
        self.assertEqual(channels_res.status_code, 200)
        community_channel = next(c for c in channels_res.data if c["channel_type"] == "community")

        post_res = admin_client.post(f"/api/messaging/channels/{community_channel['id']}/messages/", {"content": "Welcome everyone"})
        self.assertEqual(post_res.status_code, 201)

        member_client = self._login("msg_http_member")
        messages_res = member_client.get(f"/api/messaging/channels/{community_channel['id']}/messages/")
        self.assertEqual(messages_res.status_code, 200)
        self.assertEqual(len(messages_res.data), 1)
        self.assertEqual(messages_res.data[0]["content"], "Welcome everyone")
        self.assertEqual(messages_res.data[0]["sender_username"], "msg_http_admin")

    def test_an_empty_message_returns_400_not_403(self):
        """A genuinely different problem than access denial — checked directly, not assumed."""
        client = self._login("msg_http_admin")
        channels_res = client.get("/api/messaging/channels/")
        community_channel = next(c for c in channels_res.data if c["channel_type"] == "community")
        res = client.post(f"/api/messaging/channels/{community_channel['id']}/messages/", {"content": ""})
        self.assertEqual(res.status_code, 400)

    def test_a_stranger_to_a_channel_gets_403_not_a_crash(self):
        other_community = Community.objects.create(name="Other Town", slug="other-messaging-http")
        outsider = User.objects.create_user(username="msg_http_outsider", password="a-real-password-123", community=other_community, role=Role.COMMUNITY_MEMBER)
        admin_client = self._login("msg_http_admin")
        channels_res = admin_client.get("/api/messaging/channels/")
        community_channel = next(c for c in channels_res.data if c["channel_type"] == "community")

        outsider_client = self._login("msg_http_outsider")
        res = outsider_client.get(f"/api/messaging/channels/{community_channel['id']}/messages/")
        self.assertEqual(res.status_code, 403)

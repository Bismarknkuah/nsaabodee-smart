from django.core import mail
from django.test import TestCase

from accounts.models import Role, User
from communication.models import DeliveryAttempt
from communication.services import deliver_notification, resolve_recipients
from families import services as family_services
from members import services as member_services
from notifications.models import Notification
from notifications.services import notify_family_head, notify_treasurers
from tenants.models import Community


class RecipientResolutionTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer1 = User.objects.create_user(username="t1", password="x", community=self.bodi, role=Role.TREASURER, email="t1@example.com")
        self.treasurer2 = User.objects.create_user(username="t2", password="x", community=self.bodi, role=Role.TREASURER)
        self.other_community = Community.objects.create(name="Other", slug="other")
        User.objects.create_user(username="t3", password="x", community=self.other_community, role=Role.TREASURER)

    def test_role_scoped_notification_resolves_to_every_matching_user_in_the_same_community_only(self):
        notification = Notification.objects.create(
            community=self.bodi, category=Notification.Category.DEFAULTER_ESCALATION,
            message="test", recipient_role=Role.TREASURER,
        )
        recipients = resolve_recipients(notification)
        usernames = {u.username for u in recipients}
        self.assertEqual(usernames, {"t1", "t2"})  # not t3, wrong community

    def test_user_scoped_notification_resolves_to_exactly_that_user(self):
        notification = Notification.objects.create(
            community=self.bodi, category=Notification.Category.DEFAULTER_ESCALATION,
            message="test", recipient_user=self.treasurer1,
        )
        recipients = resolve_recipients(notification)
        self.assertEqual(recipients, [self.treasurer1])


class DeliveryDispatchTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer_with_email = User.objects.create_user(
            username="t1", password="x", community=self.bodi, role=Role.TREASURER, email="t1@example.com"
        )
        self.treasurer_no_email = User.objects.create_user(username="t2", password="x", community=self.bodi, role=Role.TREASURER)

    def test_deliver_notification_creates_an_attempt_per_recipient_per_channel(self):
        notification = Notification.objects.create(
            community=self.bodi, category=Notification.Category.DEFAULTER_ESCALATION,
            message="Someone defaulted", recipient_role=Role.TREASURER,
        )
        attempts = deliver_notification(notification, channels=[DeliveryAttempt.Channel.CONSOLE, DeliveryAttempt.Channel.EMAIL])
        # 2 treasurers x 2 channels = 4 attempts
        self.assertEqual(len(attempts), 4)
        self.assertEqual(DeliveryAttempt.objects.filter(notification=notification).count(), 4)

    def test_email_actually_sent_for_user_with_an_address(self):
        notification = Notification.objects.create(
            community=self.bodi, category=Notification.Category.DEFAULTER_ESCALATION,
            message="Someone defaulted", recipient_user=self.treasurer_with_email,
        )
        deliver_notification(notification, channels=[DeliveryAttempt.Channel.EMAIL])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["t1@example.com"])

        attempt = DeliveryAttempt.objects.get(notification=notification, channel=DeliveryAttempt.Channel.EMAIL)
        self.assertEqual(attempt.status, DeliveryAttempt.Status.SENT)

    def test_no_address_is_recorded_not_silently_skipped(self):
        notification = Notification.objects.create(
            community=self.bodi, category=Notification.Category.DEFAULTER_ESCALATION,
            message="Someone defaulted", recipient_user=self.treasurer_no_email,
        )
        deliver_notification(notification, channels=[DeliveryAttempt.Channel.EMAIL])
        attempt = DeliveryAttempt.objects.get(notification=notification, channel=DeliveryAttempt.Channel.EMAIL)
        self.assertEqual(attempt.status, DeliveryAttempt.Status.SKIPPED_NO_ADDRESS)

    def test_sms_recorded_as_not_configured_rather_than_crashing(self):
        notification = Notification.objects.create(
            community=self.bodi, category=Notification.Category.DEFAULTER_ESCALATION,
            message="Someone defaulted", recipient_user=self.treasurer_with_email,
        )
        deliver_notification(notification, channels=[DeliveryAttempt.Channel.SMS])
        attempt = DeliveryAttempt.objects.filter(notification=notification, channel=DeliveryAttempt.Channel.SMS).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.status, DeliveryAttempt.Status.SKIPPED_NO_ADDRESS)  # no linked member, so no phone


class NotificationTriggerIntegrationTests(TestCase):
    """Confirms notifications.services actually triggers real delivery attempts end-to-end."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="treas", password="x", community=self.bodi, role=Role.TREASURER, email="treas@example.com")
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)

    def test_notify_treasurers_creates_delivery_attempts(self):
        notify_treasurers(community=self.bodi, member=self.member, message="Flagged as defaulter")
        notification = Notification.objects.filter(community=self.bodi, recipient_role=Role.TREASURER).first()
        self.assertIsNotNone(notification)
        self.assertTrue(DeliveryAttempt.objects.filter(notification=notification).exists())
        email_attempt = DeliveryAttempt.objects.get(notification=notification, channel=DeliveryAttempt.Channel.EMAIL)
        self.assertEqual(email_attempt.status, DeliveryAttempt.Status.SENT)

    def test_family_head_notification_targets_linked_user_when_available(self):
        head_member = member_services.register_member(community=self.bodi, full_name="Head Person", gender="male", family=self.asona)
        head_user = User.objects.create_user(username="head_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER, email="head@example.com")
        member_services.link_member_to_user(member=head_member, user=head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=head_member, actor=self.admin)

        notify_family_head(family=self.asona, member=self.member, message="Flagged as defaulter")

        notification = Notification.objects.filter(community=self.bodi, related_member=self.member).first()
        self.assertEqual(notification.recipient_user_id, head_user.id)
        self.assertEqual(notification.recipient_role, "")

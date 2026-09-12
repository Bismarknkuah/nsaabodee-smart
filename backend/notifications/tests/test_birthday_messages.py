from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from notifications import services as notification_services
from notifications.models import Notification
from tenants.models import Community


class BirthdayMessageTests(TestCase):
    """'When someone registered the system should wish them happy birthday messages on their birthday.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-birthday")
        self.admin = User.objects.create_user(username="birthday_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_a_member_whose_birthday_is_today_receives_a_message(self):
        member = member_services.register_member(
            community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona,
            date_of_birth=date(1990, 6, 15),
        )
        user = User.objects.create_user(username="kojo_bday", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)

        sent = notification_services.send_birthday_messages(on_date=date(2026, 6, 15))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].recipient_user_id, user.id)
        self.assertEqual(sent[0].category, Notification.Category.BIRTHDAY)
        self.assertIn("Kojo", sent[0].message)

    def test_the_birth_year_never_matters_only_month_and_day(self):
        """A 1965-born member's birthday still fires every year, regardless of what year 'today' actually is."""
        member = member_services.register_member(
            community=self.bodi, full_name="Ama Owusu", gender="female", family=self.asona,
            date_of_birth=date(1965, 3, 1),
        )
        user = User.objects.create_user(username="ama_bday", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)

        sent = notification_services.send_birthday_messages(on_date=date(2030, 3, 1))
        self.assertEqual(len(sent), 1)

    def test_a_member_with_no_linked_login_receives_nothing(self):
        """Most members never get a login at all — this is a genuine 'nothing to do', not an error."""
        member_services.register_member(
            community=self.bodi, full_name="No Login Person", gender="male", family=self.asona,
            date_of_birth=date(1990, 6, 15),
        )
        sent = notification_services.send_birthday_messages(on_date=date(2026, 6, 15))
        self.assertEqual(len(sent), 0)

    def test_a_member_with_no_date_of_birth_at_all_is_never_matched(self):
        member = member_services.register_member(community=self.bodi, full_name="No DOB Person", gender="male", family=self.asona)
        user = User.objects.create_user(username="no_dob_user", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)

        sent = notification_services.send_birthday_messages(on_date=date(2026, 6, 15))
        self.assertEqual(len(sent), 0)

    def test_someone_whose_birthday_is_a_different_day_is_not_matched(self):
        member = member_services.register_member(
            community=self.bodi, full_name="Different Day", gender="male", family=self.asona,
            date_of_birth=date(1990, 12, 25),
        )
        user = User.objects.create_user(username="different_day_user", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)

        sent = notification_services.send_birthday_messages(on_date=date(2026, 6, 15))
        self.assertEqual(len(sent), 0)

    def test_the_celery_task_itself_actually_runs_the_real_logic(self):
        """With CELERY_TASK_ALWAYS_EAGER=True (the test default), calling the task runs the real, synchronous logic."""
        member = member_services.register_member(
            community=self.bodi, full_name="Task Test Person", gender="female", family=self.asona,
            date_of_birth=date.today(),
        )
        user = User.objects.create_user(username="task_test_user", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)

        from notifications.tasks import send_birthday_messages_task
        send_birthday_messages_task()
        self.assertTrue(Notification.objects.filter(recipient_user=user, category=Notification.Category.BIRTHDAY).exists())

    def test_a_deactivated_member_does_not_receive_a_birthday_message(self):
        member = member_services.register_member(
            community=self.bodi, full_name="Inactive Person", gender="male", family=self.asona,
            date_of_birth=date(1990, 6, 15),
        )
        user = User.objects.create_user(username="inactive_bday_user", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=member, user=user, actor=self.admin)
        member.status = "inactive"
        member.save(update_fields=["status"])

        sent = notification_services.send_birthday_messages(on_date=date(2026, 6, 15))
        self.assertEqual(len(sent), 0)

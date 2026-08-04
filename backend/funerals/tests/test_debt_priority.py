from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from communication.models import DeliveryAttempt
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from members import services as member_services
from notifications.models import Notification
from tenants.models import Community


class DebtPriorityTests(TestCase):
    """
    'Members who owe or have debts have to pay before they can pay for
    new ones and old debts have to be credited to the family the person
    owes and the financial secretary and the family head have to be
    updated.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.fin_sec = User.objects.create_user(username="finsec", password="x", community=self.bodi, role=Role.FINANCIAL_SECRETARY, email="finsec@example.com")

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.asona_head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        self.asona_head_user = User.objects.create_user(username="asona_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD, email="asona_head@example.com")
        member_services.link_member_to_user(member=self.asona_head_member, user=self.asona_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.asona_head_member, actor=self.admin)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.bretuo)

        # The OLDER funeral: Asona family, started collecting first, never fully paid.
        self.older_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Older Asona Death", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-01-01", collection_start_date="2026-01-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        # The NEWER funeral: Bretuo family, started collecting later.
        self.newer_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Newer Bretuo Death", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-06-01", collection_start_date="2026-06-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

        self.older_obligation = ContributionObligation.objects.get(funeral_event=self.older_funeral, member=self.member)
        self.newer_obligation = ContributionObligation.objects.get(funeral_event=self.newer_funeral, member=self.member)

    def test_paying_toward_a_newer_obligation_is_blocked_while_an_older_one_is_unpaid(self):
        with self.assertRaises(ValidationError):
            funeral_services.record_payment(obligation=self.newer_obligation, amount=Decimal("3"), method="cash")
        # Nothing was recorded.
        self.newer_obligation.refresh_from_db()
        self.assertEqual(self.newer_obligation.amount_paid, Decimal("0"))

    def test_paying_the_older_debt_itself_is_never_blocked(self):
        payment = funeral_services.record_payment(obligation=self.older_obligation, amount=Decimal("5"), method="cash")
        self.assertIsNotNone(payment)

    def test_once_the_older_debt_is_fully_settled_the_newer_payment_goes_through(self):
        funeral_services.record_payment(obligation=self.older_obligation, amount=Decimal("50"), method="cash")
        payment = funeral_services.record_payment(obligation=self.newer_obligation, amount=Decimal("5"), method="cash")
        self.assertIsNotNone(payment)

    def test_a_partial_payment_on_the_older_debt_still_blocks_the_newer_one(self):
        funeral_services.record_payment(obligation=self.older_obligation, amount=Decimal("2"), method="cash")  # partial (owes 5 total)
        with self.assertRaises(ValidationError):
            funeral_services.record_payment(obligation=self.newer_obligation, amount=Decimal("5"), method="cash")

    def test_two_same_day_funerals_never_block_each_other(self):
        """Two families holding funerals the same day are concurrent, not older/newer — see the concurrent-ledgers feature."""
        same_day_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Same Day Death", deceased_gender="male",
            deceased_family=self.bretuo, date_of_death="2026-01-01", collection_start_date="2026-01-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        same_day_obligation = ContributionObligation.objects.get(funeral_event=same_day_funeral, member=self.member)
        # The original older_funeral (also 2026-01-01) must NOT block this same-day one.
        payment = funeral_services.record_payment(obligation=same_day_obligation, amount=Decimal("3"), method="cash")
        self.assertIsNotNone(payment)

    def test_blocking_notifies_the_financial_secretary_and_the_owed_familys_head(self):
        try:
            funeral_services.record_payment(obligation=self.newer_obligation, amount=Decimal("3"), method="cash")
        except ValidationError:
            pass

        fin_sec_notification = Notification.objects.filter(community=self.bodi, recipient_role=Role.FINANCIAL_SECRETARY, category="old_debt").first()
        self.assertIsNotNone(fin_sec_notification)

        head_notification = Notification.objects.filter(community=self.bodi, recipient_user=self.asona_head_user, category="old_debt").first()
        self.assertIsNotNone(head_notification)
        self.assertIn("Kojo", head_notification.message)

        # Real delivery was actually attempted (email, since both have addresses), not just the in-app row.
        self.assertTrue(DeliveryAttempt.objects.filter(notification=fin_sec_notification).exists())

    def test_settling_the_old_debt_notifies_both_that_it_is_now_clear(self):
        funeral_services.record_payment(obligation=self.older_obligation, amount=Decimal("50"), method="cash")

        settled_notification = Notification.objects.filter(
            community=self.bodi, recipient_user=self.asona_head_user, category="old_debt", message__icontains="settled"
        ).first()
        self.assertIsNotNone(settled_notification)

    def test_no_settlement_notification_when_there_was_never_a_newer_obligation_to_block(self):
        """An ordinary member with only ONE obligation paying it off immediately is not 'old debt' news to anyone."""
        isolated_community = Community.objects.create(
            name="Isolated", slug="isolated-debt-test",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        isolated_admin = User.objects.create_user(username="isolated_admin", password="x", community=isolated_community, role=Role.COMMUNITY_ADMIN)
        isolated_family = family_services.create_family(community=isolated_community, name="Solo Family", actor=isolated_admin)
        lone_member = member_services.register_member(community=isolated_community, full_name="Lone Payer", gender="male", family=isolated_family)
        only_funeral = funeral_services.create_funeral_event(
            community=isolated_community, deceased_name="Only Death", deceased_gender="male",
            deceased_family=isolated_family, date_of_death="2026-01-01", collection_start_date="2026-01-01",
            actor=isolated_admin, own_family_amount=Decimal("50"),
        )
        lone_obligation = ContributionObligation.objects.get(funeral_event=only_funeral, member=lone_member)
        funeral_services.record_payment(obligation=lone_obligation, amount=Decimal("50"), method="cash")

        self.assertFalse(
            Notification.objects.filter(community=isolated_community, category="old_debt", related_member=lone_member).exists()
        )

    def test_client_op_id_idempotent_replay_never_gets_blocked_by_the_new_rule(self):
        """A retried sync of an already-successful payment must never turn into a rejection just because ANOTHER debt exists by then."""
        op_id = "12345678-1234-5678-1234-567812345678"
        payment = funeral_services.record_payment(
            obligation=self.older_obligation, amount=Decimal("50"), method="cash", client_op_id=op_id
        )
        # Replaying the exact same client_op_id must return the same payment, not re-run the debt check.
        replayed = funeral_services.record_payment(
            obligation=self.older_obligation, amount=Decimal("50"), method="cash", client_op_id=op_id
        )
        self.assertEqual(payment.id, replayed.id)

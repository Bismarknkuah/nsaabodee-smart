from decimal import Decimal

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from nsaabodeeq.asgi import application
from tenants.models import Community

# Real WebSocket testing needs an actual channel layer behind it — the
# in-memory layer here is a genuine, fully-supported Channels backend
# (not a mock), just one that only works within a single test process
# rather than across real network hosts the way channels_redis does in
# production. This is the same kind of honest substitution as SQLite
# standing in for Postgres in quick local runs: a different real
# implementation of the same interface, not a stand-in that skips the
# behavior being tested.
IN_MEMORY_CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}


@override_settings(
    CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS,
    CELERY_TASK_ALWAYS_EAGER=True,
    ALLOWED_HOSTS=["testserver"],
)
class FuneralLedgerConsumerTests(TransactionTestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    async def test_connecting_and_receiving_a_broadcast_payment_event(self):
        communicator = WebsocketCommunicator(
            application, f"/ws/funerals/{self.funeral.id}/",
            headers=[(b"origin", b"http://testserver")],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        from channels.db import database_sync_to_async
        from funerals.models import ContributionObligation

        obligation = await database_sync_to_async(ContributionObligation.objects.get)(
            funeral_event=self.funeral, member=self.member
        )
        await database_sync_to_async(funeral_services.record_payment)(
            obligation=obligation, amount=Decimal("50"), method="cash", collector=self.admin
        )

        message = await communicator.receive_json_from(timeout=5)
        self.assertEqual(message["event"], "payment_recorded")
        self.assertEqual(message["member_name"], "Kojo")
        self.assertEqual(message["new_balance"], "0.00")
        self.assertEqual(message["payment_status"], "paid")

        await communicator.disconnect()

    async def test_two_different_funerals_are_isolated_channel_groups(self):
        """A client watching funeral A's ledger must never receive funeral B's payment events."""
        other_funeral = await self._create_second_funeral()

        from channels.db import database_sync_to_async
        from funerals.models import ContributionObligation

        # Settle funeral A's own obligation first — funeral A started
        # collecting before funeral B, and the debt-priority rule
        # (see funerals/tests/test_debt_priority.py) correctly refuses a
        # payment toward a newer funeral while an older one is still
        # owed. That rule isn't what this test is about; clearing it
        # first just gets to the actual scenario being tested.
        obligation_a = await database_sync_to_async(ContributionObligation.objects.get)(
            funeral_event=self.funeral, member=self.member
        )
        await database_sync_to_async(funeral_services.record_payment)(
            obligation=obligation_a, amount=obligation_a.expected_amount, method="cash"
        )

        communicator_a = WebsocketCommunicator(
            application, f"/ws/funerals/{self.funeral.id}/",
            headers=[(b"origin", b"http://testserver")],
        )
        await communicator_a.connect()

        obligation_b = await database_sync_to_async(ContributionObligation.objects.get)(
            funeral_event=other_funeral, member=self.member
        )
        await database_sync_to_async(funeral_services.record_payment)(
            obligation=obligation_b, amount=Decimal("5"), method="cash"
        )

        # Nothing should arrive on funeral A's socket for a payment made on funeral B.
        self.assertTrue(await communicator_a.receive_nothing(timeout=1))
        await communicator_a.disconnect()

    async def _create_second_funeral(self):
        from channels.db import database_sync_to_async
        bretuo = await database_sync_to_async(family_services.create_family)(
            community=self.bodi, name="Bretuo", actor=self.admin
        )
        await database_sync_to_async(family_services.recommend_family_rate)(
            family=bretuo, amount=Decimal("30"), actor=self.admin
        )
        await database_sync_to_async(family_services.approve_family_rate)(family=bretuo, actor=self.admin)
        return await database_sync_to_async(funeral_services.create_funeral_event)(
            community=self.bodi, deceased_name="Other Deceased", deceased_gender="female",
            deceased_family=bretuo, date_of_death="2026-07-02", collection_start_date="2026-07-02",
        )


class NotificationDeliveryTaskTests(TransactionTestCase):
    def test_deliver_notification_task_creates_delivery_attempts(self):
        from communication.models import DeliveryAttempt
        from communication.tasks import deliver_notification_task
        from notifications.models import Notification

        bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        treasurer = User.objects.create_user(username="treas", password="x", community=bodi, role=Role.TREASURER, email="t@example.com")
        notification = Notification.objects.create(
            community=bodi, category=Notification.Category.DEFAULTER_ESCALATION,
            message="test", recipient_user=treasurer,
        )

        deliver_notification_task(str(notification.id))  # called directly, not .delay(), to run inline for this test

        self.assertTrue(DeliveryAttempt.objects.filter(notification=notification).exists())

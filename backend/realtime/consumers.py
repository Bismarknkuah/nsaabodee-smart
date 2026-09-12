"""
One consumer, one concept: "live updates for a single funeral's ledger."
A client connects to /ws/funerals/{funeral_id}/, is added to that
funeral's own channel-layer group, and receives a message every time
funerals.services.record_payment() (or gifts/expenses/attendance,
should a future pass wire those in the same way) broadcasts to that
group — no polling, no manual refresh needed to see a payment another
collector just recorded.

Deliberately scoped per-funeral rather than one firehose-for-everything
channel: a community running four concurrent funerals means four
independent groups, matching the same "each funeral's ledger stays
isolated" principle the REST API and the web/mobile UIs already follow
(see funerals/models.py's docstring on why FuneralEvent has no
uniqueness constraint on concurrency).

No authentication is enforced at the WebSocket layer yet — see this
app's README section for why that's a flagged, real gap rather than an
oversight glossed over.
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class FuneralLedgerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.funeral_id = self.scope["url_route"]["kwargs"]["funeral_id"]
        self.group_name = f"funeral_{self.funeral_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ledger_event(self, event):
        """Handles messages of type 'ledger.event' sent via group_send — see realtime/broadcast.py."""
        await self.send(text_data=json.dumps(event["data"]))

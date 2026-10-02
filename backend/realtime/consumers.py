"""
One consumer, one concept: "live updates for a single funeral's ledger."
A client connects to /ws/funerals/{funeral_id}/?token=<access_token>, is
added to that funeral's own channel-layer group, and receives a message
every time funerals.services.record_payment() (or gifts/expenses/
attendance, should a future pass wire those in the same way) broadcasts
to that group. No polling, no manual refresh needed to see a payment
another collector just recorded.

Deliberately scoped per-funeral rather than one firehose-for-everything
channel: a community running four concurrent funerals means four
independent groups, matching the same "each funeral's ledger stays
isolated" principle the REST API and the web/mobile UIs already follow
(see funerals/models.py's docstring on why FuneralEvent has no
uniqueness constraint on concurrency).

Authenticated at connect time, not left open. A funeral's own memorial
page is deliberately public and its URL contains the funeral's id, so
without a real check here, anyone who ever viewed that public page
could connect to this same channel and see every payer's name and
amount live, with no login at all. The browser's own WebSocket API
cannot set a custom Authorization header, so the same JWT access token
already used for every REST request is instead passed as a query
parameter (?token=...) and validated by hand here using
rest_framework_simplejwt's own token classes, the same signature and
expiry check DRF's JWTAuthentication already performs, then the
connecting user's own community is checked against the funeral's,
exactly the same isolation the REST API already enforces. A connection
that fails either check is closed immediately, before ever joining the
group or receiving anything.
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class FuneralLedgerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.funeral_id = self.scope["url_route"]["kwargs"]["funeral_id"]
        user = await self._authenticate()
        if user is None:
            await self.close(code=4401)
            return
        authorized = await database_sync_to_async(self._is_authorized_for_funeral)(user, self.funeral_id)
        if not authorized:
            await self.close(code=4403)
            return

        self.group_name = f"funeral_{self.funeral_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ledger_event(self, event):
        """Handles messages of type 'ledger.event' sent via group_send — see realtime/broadcast.py."""
        await self.send(text_data=json.dumps(event["data"]))

    async def _authenticate(self):
        """Validates the ?token=... query parameter with the exact same JWT check DRF's own JWTAuthentication performs for every REST request. Returns the User, or None if the token is missing, malformed, or expired."""
        query_string = self.scope.get("query_string", b"").decode()
        params = dict(pair.split("=", 1) for pair in query_string.split("&") if "=" in pair)
        raw_token = params.get("token")
        if not raw_token:
            return None
        return await database_sync_to_async(self._validate_token)(raw_token)

    @staticmethod
    def _validate_token(raw_token):
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.tokens import AccessToken

        from accounts.authentication import CommunityAwareJWTAuthentication

        try:
            validated_token = AccessToken(raw_token)
            return CommunityAwareJWTAuthentication().get_user(validated_token)
        except TokenError:
            return None
        except Exception:
            return None

    @staticmethod
    def _is_authorized_for_funeral(user, funeral_id):
        """Same isolation the REST API already enforces: a Platform/Super Admin can see any community's funeral; anyone else only their own community's."""
        from funerals.models import FuneralEvent

        if user.is_superuser or user.role == "platform_admin":
            return True
        funeral = FuneralEvent.objects.filter(id=funeral_id).only("community_id").first()
        if funeral is None:
            return False
        return user.community_id == funeral.community_id

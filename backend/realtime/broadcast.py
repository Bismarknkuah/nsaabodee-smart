"""
The publish side of realtime/consumers.py. A plain function (not a
class) so any service function elsewhere in the codebase — funerals,
gifts, funeral_logistics — can call it after a real write succeeds,
the same lightweight way notifications.services._deliver() triggers a
Celery task. Never raises: a Redis hiccup or a channel layer being
unreachable should never take down the actual payment-recording request
that triggered it — this is a nice-to-have live update, not the source
of truth (the REST API/database always is).
"""

import logging

logger = logging.getLogger("realtime")


def broadcast_funeral_ledger_event(funeral_id: str, event_type: str, data: dict):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"funeral_{funeral_id}",
            {"type": "ledger.event", "data": {"event": event_type, **data}},
        )
    except Exception:
        logger.exception("Failed to broadcast realtime funeral ledger event (non-fatal)")

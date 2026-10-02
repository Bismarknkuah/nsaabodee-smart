"""
Notification delivery moved off the request/response cycle. Recording a
payment (or a defaulter escalation firing) should never make a
collector's phone wait on an SMS provider's round-trip before their
"payment recorded" confirmation shows up — that round-trip now happens
in a Celery worker process instead, out of band.

With CELERY_TASK_ALWAYS_EAGER=True (the default — see settings.py), this
still runs synchronously in-process, which is exactly why every existing
test that asserts a DeliveryAttempt exists immediately after calling
notify_treasurers()/notify_family_head() still passes unchanged: eager
mode IS real task execution, just without an actual queue in between.
Flip that setting off (and point CELERY_BROKER_URL at a real Redis — see
docker-compose.yml) to get genuine asynchronous, out-of-process delivery.
"""

from celery import shared_task


@shared_task
def deliver_notification_task(notification_id: str):
    from notifications.models import Notification
    from .services import deliver_notification

    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        return
    deliver_notification(notification)

"""
'When someone registered the system should wish them happy birthday
messages on their birthday.' Runs once daily via Celery Beat (see
CELERY_BEAT_SCHEDULE in settings.py) — same eager-mode-in-tests
reasoning as communication/tasks.py: with CELERY_TASK_ALWAYS_EAGER=True
(the default), calling this task still runs the real logic
synchronously, so tests calling it directly see real, immediate
results without a live broker.
"""

from celery import shared_task


@shared_task
def send_birthday_messages_task():
    from .services import send_birthday_messages

    send_birthday_messages()

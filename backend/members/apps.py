from django.apps import AppConfig


class MembersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "members"

    def ready(self):
        from django.db.models.signals import post_save
        from . import signals
        post_save.connect(signals.enroll_new_member_in_open_funerals, sender="members.Member")

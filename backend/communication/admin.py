from django.contrib import admin

from .models import DeliveryAttempt


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ("channel", "recipient_address", "status", "attempted_at")
    list_filter = ("channel", "status")

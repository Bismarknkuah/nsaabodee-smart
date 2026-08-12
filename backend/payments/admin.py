from django.contrib import admin

from .models import MomoPaymentRequest


@admin.register(MomoPaymentRequest)
class MomoPaymentRequestAdmin(admin.ModelAdmin):
    list_display = ("reference_id", "phone_number", "amount", "status", "created_at")
    list_filter = ("status",)

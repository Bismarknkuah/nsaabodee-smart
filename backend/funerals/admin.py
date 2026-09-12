from django.contrib import admin

from .models import ContributionObligation, ContributionPayment, FuneralEvent


@admin.register(FuneralEvent)
class FuneralEventAdmin(admin.ModelAdmin):
    list_display = ("deceased_name", "community", "deceased_family", "status", "collection_start_date")
    list_filter = ("status", "community")
    search_fields = ("deceased_name",)


@admin.register(ContributionObligation)
class ContributionObligationAdmin(admin.ModelAdmin):
    list_display = ("member", "funeral_event", "rate_type", "expected_amount", "amount_paid")
    list_filter = ("rate_type", "community")


@admin.register(ContributionPayment)
class ContributionPaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "obligation", "amount", "method", "paid_at")
    search_fields = ("receipt_number",)

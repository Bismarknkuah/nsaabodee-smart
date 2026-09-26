from django.contrib import admin

from .models import DonationAccountRegistration, GiftDonation


@admin.register(GiftDonation)
class GiftDonationAdmin(admin.ModelAdmin):
    list_display = ("donor_name", "recipient_family", "funeral_event", "donor_category", "amount_cash", "gift_item", "received_by_member", "given_at")
    search_fields = ("donor_name", "receipt_number")
    list_filter = ("community", "donor_category")


@admin.register(DonationAccountRegistration)
class DonationAccountRegistrationAdmin(admin.ModelAdmin):
    list_display = ("member", "funeral_event", "is_active", "registered_at")
    list_filter = ("is_active", "community")

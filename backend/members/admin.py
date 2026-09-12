from django.contrib import admin

from .models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "membership_number", "community", "family", "status", "defaulter_tier")
    list_filter = ("status", "defaulter_tier", "community")
    search_fields = ("full_name", "phone", "ghana_card_number", "membership_number")

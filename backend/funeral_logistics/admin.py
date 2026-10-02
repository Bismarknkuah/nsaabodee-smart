from django.contrib import admin

from .models import FuneralAttendance, FuneralExpense


@admin.register(FuneralExpense)
class FuneralExpenseAdmin(admin.ModelAdmin):
    list_display = ("description", "funeral_event", "category", "amount", "incurred_on")
    list_filter = ("category", "community")
    search_fields = ("description", "voucher_number")


@admin.register(FuneralAttendance)
class FuneralAttendanceAdmin(admin.ModelAdmin):
    list_display = ("__str__", "funeral_event", "attended_at")
    list_filter = ("community",)

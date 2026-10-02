from django.contrib import admin

from .models import Family, FamilyAuditLog


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "community", "status", "family_head", "member_count", "updated_at")
    list_filter = ("status", "community")
    search_fields = ("name", "community__name")


@admin.register(FamilyAuditLog)
class FamilyAuditLogAdmin(admin.ModelAdmin):
    list_display = ("family", "action", "actor", "created_at")
    list_filter = ("action", "community")
    readonly_fields = [f.name for f in FamilyAuditLog._meta.fields]

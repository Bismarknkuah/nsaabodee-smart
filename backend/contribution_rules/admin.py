from django.contrib import admin

from .models import DefaulterPolicy, GeneralRateChangeLog, MemberStatusRule

admin.site.register(GeneralRateChangeLog)
admin.site.register(MemberStatusRule)
admin.site.register(DefaulterPolicy)

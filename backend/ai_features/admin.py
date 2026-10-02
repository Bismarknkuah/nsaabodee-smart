from django.contrib import admin

from .models import MeetingSummary, SuspiciousTransactionFlag

admin.site.register(MeetingSummary)
admin.site.register(SuspiciousTransactionFlag)

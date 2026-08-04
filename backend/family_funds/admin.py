from django.contrib import admin

from .models import FamilyFund, FamilyFundContribution, FamilyFuneralExpense

admin.site.register(FamilyFund)
admin.site.register(FamilyFundContribution)
admin.site.register(FamilyFuneralExpense)

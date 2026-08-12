from django.urls import path

from .views import (
    ContributionRulesView,
    DefaulterThresholdsView,
    FamilyTierRatesView,
    GeneralRatesView,
    PreviewObligationsView,
    StatusExemptionView,
)

urlpatterns = [
    path("contribution-rules/", ContributionRulesView.as_view(), name="contribution-rules"),
    path("contribution-rules/general-rates/", GeneralRatesView.as_view(), name="contribution-rules-general"),
    path("contribution-rules/family-tier-rates/", FamilyTierRatesView.as_view(), name="contribution-rules-family-tiers"),
    path("contribution-rules/status-exemption/", StatusExemptionView.as_view(), name="contribution-rules-status"),
    path("contribution-rules/defaulter-thresholds/", DefaulterThresholdsView.as_view(), name="contribution-rules-defaulter"),
    path("contribution-rules/preview/", PreviewObligationsView.as_view(), name="contribution-rules-preview"),
]

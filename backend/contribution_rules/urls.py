from django.urls import path

from .views import (
    ContributionRulesView,
    DefaulterThresholdsView,
    FamilyPositionRatesView,
    FamilyTierRatesView,
    GeneralRatesView,
    MembersMissingBirthDateView,
    MembersNeedingAgeReviewView,
    PreviewObligationsView,
    StatusExemptionView,
    TownElderPerTitleRatesView,
    TownElderRateView,
)

urlpatterns = [
    path("contribution-rules/", ContributionRulesView.as_view(), name="contribution-rules"),
    path("contribution-rules/general-rates/", GeneralRatesView.as_view(), name="contribution-rules-general"),
    path("contribution-rules/family-tier-rates/", FamilyTierRatesView.as_view(), name="contribution-rules-family-tiers"),
    path("contribution-rules/town-elder-rate/", TownElderRateView.as_view(), name="contribution-rules-town-elder"),
    path("contribution-rules/town-elder-per-title-rates/", TownElderPerTitleRatesView.as_view(), name="contribution-rules-town-elder-per-title"),
    path("contribution-rules/family-position-rates/", FamilyPositionRatesView.as_view(), name="contribution-rules-family-position"),
    path("contribution-rules/status-exemption/", StatusExemptionView.as_view(), name="contribution-rules-status"),
    path("contribution-rules/defaulter-thresholds/", DefaulterThresholdsView.as_view(), name="contribution-rules-defaulter"),
    path("contribution-rules/preview/", PreviewObligationsView.as_view(), name="contribution-rules-preview"),
    path("contribution-rules/members-needing-age-review/", MembersNeedingAgeReviewView.as_view(), name="contribution-rules-age-review"),
    path("contribution-rules/members-missing-birth-date/", MembersMissingBirthDateView.as_view(), name="contribution-rules-missing-dob"),
]

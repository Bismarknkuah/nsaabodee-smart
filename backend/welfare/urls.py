from django.urls import path

from .views import (
    ApproveFamilyCampaignByCommunityAdminView,
    CampaignListView,
    CampaignObligationsView,
    CommunityWideCampaignInitiateView,
    ContributionCategoryListCreateView,
    DecideFamilyCampaignView,
    FamilyCampaignInitiateView,
    PendingCommunityAdminWelfareApprovalsView,
    RecordWelfarePaymentView,
)

urlpatterns = [
    path("welfare/categories/", ContributionCategoryListCreateView.as_view(), name="welfare-categories"),
    path("welfare/campaigns/", CampaignListView.as_view(), name="welfare-campaigns"),
    path("welfare/campaigns/community-wide/", CommunityWideCampaignInitiateView.as_view(), name="welfare-campaign-initiate-community"),
    path("welfare/families/<uuid:family_id>/campaigns/", FamilyCampaignInitiateView.as_view(), name="welfare-campaign-initiate-family"),
    path("welfare/campaigns/<uuid:campaign_id>/decide/", DecideFamilyCampaignView.as_view(), name="welfare-campaign-decide"),
    path("welfare/campaigns/pending-admin-approval/", PendingCommunityAdminWelfareApprovalsView.as_view(), name="welfare-campaign-pending-admin-approval"),
    path("welfare/campaigns/<uuid:campaign_id>/admin-approve/", ApproveFamilyCampaignByCommunityAdminView.as_view(), name="welfare-campaign-admin-approve"),
    path("welfare/campaigns/<uuid:campaign_id>/obligations/", CampaignObligationsView.as_view(), name="welfare-campaign-obligations"),
    path("welfare/obligations/<uuid:obligation_id>/record-payment/", RecordWelfarePaymentView.as_view(), name="welfare-obligation-record-payment"),
]

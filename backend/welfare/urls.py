from django.urls import path

from .views import (
    AcknowledgeWelfareDisbursementView,
    ApproveFamilyCampaignByCommunityAdminView,
    CampaignListView,
    CampaignObligationsView,
    CommunityWideCampaignInitiateView,
    ContributionCategoryListCreateView,
    DecideFamilyCampaignView,
    DecideWelfareRequestView,
    DisburseWelfareRequestView,
    FamilyCampaignInitiateView,
    ListWelfareRequestsView,
    PendingCommunityAdminWelfareApprovalsView,
    RecordVoluntaryContributionView,
    RecordWelfarePaymentView,
    SetCampaignTargetMembersView,
    SubmitWelfareRequestView,
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
    path("welfare/campaigns/<uuid:campaign_id>/target-members/", SetCampaignTargetMembersView.as_view(), name="welfare-campaign-target-members"),
    path("welfare/campaigns/<uuid:campaign_id>/contribute/", RecordVoluntaryContributionView.as_view(), name="welfare-campaign-contribute"),
    path("welfare/obligations/<uuid:obligation_id>/record-payment/", RecordWelfarePaymentView.as_view(), name="welfare-obligation-record-payment"),
    path("welfare/campaigns/<uuid:campaign_id>/requests/", SubmitWelfareRequestView.as_view(), name="welfare-request-submit"),
    path("welfare/campaigns/<uuid:campaign_id>/requests/list/", ListWelfareRequestsView.as_view(), name="welfare-request-list"),
    path("welfare/requests/<uuid:request_id>/decide/", DecideWelfareRequestView.as_view(), name="welfare-request-decide"),
    path("welfare/requests/<uuid:request_id>/disburse/", DisburseWelfareRequestView.as_view(), name="welfare-request-disburse"),
    path("welfare/requests/<uuid:request_id>/acknowledge/", AcknowledgeWelfareDisbursementView.as_view(), name="welfare-request-acknowledge"),
]

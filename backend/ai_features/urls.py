from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import (
    AskChatbotView,
    ChatbotHistoryView,
    DraftTributeView,
    FuzzySearchView,
    InactiveMembersView,
    MeetingSummaryView,
    PredictCollectionsView,
    SuspiciousTransactionFlagViewSet,
)

router = DefaultRouter()
router.register("suspicious-transactions", SuspiciousTransactionFlagViewSet, basename="suspicious-transaction")

urlpatterns = [
    path("ai/funerals/<uuid:funeral_id>/predict-collections/", PredictCollectionsView.as_view(), name="ai-predict-collections"),
    path("ai/funerals/<uuid:funeral_id>/draft-tribute/", DraftTributeView.as_view(), name="ai-draft-tribute"),
    path("ai/inactive-members/", InactiveMembersView.as_view(), name="ai-inactive-members"),
    path("ai/search/", FuzzySearchView.as_view(), name="ai-fuzzy-search"),
    path("ai/meeting-summary/", MeetingSummaryView.as_view(), name="ai-meeting-summary"),
    path("ai/chatbot/", AskChatbotView.as_view(), name="ai-chatbot-ask"),
    path("ai/chatbot/history/", ChatbotHistoryView.as_view(), name="ai-chatbot-history"),
    path("", include(router.urls)),
]

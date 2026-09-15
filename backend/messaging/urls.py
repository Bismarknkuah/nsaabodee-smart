from django.urls import path

from .views import ChannelMessagesView, MyChannelsView

urlpatterns = [
    path("messaging/channels/", MyChannelsView.as_view(), name="messaging-my-channels"),
    path("messaging/channels/<uuid:channel_id>/messages/", ChannelMessagesView.as_view(), name="messaging-channel-messages"),
]

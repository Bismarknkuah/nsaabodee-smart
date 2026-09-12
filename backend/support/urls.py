from django.urls import path

from .views import AllTicketsView, MyTicketsView, TicketMessagesView, UpdateTicketStatusView

urlpatterns = [
    path("support/tickets/", MyTicketsView.as_view(), name="support-my-tickets"),
    path("support/tickets/all/", AllTicketsView.as_view(), name="support-all-tickets"),
    path("support/tickets/<uuid:ticket_id>/status/", UpdateTicketStatusView.as_view(), name="support-ticket-status"),
    path("support/tickets/<uuid:ticket_id>/messages/", TicketMessagesView.as_view(), name="support-ticket-messages"),
]

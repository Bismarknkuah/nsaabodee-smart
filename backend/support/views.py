from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers as drf_serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import SupportTicket
from .serializers import SupportTicketMessageSerializer, SupportTicketSerializer


class SubmitTicketSerializer(drf_serializers.Serializer):
    subject = drf_serializers.CharField()
    description = drf_serializers.CharField()
    priority = drf_serializers.ChoiceField(choices=SupportTicket.Priority.choices, required=False, default=SupportTicket.Priority.MEDIUM)


class PostTicketMessageSerializer(drf_serializers.Serializer):
    content = drf_serializers.CharField()


class MyTicketsView(APIView):
    """'Handle support tickets' — any signed-in user, any role, can raise one and see their own."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = services.list_my_tickets(user=request.user)
        return Response(SupportTicketSerializer(tickets, many=True).data)

    def post(self, request):
        serializer = SubmitTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ticket = services.submit_ticket(submitted_by=request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class AllTicketsView(APIView):
    """
    'Only the community and temporary support should be moved or
    reported to the platform admin, all other members or executives
    support should be reported to their community admin.' The same
    endpoint serves two entirely separate queues depending on who's
    asking — see support.services.list_all_tickets.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tickets = services.list_all_tickets(actor=request.user, status=request.query_params.get("status") or None)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(SupportTicketSerializer(tickets, many=True).data)


class UpdateTicketStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        new_status = request.data.get("status", "")
        try:
            updated = services.update_ticket_status(ticket=ticket, status=new_status, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(SupportTicketSerializer(updated).data)


class TicketMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        try:
            messages = services.list_ticket_messages(ticket=ticket, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(SupportTicketMessageSerializer(messages, many=True).data)

    def post(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        serializer = PostTicketMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = services.post_ticket_message(ticket=ticket, sender=request.user, content=serializer.validated_data["content"])
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(SupportTicketMessageSerializer(message).data, status=status.HTTP_201_CREATED)

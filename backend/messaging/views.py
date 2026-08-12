from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers as drf_serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Channel
from .serializers import ChannelMessageSerializer, ChannelSerializer


class PostChannelMessageSerializer(drf_serializers.Serializer):
    content = drf_serializers.CharField()


class MyChannelsView(APIView):
    """'Add message channel to all user types.' Every channel this specific person actually belongs to — computed fresh each time, never stored."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from tenants.services import is_feature_enabled
        if not is_feature_enabled("messaging"):
            return Response([])
        channels = services.list_my_channels(user=request.user)
        return Response(ChannelSerializer(channels, many=True).data)


class ChannelMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        from tenants.services import is_feature_enabled
        if not is_feature_enabled("messaging"):
            return Response({"detail": "Messaging has been temporarily disabled by a platform administrator."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        channel = get_object_or_404(Channel, id=channel_id)
        try:
            messages = services.list_messages(channel=channel, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(ChannelMessageSerializer(messages, many=True).data)

    def post(self, request, channel_id):
        from tenants.services import is_feature_enabled
        if not is_feature_enabled("messaging"):
            return Response({"detail": "Messaging has been temporarily disabled by a platform administrator."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        channel = get_object_or_404(Channel, id=channel_id)
        serializer = PostChannelMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # a genuinely empty/missing "content" is a 400, not an access question
        try:
            message = services.post_message(channel=channel, sender=request.user, content=serializer.validated_data["content"])
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(ChannelMessageSerializer(message).data, status=status.HTTP_201_CREATED)

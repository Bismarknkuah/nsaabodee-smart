from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/funerals/(?P<funeral_id>[0-9a-f-]+)/$", consumers.FuneralLedgerConsumer.as_asgi()),
]

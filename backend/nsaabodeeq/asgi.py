"""
ASGI config for nsaabodeeq project — wraps the plain Django ASGI app
(handles ordinary HTTP requests exactly as before) with Channels'
ProtocolTypeRouter, which adds a second protocol (websocket) routed to
realtime/routing.py's consumer. HTTP requests are completely unaffected;
this is purely additive.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nsaabodeeq.settings')

django_asgi_app = get_asgi_application()

from realtime.routing import websocket_urlpatterns  # noqa: E402  (must import after get_asgi_application())

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)),
})

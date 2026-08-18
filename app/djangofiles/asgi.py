import json
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangofiles.settings")

asgi_application = get_asgi_application()

from django.conf import settings  # noqa: E402
from django.template.defaultfilters import filesizeformat  # noqa: E402
from home import routing  # noqa: E402


class BodySizeLimit:
    """
    Reject requests whose declared Content-Length exceeds UPLOAD_MAX_SIZE
    before Django's ASGIHandler spools the body to disk. Auth, pub_load, and
    quota checks all run in the view — after the full body has been received
    — so without this gate any client that reaches the app could stream
    gigabytes into the container's temp dir. nginx enforces the same limit at
    the edge; this covers deployments fronted by other proxies and returns
    JSON the upload UI can display.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            content_length = dict(scope.get("headers") or []).get(b"content-length", b"")
            if content_length.isdigit() and int(content_length) > settings.UPLOAD_MAX_SIZE:
                message = f"Upload Failed: Maximum upload size is {filesizeformat(settings.UPLOAD_MAX_SIZE)}."
                body = json.dumps({"error": True, "message": message}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


application = ProtocolTypeRouter(
    {
        "http": BodySizeLimit(asgi_application),
        "websocket": AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns)),
    }
)

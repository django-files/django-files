from django.urls import path

from .consumers import HomeConsumer


websocket_urlpatterns = [
    path('ws/home/', HomeConsumer.as_asgi()),
]

from django.urls import re_path
from .consumers import LiveEventsConsumer

websocket_urlpatterns = [re_path(r"^ws/events/$", LiveEventsConsumer.as_asgi())]

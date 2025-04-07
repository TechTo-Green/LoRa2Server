from django.urls import path
from .views import start_bluetooth_listener, stop_bluetooth_listener, index

urlpatterns = [
    path('start/', start_bluetooth_listener),
    path('stop/', stop_bluetooth_listener),

    path('', index),  # Default route to start the listener
]

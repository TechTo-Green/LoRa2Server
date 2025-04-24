from django.urls import path
from .views import start_bluetooth_listener, stop_bluetooth_listener, index, get_available_ports, test_port

urlpatterns = [
    path('start/', start_bluetooth_listener, name='start_bluetooth'),
    path('stop/', stop_bluetooth_listener, name='stop_bluetooth'),
    path('ports/', get_available_ports, name='get_ports'),
    path('test-port/', test_port, name='test_port'),
    path('', index, name='bluetooth_index'),
]

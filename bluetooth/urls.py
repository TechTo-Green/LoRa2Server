from django.urls import path
from . import views

urlpatterns = [
    path('get-latest-data/', views.get_latest_data, name='get_latest_data'),
    path('start/', views.start_bluetooth_listener, name='start_bluetooth'),
    path('stop/', views.stop_bluetooth_listener, name='stop_bluetooth'),
    path('ports/', views.get_available_ports, name='get_ports'),
    path('test-port/', views.test_port, name='test_port'),
    path('', views.index, name='bluetooth_index'),
]

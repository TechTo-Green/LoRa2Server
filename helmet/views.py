import json
import serial
import serial.tools.list_ports
import requests
from django.http import JsonResponse
from django.shortcuts import render



from utils.wait_for_usb import wait_for_usb




def set_port(request):
    global SERIAL_PORT
    SERIAL_PORT = wait_for_usb()
    return JsonResponse({'serial_port': SERIAL_PORT})


def index(request):
    return render(request, 'lora/index.html')


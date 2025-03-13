import json
import threading
import requests
import serial
from django.http import JsonResponse
from django.shortcuts import render

from lora.models import AppConfig  # Ensure this model is correctly implemented
from utils.wait_for_usb import wait_for_usb  # Ensure this utility works as intended
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings


def get_installed_apps(request):
    user_apps = [app for app in settings.INSTALLED_APPS if ".apps." in app]
    return JsonResponse({"apps": user_apps})


@csrf_exempt
def set_port(request):
    SERIAL_PORT = wait_for_usb()
    print(f"Detected USB port: {SERIAL_PORT}")  # Debugging print statement
    config = AppConfig.get_config()
    config.serial_port = SERIAL_PORT
    config.save()
    return JsonResponse({'port': SERIAL_PORT})


def index(request):
    config = AppConfig.get_config()
    return render(request, 'index.html', {
        'EXP_KEYS': config.exp_keys,
        'HOST': config.host,
        'BAUD_RATE': config.baud_rate
    })


@csrf_exempt
def update_config(request):
    if request.method == "POST":
        print(f"Received request body: {request.body}")  # Debugging print statement
        try:
            config = AppConfig.get_config()
            data = json.loads(request.body)
            print(f"Current host: {config.host}")  # Debugging print statement
            if 'EXP_KEYS' in data:
                config.exp_keys = data['EXP_KEYS']
                print(f"Updated EXP_KEYS: {config.exp_keys}")  # Debugging print statement
            if 'HOST' in data:
                config.host = data['HOST']
                print(f"Updated HOST: {config.host}")  # Debugging print statement
            if 'BAUD_RATE' in data:
                config.baud_rate = int(data['BAUD_RATE'])
                print(f"Updated BAUD_RATE: {config.baud_rate}")  # Debugging print statement

            config.save()
            return JsonResponse({"message": "Configuration updated successfully"})

        except Exception as e:
            print(f"Error updating configuration: {str(e)}")  # Debugging print statement
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)


def start(request):
    config = AppConfig.get_config()

    # Check if all required configurations are set
    if not all([config.exp_keys, config.host, config.baud_rate, config.serial_port]):
        print("Configuration is incomplete.")  # Debugging print statement
        return JsonResponse({'error': 'Configuration not complete'}, status=400)

    def serial_worker():
        print("Serial worker thread started.")  # Debugging print statement
        try:
            with serial.Serial(config.serial_port, config.baud_rate, timeout=1) as ser:
                while True:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        print(f"Received line from serial port: {line}")  # Debugging print statement
                        try:
                            data = json.loads(line)
                            print(f"Parsed JSON data: {data}")  # Debugging print statement
                            print(list(key for key in config.exp_keys), data)
                            # Check if all expected keys are present in the data
                            if all(key in data for key in config.exp_keys):
                                try:
                                    response = requests.post(
                                        f"{config.host}/lora/data/",
                                        json=data,
                                        headers={'Content-Type': 'application/json'}
                                    )
                                    print(f"Data sent to {config.host}, Response status: {response.status_code}")
                                except requests.RequestException as e:
                                    print(f"Request error: {str(e)}")

                        except json.JSONDecodeError as e:
                            print(f"JSON decoding error: {str(e)}")  # Debugging print statement

                        except KeyError as e:
                            print(f"Missing key error: {str(e)}")  # Debugging print statement

        except serial.SerialException as e:
            print(f"Serial error: {str(e)}")  # Debugging print statement

    # Start the thread and confirm it started successfully
    thread = threading.Thread(target=serial_worker, daemon=True)
    thread.start()
    print("Serial worker thread has been started.")  # Debugging print statement

    return JsonResponse({'status': 'Serial communication started'}, status=200)

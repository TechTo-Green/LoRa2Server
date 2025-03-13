import json
import os

import requests
import serial
from django.http import JsonResponse
from django.shortcuts import render
from django.core.cache import cache

from utils.wait_for_usb import wait_for_usb
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging

LOG_FILE_PATH = getattr(settings, 'LOG_FILE_PATH', os.path.join(os.path.dirname(__file__), 'django.log'))

# Set up logging (write both to console and file)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE_PATH)
    ]
)


def get_installed_apps(request):
    user_apps = [app for app in settings.INSTALLED_APPS if ".apps." in app]
    return JsonResponse({"apps": user_apps})


@csrf_exempt
def set_port(request):
    SERIAL_PORT = wait_for_usb()
    cache.set('serial_port', SERIAL_PORT)  # Store the port in cache
    logging.info(f"Serial port set to: {SERIAL_PORT}")
    return JsonResponse({'port': SERIAL_PORT})


def index(request):
    return render(request, 'index.html')


@csrf_exempt
def update_config(request):
    """
    Update configurations dynamically and store them in cache.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Update configurations in cache
            if 'EXP_KEYS' in data:
                cache.set('EXP_KEYS', data['EXP_KEYS'])
            if 'HOST' in data:
                cache.set('HOST', data['HOST'])
            if 'BAUD_RATE' in data:
                cache.set('BAUD_RATE', int(data['BAUD_RATE']))  # Ensure BAUD_RATE is an integer

            # Recalculate API_URL based on HOST
            HOST = cache.get('HOST')
            API_URL = f"{HOST}/lora/data/"
            cache.set('API_URL', API_URL)

            return JsonResponse({"message": "Configuration updated successfully"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)


def start():
    """
    Start listening to the serial port and send received JSON data to an API endpoint.
    """
    # Fetch configurations from settings.py
    EXP_KEYS = cache.get('EXP_KEYS')  # ['temp', 'lat', 'lon', 'alt', 'heading']
    HOST = cache.get('HOST')  # "http://localhost:8000"
    API_URL = f"{HOST}/lora/data/"
    BAUD_RATE = cache.get('BAUD_RATE')  # 115200

    SERIAL_PORT = cache.get('serial_port')
    if not SERIAL_PORT:
        logging.error("Serial port not set. Please set the port before starting.")
        return

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        logging.info(f"Listening on {SERIAL_PORT} at {BAUD_RATE} baud...")

        while True:
            try:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    logging.info(f"Received data: {line}")
                    try:
                        data = json.loads(line)
                        if all(key in data for key in EXP_KEYS):
                            logging.info(f"Valid data received: {data}")
                            try:
                                response = requests.post(
                                    API_URL,
                                    json=data,
                                    headers={'Content-Type': 'application/json'}
                                )
                                response.raise_for_status()
                                logging.info(f"Data successfully sent to API. Response: {response.text}")
                            except requests.RequestException as http_err:
                                logging.error(f"HTTP error occurred while sending data: {http_err}")
                        else:
                            logging.warning(f"Data missing required fields: {data}")
                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON received: {line}")
            except Exception as e:
                logging.error(f"Error reading from serial port: {e}")

    except serial.SerialException as ser_err:
        logging.error(f"Serial error: {ser_err}")
    except KeyboardInterrupt:
        logging.info("Program terminated by user.")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            logging.info("Serial port closed.")


def fetch_logs(request):
    try:
        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, 'r') as log_file:
                logs = log_file.readlines()[-50:]  # Fetch last 50 lines of logs
            return JsonResponse({"logs": logs}, json_dumps_params={'indent': 2}, safe=False)
        else:
            return JsonResponse({"error": "Log file not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

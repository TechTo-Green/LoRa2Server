import serial
import re
import requests
import json
import socket
import time
import threading
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import sys
import os

# Set UTF-8 encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')
os.system("")  # Enable ANSI escape sequences in Windows CMD

BLUETOOTH_PORT = "COM8"
BAUD_RATE = 115200

# Get local machine IP (for localhost replacement)
LOCAL_IP = socket.gethostbyname(socket.gethostname())
API_ENDPOINT = f"http://{LOCAL_IP}:8000/lora/data/"

# Define the required fields
FIELDS = ['altitude', 'latitude', 'longitude', 'speed']

# Global flag for stopping the thread
running = False


def parse_data(line):
    """ Extract relevant data from different possible formats. """

    # Default dictionary with 0 for missing fields
    parsed_data = {field: 0 for field in FIELDS}

    # Format 1: Lat, Lon, Alt, Speed
    pattern1 = r"Lat:([-0-9.]+),Lon:([-0-9.]+),Alt:([-0-9.]+),Speed:([-0-9.]+)"
    match1 = re.search(pattern1, line)

    if match1:
        parsed_data["latitude"] = float(match1.group(1))
        parsed_data["longitude"] = float(match1.group(2))
        parsed_data["altitude"] = float(match1.group(3))
        parsed_data["speed"] = float(match1.group(4))
        return parsed_data  # ✅ Successfully parsed

    # Format 2: GPS, Alt, Yaw, Temp (Fallback format)
    pattern2 = r"GPS:\s([-0-9.]+),\s([-0-9.]+)\sAlt:\s([-0-9.]+)m\s\|\sYaw:\s([-0-9.]+)°\s\|\sTemp:\s([-0-9.]+)C"
    match2 = re.search(pattern2, line)

    if match2:
        parsed_data["latitude"] = float(match2.group(1))
        parsed_data["longitude"] = float(match2.group(2))
        parsed_data["altitude"] = float(match2.group(3))
        parsed_data["speed"] = 0  # No speed in this format
        return parsed_data  # ✅ Successfully parsed

    return None  # ❌ Neither format matched


"""
def send_to_api(data):
    # Send parsed JSON data to the API endpoint, with retries on failure. 
    headers = {"Content-Type": "application/json"}
    max_retries = 3  # Retry up to 3 times if the request fails

    for attempt in range(max_retries):
        try:
            response = requests.post(API_ENDPOINT, data=json.dumps(data), headers=headers, timeout=5)

            if response.status_code in [200, 201]:  # Accept both 200 and 201 as success
                print(f"✅ Data sent successfully: {response.json()}")
                return
            else:
                print(f"⚠️ Unexpected response. Status: {response.status_code}, Response: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"❌ API Request Error (Attempt {attempt + 1}/{max_retries}): {e}")

        time.sleep(2)  # Wait before retrying

    print("🚨 API request failed after multiple attempts.")
"""

SUPABASE_URL = "https://jkqwwyxskvyqlobbnlog.supabase.co"
SUPABASE_TABLE = "bv_rover_location"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImprcXd3eXhza3Z5cWxvYmJubG9nIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQwMDQ5ODYsImV4cCI6MjA1OTU4MDk4Nn0.-2OFeV7_msHoecBMRE879dp8VcJSbPgur1-BBGzVdH0"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def send_to_api(data):
    max_retries = 3  # Retry up to 3 times if the request fails

    for attempt in range(max_retries):
        try:
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
                headers=SUPABASE_HEADERS,
                data=json.dumps(data),
                timeout=5
            )

            if res.status_code in [200, 201]:  # Accept both 200 and 201 as success
                print(f"✅ Data sent successfully: {res.json()}")
                return
            else:
                print(f"⚠️ Unexpected res. Status: {res.status_code}, Response: {res.text}")

        except requests.exceptions.RequestException as e:
            print(f"❌ API Request Error (Attempt {attempt + 1}/{max_retries}): {e}")

        time.sleep(2)  # Wait before retrying

    print("🚨 API request failed after multiple attempts.")


def connect_bluetooth():
    """ Establish a Bluetooth connection and retry if it fails. """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 Connecting to {BLUETOOTH_PORT} at {BAUD_RATE} baud (Attempt {attempt + 1}/{max_retries})...")
            return serial.Serial(BLUETOOTH_PORT, BAUD_RATE, timeout=1)
        except serial.SerialException as e:
            print(f"❌ Bluetooth Connection Error: {e}")

        time.sleep(2)  # Wait before retrying

    print("🚨 Failed to establish Bluetooth connection after multiple attempts.")
    return None


def bluetooth_listener():
    """ Background process that reads from Bluetooth and sends data. """
    global running

    esp_bt = connect_bluetooth()

    if esp_bt:
        try:
            print(f"✅ Connected. Listening on {BLUETOOTH_PORT}...")
            last_send_time = 0
            latest_data = None

            while running:  # Keep running while the flag is True
                try:
                    if esp_bt.in_waiting:
                        raw_data = esp_bt.readline().decode(errors='replace').strip()
                        parsed = parse_data(raw_data)

                        if parsed:
                            latest_data = parsed
                            print(f"📊 New data received: {raw_data}")
                        else:
                            print(f"⚠️ Unrecognized format: {raw_data}")

                    # Send data every 2 seconds if we have valid data
                    current_time = time.time()
                    if latest_data and (current_time - last_send_time) >= 2:
                        print(f"🕒 Sending data (2-second interval)")
                        send_to_api(latest_data)
                        last_send_time = current_time

                    # Small delay to prevent CPU hogging
                    time.sleep(0.1)

                except UnicodeDecodeError:
                    print("⚠️ Decoding error: Received corrupt data.")
                except serial.SerialException:
                    print("❌ Bluetooth connection lost! Reconnecting...")
                    esp_bt = connect_bluetooth()
                    if not esp_bt:
                        break  # Exit if unable to reconnect

        except KeyboardInterrupt:
            print("🛑 Stopping script gracefully.")

        finally:
            if esp_bt and esp_bt.is_open:
                esp_bt.close()
                print("🔌 Serial port closed.")

    print("🚨 Bluetooth listener stopped.")


@csrf_exempt
def start_bluetooth_listener(request):
    """ API endpoint to start Bluetooth listener. """
    global running

    if running:
        return JsonResponse({"status": "already running"}, status=400)

    running = True
    thread = threading.Thread(target=bluetooth_listener, daemon=True)
    thread.start()

    return JsonResponse({"status": "started"})


def stop_bluetooth_listener(request):
    """ API endpoint to stop Bluetooth listener. """
    global running

    if not running:
        return JsonResponse({"status": "not running"}, status=400)

    running = False
    return JsonResponse({"status": "stopped"})


def index(request):
    """ API endpoint to check if the server is running. """
    return render(request, 'bluetooth/index.html')

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
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import serial.tools.list_ports

# Set UTF-8 encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')
os.system("")  # Enable ANSI escape sequences in Windows CMD

# Configuration
BLUETOOTH_PORT = "COM8"
BAUD_RATE = 115200
MAX_RETRIES = 3
RETRY_DELAY = 2
SEND_INTERVAL = 2  # seconds

# Supabase Configuration
SUPABASE_URL = "https://jkqwwyxskvyqlobbnlog.supabase.co"
SUPABASE_TABLE = "bv_rover_location"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImprcXd3eXhza3Z5cWxvYmJubG9nIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQwMDQ5ODYsImV4cCI6MjA1OTU4MDk4Nn0.-2OFeV7_msHoecBMRE879dp8VcJSbPgur1-BBGzVdH0"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

@dataclass
class BluetoothData:
    latitude: float
    longitude: float
    altitude: float
    speed: float
    timestamp: datetime

@dataclass
class PortInfo:
    device: str
    description: str
    hwid: str
    is_connected: bool = False
    is_transmitting: bool = False

class BluetoothManager:
    def __init__(self):
        self.running = False
        self.thread = None
        self.connection = None
        self.lock = threading.Lock()
        self.last_data: Optional[BluetoothData] = None
        self.last_send_time = 0
        self.current_port = None
        self.testing_port = False

    def get_available_ports(self) -> List[PortInfo]:
        """Get list of available serial ports with their details."""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append(PortInfo(
                device=port.device,
                description=port.description or "Unknown",
                hwid=port.hwid or "Unknown",
                is_connected=port.device == self.current_port if self.current_port else False
            ))
        return ports

    def test_port(self, port_name: str) -> Dict[str, Any]:
        """Test if a port is transmitting any data."""
        self.testing_port = True
        result = {
            "success": False,
            "message": "",
            "data": None,
            "raw_data": None,
            "port_info": {
                "device": port_name,
                "description": "",
                "hwid": ""
            }
        }

        try:
            # Get port info
            for port in serial.tools.list_ports.comports():
                if port.device == port_name:
                    result["port_info"]["description"] = port.description or "Unknown"
                    result["port_info"]["hwid"] = port.hwid or "Unknown"
                    break

            with serial.Serial(port_name, BAUD_RATE, timeout=1) as test_connection:
                # Wait for data for 2 seconds
                start_time = time.time()
                while time.time() - start_time < 2:
                    if test_connection.in_waiting:
                        raw_data = test_connection.readline().decode(errors='replace').strip()
                        if raw_data:  # If we got any data at all
                            result["success"] = True
                            result["message"] = "Port is transmitting data"
                            result["raw_data"] = raw_data
                            
                            # Try to parse the data, but don't fail if it's invalid
                            try:
                                parsed_data = self.parse_data(raw_data)
                                if parsed_data:
                                    # Extract additional data if available
                                    temp_match = re.search(r"Temp:([-0-9.]+)C", raw_data)
                                    yaw_match = re.search(r"yaw:([-0-9.]+)", raw_data)
                                    
                                    result["data"] = {
                                        "latitude": parsed_data.latitude,
                                        "longitude": parsed_data.longitude,
                                        "temperature": float(temp_match.group(1)) if temp_match else None,
                                        "yaw": float(yaw_match.group(1)) if yaw_match else None
                                    }
                            except Exception as e:
                                print(f"⚠️ Parsing error: {e}")
                            break
                    time.sleep(0.1)
                
                if not result["success"]:
                    result["message"] = "No data received"
        except serial.SerialException as e:
            result["message"] = f"Connection error: {str(e)}"
        except Exception as e:
            result["message"] = f"Error: {str(e)}"
        finally:
            self.testing_port = False
            return result

    def connect(self) -> Optional[serial.Serial]:
        """Establish Bluetooth connection with retries."""
        for attempt in range(MAX_RETRIES):
            try:
                print(f"🔄 Connecting to {BLUETOOTH_PORT} (Attempt {attempt + 1}/{MAX_RETRIES})...")
                return serial.Serial(BLUETOOTH_PORT, BAUD_RATE, timeout=1)
            except serial.SerialException as e:
                print(f"❌ Connection Error: {e}")
                time.sleep(RETRY_DELAY)
        return None

    def parse_data(self, line: str) -> Optional[BluetoothData]:
        """Parse incoming data with validation."""
        try:
            # Format 1: Lat, Lon, Alt, Speed
            pattern1 = r"Lat:([-0-9.]+),Lon:([-0-9.]+),Alt:([-0-9.]+),Speed:([-0-9.]+)"
            match1 = re.search(pattern1, line)
            
            if match1:
                return BluetoothData(
                    latitude=float(match1.group(1)),
                    longitude=float(match1.group(2)),
                    altitude=float(match1.group(3)),
                    speed=float(match1.group(4)),
                    timestamp=datetime.now()
                )

            # Format 2: GPS, Alt, Yaw, Temp
            pattern2 = r"GPS:\s([-0-9.]+),\s([-0-9.]+)\sAlt:\s([-0-9.]+)m"
            match2 = re.search(pattern2, line)
            
            if match2:
                return BluetoothData(
                    latitude=float(match2.group(1)),
                    longitude=float(match2.group(2)),
                    altitude=float(match2.group(3)),
                    speed=0.0,
                    timestamp=datetime.now()
                )

            # Format 3: Lat:22.5726,Lng:88.3639,4,Temp:28.39C,yaw:337.41,1,0,1,0
            pattern3 = r"Lat:([-0-9.]+),Lng:([-0-9.]+).*?Temp:([-0-9.]+)C.*?yaw:([-0-9.]+)"
            match3 = re.search(pattern3, line)
            
            if match3:
                return BluetoothData(
                    latitude=float(match3.group(1)),
                    longitude=float(match3.group(2)),
                    altitude=0.0,  # Not provided in this format
                    speed=0.0,     # Not provided in this format
                    timestamp=datetime.now()
                )

            # Format 4: Alternative format with different separators
            pattern4 = r"Lat:([-0-9.]+)\s*,\s*Lng:([-0-9.]+)\s*,\s*Temp:([-0-9.]+)C\s*,\s*Yaw:([-0-9.]+)"
            match4 = re.search(pattern4, line)
            
            if match4:
                return BluetoothData(
                    latitude=float(match4.group(1)),
                    longitude=float(match4.group(2)),
                    altitude=0.0,  # Not provided in this format
                    speed=0.0,     # Not provided in this format
                    timestamp=datetime.now()
                )

            return None
        except (ValueError, AttributeError) as e:
            print(f"⚠️ Parsing error: {e}")
            return None

    def send_to_api(self, data: BluetoothData) -> bool:
        """Send data to Supabase with retries."""
        payload = {
            "latitude": data.latitude,
            "longitude": data.longitude,
            "altitude": data.altitude,
            "speed": data.speed,
            "timestamp": data.timestamp.isoformat()
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
                    headers=SUPABASE_HEADERS,
                    json=payload,
                    timeout=5
                )

                if response.status_code in [200, 201]:
                    print(f"✅ Data sent successfully")
                    return True
                else:
                    print(f"⚠️ API Error: {response.status_code} - {response.text}")

            except requests.exceptions.RequestException as e:
                print(f"❌ API Error (Attempt {attempt + 1}/{MAX_RETRIES}): {e}")

            time.sleep(RETRY_DELAY)

        return False

    def listener(self):
        """Main Bluetooth listener loop."""
        while self.running:
            try:
                if not self.connection or not self.connection.is_open:
                    self.connection = self.connect()
                    if not self.connection:
                        time.sleep(RETRY_DELAY)
                        continue

                if self.connection.in_waiting:
                    raw_data = self.connection.readline().decode(errors='replace').strip()
                    parsed_data = self.parse_data(raw_data)

                    if parsed_data:
                        with self.lock:
                            self.last_data = parsed_data
                            print(f"📊 New data: {raw_data}")

                # Send data at regular intervals
                current_time = time.time()
                if self.last_data and (current_time - self.last_send_time) >= SEND_INTERVAL:
                    if self.send_to_api(self.last_data):
                        self.last_send_time = current_time

                time.sleep(0.1)

            except (serial.SerialException, UnicodeDecodeError) as e:
                print(f"❌ Connection error: {e}")
                if self.connection:
                    self.connection.close()
                self.connection = None
                time.sleep(RETRY_DELAY)

    def start(self):
        """Start the Bluetooth listener thread."""
        if self.running:
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self.listener, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        """Stop the Bluetooth listener thread."""
        if not self.running:
            return False
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.connection and self.connection.is_open:
            self.connection.close()
        return True

# Global Bluetooth manager instance
bluetooth_manager = BluetoothManager()

@csrf_exempt
def start_bluetooth_listener(request):
    """API endpoint to start Bluetooth listener."""
    if bluetooth_manager.start():
        return JsonResponse({"status": "started", "message": "Bluetooth listener started successfully"})
    return JsonResponse({"status": "error", "message": "Bluetooth listener is already running"}, status=400)

@csrf_exempt
def stop_bluetooth_listener(request):
    """API endpoint to stop Bluetooth listener."""
    if bluetooth_manager.stop():
        return JsonResponse({"status": "stopped", "message": "Bluetooth listener stopped successfully"})
    return JsonResponse({"status": "error", "message": "Bluetooth listener is not running"}, status=400)

@csrf_exempt
def get_available_ports(request):
    """API endpoint to get list of available ports."""
    ports = bluetooth_manager.get_available_ports()
    return JsonResponse({
        "ports": [{
            "device": port.device,
            "description": port.description,
            "hwid": port.hwid,
            "is_connected": port.is_connected
        } for port in ports]
    })

@csrf_exempt
def test_port(request):
    """API endpoint to test a specific port."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        port_name = data.get('port')
        if not port_name:
            return JsonResponse({"error": "Port name is required"}, status=400)
        
        result = bluetooth_manager.test_port(port_name)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def index(request):
    """Render the Bluetooth control interface."""
    return render(request, 'bluetooth/index.html')

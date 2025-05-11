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
BLUETOOTH_PORT = "COM3"
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
    bearing: Optional[float] = None
    temperature: Optional[float] = None
    distance1: Optional[float] = None
    distance2: Optional[float] = None
    distance3: Optional[float] = None
    satellite_count: Optional[int] = None
    timestamp: datetime = datetime.now()
    raw_data: Optional[str] = None

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
        self.data_history: List[BluetoothData] = []
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
                                    bearing_match = re.search(r"bearing:([-0-9.]+)", raw_data)
                                    
                                    result["data"] = {
                                        "latitude": parsed_data.latitude,
                                        "longitude": parsed_data.longitude,
                                        "temperature": float(temp_match.group(1)) if temp_match else None,
                                        "bearing": float(bearing_match.group(1)) if bearing_match else None
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
                print(f"🔄 Connecting to {self.current_port} (Attempt {attempt + 1}/{MAX_RETRIES})...")
                return serial.Serial(self.current_port, BAUD_RATE, timeout=1)
            except serial.SerialException as e:
                print(f"❌ Connection Error: {e}")
                time.sleep(RETRY_DELAY)
        return None

    def parse_data(self, raw_data: str) -> Optional[BluetoothData]:
        """Parse the incoming data into a structured format."""
        try:
            print(f"📝 Raw data received: {raw_data}")
            # Remove 'Sent: ' prefix if present
            data = raw_data.replace('Sent: ', '')
            print(f"📝 Cleaned data: {data}")
            
            # Try different patterns to match the data format
            patterns = [
                # Format: Lat:22.5726,Lng:88.3639,4,Temp:28.39C,yaw:337.41,1,0,1,0
                r"Lat:([-0-9.]+),Lng:([-0-9.]+),([0-9.]+),Temp:([-0-9.]+)C,yaw:([-0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+)",
                # Format 2: GPS:22.5726,88.3639 Alt:100m
                r"GPS:\s*([-0-9.]+),\s*([-0-9.]+)\s*Alt:\s*([-0-9.]+)m",
                # Format 3: Lat, Lon, Alt, Speed
                r"Lat:([-0-9.]+),Lon:([-0-9.]+),Alt:([-0-9.]+),Speed:([-0-9.]+)"
            ]
            
            for i, pattern in enumerate(patterns):
                print(f"🔍 Trying pattern {i+1}: {pattern}")
                match = re.search(pattern, data)
                if match:
                    print(f"✅ Pattern {i+1} matched!")
                    print(f"📊 Match groups: {match.groups()}")
                    groups = match.groups()
                    if len(groups) >= 4:
                        # Extract values based on the matched pattern
                        if i == 0:  # Main format
                            parsed_data = BluetoothData(
                                latitude=float(groups[0]),
                                longitude=float(groups[1]),
                                altitude=float(groups[2]),
                                speed=None,  # yaw value is actually speed
                                temperature=float(groups[3]),
                                bearing=float(groups[4]),  # No bearing in this format
                                distance1=float(groups[5]),
                                distance2=float(groups[6]),
                                distance3=float(groups[7]),
                                satellite_count=int(groups[8]),
                                raw_data=raw_data
                            )
                        else:
                            parsed_data = BluetoothData(
                                latitude=float(groups[0]),
                                longitude=float(groups[1]),
                                altitude=float(groups[2]),
                                speed=float(groups[3]) if len(groups) > 3 else 0.0,
                                temperature=None,
                                bearing=None,
                                distance1=None,
                                distance2=None,
                                distance3=None,
                                satellite_count=None,
                                raw_data=raw_data
                            )
                        print(f"📊 Parsed data: {parsed_data}")
                        return parsed_data
                else:
                    print(f"❌ Pattern {i+1} did not match")
            
            print("⚠️ No patterns matched the data")
            return None
        except Exception as e:
            print(f"❌ Parsing error: {e}")
            import traceback
            print(f"📝 Error details: {traceback.format_exc()}")
            return None

    def send_to_api(self, data: BluetoothData) -> bool:
        """Send data to Supabase with retries."""
        payload = {
            "latitude": data.latitude,
            "longitude": data.longitude,
            "altitude": data.altitude,
            "speed": data.speed,
            "bearing": data.bearing,
            "temperature": data.temperature,
            "distance1": data.distance1,
            "distance2": data.distance2,
            "distance3": data.distance3,
            "satellite_count": data.satellite_count,
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
        print("🎧 Starting Bluetooth listener loop")
        while self.running:
            try:
                if not self.connection or not self.connection.is_open:
                    print("🔌 Connection not open, attempting to connect...")
                    self.connection = self.connect()
                    if not self.connection:
                        print("❌ Failed to connect, retrying...")
                        time.sleep(RETRY_DELAY)
                        continue
                    print("✅ Connection established")

                if self.connection.in_waiting:
                    print("📥 Data available, reading...")
                    raw_data = self.connection.readline().decode(errors='replace').strip()
                    print(f"📝 Raw data received: {raw_data}")
                    
                    parsed_data = self.parse_data(raw_data)
                    print(f"📊 Parsed data result: {parsed_data}")

                    if parsed_data:
                        with self.lock:
                            print("🔒 Acquired lock, updating data...")
                            self.last_data = parsed_data
                            self.data_history.append(parsed_data)
                            # Keep only last 100 data points
                            if len(self.data_history) > 100:
                                self.data_history.pop(0)
                            print(f"📊 Data updated. History size: {len(self.data_history)}")

                # Send data at regular intervals
                current_time = time.time()
                if self.last_data and (current_time - self.last_send_time) >= SEND_INTERVAL:
                    print("⏰ Time to send data to API...")
                    if self.send_to_api(self.last_data):
                        self.last_send_time = current_time
                        print("✅ Data sent to API successfully")
                    else:
                        print("❌ Failed to send data to API")

                time.sleep(0.1)

            except (serial.SerialException, UnicodeDecodeError) as e:
                print(f"❌ Connection error: {e}")
                if self.connection:
                    self.connection.close()
                self.connection = None
                time.sleep(RETRY_DELAY)

    def start(self, port_name: str) -> bool:
        """Start the Bluetooth listener thread."""
        if self.running:
            return False
        
        self.current_port = port_name
        self.running = True
        self.thread = threading.Thread(target=self.listener, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> bool:
        """Stop the Bluetooth listener thread."""
        if not self.running:
            return False
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.connection and self.connection.is_open:
            self.connection.close()
        return True

    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """Get the latest data point."""
        print("🔍 Getting latest data...")
        with self.lock:
            if self.last_data:
                print(f"📊 Latest data available: {self.last_data}")
                return {
                    "latitude": self.last_data.latitude,
                    "longitude": self.last_data.longitude,
                    "altitude": self.last_data.altitude,
                    "speed": self.last_data.speed,
                    "bearing": self.last_data.bearing,
                    "temperature": self.last_data.temperature,
                    "distance1": self.last_data.distance1,
                    "distance2": self.last_data.distance2,
                    "distance3": self.last_data.distance3,
                    "satellite_count": self.last_data.satellite_count,
                    "timestamp": self.last_data.timestamp.isoformat(),
                    "raw_data": self.last_data.raw_data
                }
            print("⚠️ No latest data available")
            return None

# Global Bluetooth manager instance
bluetooth_manager = BluetoothManager()

@csrf_exempt
def start_bluetooth_listener(request):
    """API endpoint to start Bluetooth listener."""
    print("🔍 start_bluetooth_listener view called")
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        port_name = data.get('port')
        print(f"📡 Starting Bluetooth listener on port: {port_name}")
        if not port_name:
            return JsonResponse({"error": "Port name is required"}, status=400)
        
        if bluetooth_manager.start(port_name):
            print("✅ Bluetooth listener started successfully")
            return JsonResponse({"status": "started", "message": "Bluetooth listener started successfully"})
        print("⚠️ Bluetooth listener is already running")
        return JsonResponse({"status": "error", "message": "Bluetooth listener is already running"}, status=400)
    except json.JSONDecodeError:
        print("❌ Invalid JSON in request")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        print(f"❌ Error starting Bluetooth listener: {e}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def stop_bluetooth_listener(request):
    """API endpoint to stop Bluetooth listener."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    if bluetooth_manager.stop():
        return JsonResponse({"status": "stopped", "message": "Bluetooth listener stopped successfully"})
    return JsonResponse({"status": "error", "message": "Bluetooth listener is not running"}, status=400)

@csrf_exempt
def get_latest_data(request):
    """API endpoint to get the latest data point."""
    print("🔍 get_latest_data view called")
    if request.method != 'GET':
        print("❌ Invalid request method")
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    data = bluetooth_manager.get_latest_data()
    print(f"📊 Latest data from manager: {data}")
    if data:
        print("✅ Returning data to client")
        return JsonResponse({"status": "success", "data": data})
    print("⚠️ No data available to return")
    return JsonResponse({"status": "error", "message": "No data available"}, status=404)

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

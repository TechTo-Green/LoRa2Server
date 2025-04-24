import serial
import time
import sys
from datetime import datetime
import json

def parse_data(raw_data):
    """Parse the incoming data into a structured format."""
    try:
        # Remove 'Sent: ' prefix if present
        data = raw_data.replace('Sent: ', '')
        
        # Split the data into parts
        parts = data.split(',')
        
        # Extract values
        lat = float(parts[0].split(':')[1])
        lng = float(parts[1].split(':')[1])
        temp = float(parts[3].split(':')[1].replace('C', ''))
        yaw = float(parts[4].split(':')[1])
        
        # Create structured data
        parsed = {
            'timestamp': datetime.now().isoformat(),
            'latitude': lat,
            'longitude': lng,
            'temperature': temp,
            'yaw': yaw,
            'raw': raw_data
        }
        
        return parsed
    except Exception as e:
        print(f"⚠️ Parsing error: {e}")
        return None

def test_bluetooth(port='COM12', baud_rate=115200):
    print(f"🔍 Testing Bluetooth connection on {port} at {baud_rate} baud...")
    
    try:
        # Initialize serial connection
        ser = serial.Serial(port, baud_rate, timeout=1)
        print(f"✅ Connected to {port}")
        
        # Data collection
        data_points = []
        start_time = time.time()
        
        # Main loop
        while True:
            try:
                # Check if there's data to read
                if ser.in_waiting:
                    # Read and decode the data
                    raw_data = ser.readline().decode(errors='replace').strip()
                    print(f"\n📥 Received: {raw_data}")
                    
                    # Parse the data
                    parsed = parse_data(raw_data)
                    if parsed:
                        data_points.append(parsed)
                        print("\n📊 Parsed Data:")
                        print(f"  Latitude: {parsed['latitude']}")
                        print(f"  Longitude: {parsed['longitude']}")
                        print(f"  Temperature: {parsed['temperature']}°C")
                        print(f"  Yaw: {parsed['yaw']}°")
                
                # Small delay to prevent CPU hogging
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                print("\n🛑 Stopping script...")
                break
                
            except Exception as e:
                print(f"⚠️ Error: {e}")
                time.sleep(1)  # Wait before retrying
                
    except serial.SerialException as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    finally:
        # Clean up
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("🔌 Serial port closed")
        
        # Save collected data
        if data_points:
            filename = f"bluetooth_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(data_points, f, indent=2)
            print(f"\n💾 Data saved to {filename}")
            
            # Print summary
            duration = time.time() - start_time
            print(f"\n📈 Summary:")
            print(f"  Total data points: {len(data_points)}")
            print(f"  Duration: {duration:.2f} seconds")
            print(f"  Average rate: {len(data_points)/duration:.2f} points/second")

if __name__ == "__main__":
    # Get port from command line argument or use default
    port = sys.argv[1] if len(sys.argv) > 1 else 'COM12'
    test_bluetooth(port) 
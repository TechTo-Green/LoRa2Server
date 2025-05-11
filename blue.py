import serial
import time

for port in ['COM12', 'COM6']:
    try:
        print(f"\nTrying {port}...")
        ser = serial.Serial(port, 115200, timeout=2)
        time.sleep(2)  # wait for any data
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"Received from {port}: {line}")
        else:
            print(f"No data from {port}")
        ser.close()
    except Exception as e:
        print(f"Failed to read from {port}: {e}")

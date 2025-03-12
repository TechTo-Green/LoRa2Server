import json
import serial
import serial.tools.list_ports
import requests
from utils.wait_for_usb import wait_for_usb

EXP_KEYS = ['temp', 'lat', 'lon', 'alt', 'heading']
API_URL = "http://localhost:8000/api/data/"
SERIAL_PORT = wait_for_usb()
BAUD_RATE = 115200


def main():
    # Wait until a new USB device (ESP8266) is attached

    try:
        # Initialize the serial connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Listening on {SERIAL_PORT} at {BAUD_RATE} baud...")

        while True:
            # Read a line from the serial port
            try:
                line = ser.readline().decode('utf-8').strip()
            except Exception as e:
                print(f"Error reading from serial port: {e}")
                continue

            if line:
                try:
                    # Parse the JSON data from the serial line
                    data = json.loads(line)
                    # Verify expected data structure
                    expected_keys = EXP_KEYS
                    if all(key in data for key in expected_keys):
                        print("Received valid data:", data)
                        # Send the JSON data as a POST request
                        try:
                            response = requests.post(
                                API_URL,
                                json=data,
                                headers={'Content-Type': 'application/json'}
                            )
                            response.raise_for_status()
                            print("Data successfully sent to the API. Response:", response.text)
                        except requests.RequestException as http_err:
                            print(f"HTTP error occurred: {http_err}")
                    else:
                        print("Received data missing required fields:", data)
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {line}")
    except serial.SerialException as ser_err:
        print(f"Serial error: {ser_err}")
    except KeyboardInterrupt:
        print("Program terminated by user.")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial port closed.")


if __name__ == "__main__":
    main()

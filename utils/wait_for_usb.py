import time

import serial
from serial.tools import list_ports



def wait_for_usb():
    """
    Waits for a new USB device (serial port) to be attached.
    Returns the device name of the new serial port.
    """
    print("Scanning for available serial ports...")
    initial_ports = {port.device for port in serial.tools.list_ports.comports()}
    print("Initial ports:", initial_ports)
    print("Waiting for a new USB device to be attached...")

    while True:
        current_ports = {port.device for port in serial.tools.list_ports.comports()}
        new_ports = current_ports - initial_ports
        print(new_ports, current_ports)
        if new_ports:
            serial_port = new_ports.pop()
            print(f"New USB device detected: {serial_port}")
            return serial_port
        time.sleep(1)

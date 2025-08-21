# utils.py
# This file contains utility and helper functions for the BACnet Tools GUI.

import os
import sys
import socket
import psutil # Added for network interface names

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller bundled data. """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # In development, use the script's directory
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_persistent_data_path(relative_path):
    """ Get absolute path for persistent user data, works for dev and for PyInstaller. """
    try:
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle, get the executable's directory.
            base_path = os.path.dirname(sys.executable)
        else:
            # In development, use the script's directory.
            base_path = os.path.abspath(".")
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_network_interfaces():
    """
    Gets a list of non-loopback IPv4 network interfaces with their names.
    """
    interfaces = []
    try:
        addrs = psutil.net_if_addrs()
        for name, addresses in addrs.items():
            for addr in addresses:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    interfaces.append(f"{name} ({addr.address})")
    except Exception:
        pass  # Silently fail if interfaces can't be determined
    return interfaces
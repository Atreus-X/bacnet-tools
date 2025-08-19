# config.py
# This file contains the static configuration data for the BACnet Tools GUI.

# --- About Information ---
ABOUT_TEXT = """BACnet Tools GUI
Version: 1.0

This application provides a graphical user interface for the open-source BACnet command-line tools.

It allows for the discovery and interrogation of BACnet devices on both BACnet/IP and BACnet MS/TP networks.

Developed by:

Wayne Chrestay
Metering and Automation Systems Engineer
wchresta@andrew.cmu.edu
Carnegie Mellon University

Disclaimer:
This software is provided "as-is", without any warranty, express or implied. In no event shall the author be held liable for any damages arising from the use of this software. Use at your own risk.

For more information on the underlying BACnet stack, please visit:
http://bacnet.sourceforge.net/
"""

# --- BACnet Tag Mapping ---
TAG_MAP = {
    "REAL (4)": "4",
    "UnsignedInt (2)": "2",
    "Boolean (1)": "1",
    "CharString (7)": "7",
    "Enumerated (9)": "9",
    "Null (0)": "0",
    "SignedInt (3)": "3",
    "Double (5)": "5",
    "OctetString (6)": "6",
    "Date (10)": "10",
    "Time (11)": "11",
}

# --- Default Values ---
DEFAULTS = {
    'bbmd_ip': '172.19.10.102',
    'ip_network_number': '43722',
    'ip_port': '47808',
    'apdu_timeout': '5000',
    'bbmd_ttl': '60',
    'baud_rate': '38400',
    'read_property': '2;1;85',
    'write_property': '4;1;85',
    'write_value': '0.0',
    'write_tag': 'REAL (4)',
    'write_priority': '16'
}

# --- History File Configuration ---
HISTORY_FILE = 'bacnet_gui_history.json'
HISTORY_LIMIT = 10

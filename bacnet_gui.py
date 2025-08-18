# BACnet Tools GUI Application
# This script creates a Windows application with a graphical user interface (GUI)
# to provide a user-friendly way to interact with the BACnet command-line tools.
# It supports both BACnet/IP and BACnet MS/TP transports, including remote MS/TP discovery.
#
# Prerequisites:
# 1. Python must be installed.
# 2. The BACnet Stack executables must be downloaded and extracted.
#
# Folder Structure:
# This script assumes it is located in a folder, and the BACnet
# executables are in a 'bin' subfolder.
# C:\YourProject\
# |
# |- bacnet_gui.py (this script)
# |
# |- bin\
#    |- bacwi.exe
#    |- bacrp.exe
#    |- bacwp.exe
#    |- ... (other files from the zip)

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os
import sys # Added for PyInstaller pathing
import subprocess
import socket
import threading
import json

HISTORY_FILE = 'bacnet_gui_history.json'
HISTORY_LIMIT = 10

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # In development, use the script's directory
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_network_interfaces():
    """
    Gets a list of non-loopback IPv4 network interfaces.
    """
    interfaces = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            if info[0] == socket.AF_INET:
                ip = info[4][0]
                if not ip.startswith("127."):
                    interfaces.append(ip)
    except socket.gaierror:
        pass  # Silently fail if interfaces can't be determined
    return list(set(interfaces))

class BACnetApp(tk.Tk):
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
        'baud_rate': '38400',
        'read_property': '2;1;85',
        'write_property': '4;1;85',
        'write_value': '0.0',
        'write_tag': 'REAL (4)',
        'write_priority': '16'
    }

    def __init__(self):
        super().__init__()
        self.title("BACnet Tools GUI")
        self.geometry("820x900")

        self.history = {}
        self.load_history()
        
        # --- Menu Bar ---
        self.setup_menu()

        # --- Scrollable Frame Setup ---
        main_canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(
                scrollregion=main_canvas.bbox("all")
            )
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)


        # --- Transport Selection ---
        transport_frame = ttk.LabelFrame(main_frame, text="Transport", padding="10")
        transport_frame.pack(fill=tk.X, pady=5)
        self.transport_var = tk.StringVar(value=self.history.get('last_transport', 'ip'))
        ttk.Radiobutton(transport_frame, text="BACnet/IP", variable=self.transport_var, value='ip', command=self.toggle_transport_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(transport_frame, text="BACnet MS/TP", variable=self.transport_var, value='mstp', command=self.toggle_transport_fields).pack(side=tk.LEFT, padx=10)

        # --- Configuration Frames (Created but packed later) ---
        self.ip_frame = ttk.LabelFrame(main_frame, text="BACnet/IP Configuration", padding="10")
        self.mstp_frame = ttk.LabelFrame(main_frame, text="BACnet MS/TP Configuration", padding="10")
        self.setup_ip_widgets()
        self.setup_mstp_widgets()

        # --- Actions Frame ---
        self.actions_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        self.setup_actions_widgets(self.actions_frame)
        self.actions_frame.pack(fill=tk.X, pady=5)
        
        # --- Output Frame ---
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=20)
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # --- Exit Button ---
        exit_button = ttk.Button(main_frame, text="Exit", command=self.on_closing)
        exit_button.pack(pady=10)

        self.populate_fields_from_history()
        self.toggle_transport_fields()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_menu(self):
        menubar = tk.Menu(self)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Reset to Defaults", command=self.reset_fields_to_defaults)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # About Menu
        about_menu = tk.Menu(menubar, tearoff=0)
        about_menu.add_command(label="About...", command=self.show_about_dialog)
        menubar.add_cascade(label="About", menu=about_menu)
        
        self.config(menu=menubar)

    def show_about_dialog(self):
        about_window = tk.Toplevel(self)
        about_window.title("About BACnet Tools GUI")
        
        about_width = 400
        about_height = 400
        
        label = ttk.Label(about_window, text=self.ABOUT_TEXT, padding="10", wraplength=about_width - 20, justify=tk.LEFT)
        label.pack(expand=True, fill=tk.BOTH)
        
        ok_button = ttk.Button(about_window, text="OK", command=about_window.destroy)
        ok_button.pack(pady=10)
        
        # Center the window on the main application
        self.update_idletasks()
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        
        x_pos = main_x + (main_width // 2) - (about_width // 2)
        y_pos = main_y + (main_height // 2) - (about_height // 2)
        
        about_window.geometry(f"{about_width}x{about_height}+{x_pos}+{y_pos}")
        
        about_window.transient(self)
        about_window.grab_set()
        self.wait_window(about_window)


    def setup_ip_widgets(self):
        frame = self.ip_frame
        ttk.Label(frame, text="Device IP:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ip_address_var = tk.StringVar()
        self.ip_address_cb = ttk.Combobox(frame, textvariable=self.ip_address_var, width=28)
        self.ip_address_cb.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Instance #:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.instance_number_var = tk.StringVar()
        self.instance_number_cb = ttk.Combobox(frame, textvariable=self.instance_number_var, width=13)
        self.instance_number_cb.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame, text="Interface:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.interface_var = tk.StringVar()
        self.interface_cb = ttk.Combobox(frame, textvariable=self.interface_var, width=28)
        self.interface_cb['values'] = get_network_interfaces()
        self.interface_cb.grid(row=1, column=1, padx=5, pady=5)
        if self.interface_cb['values']: self.interface_cb.current(0)

        ttk.Label(frame, text="APDU Timeout (ms):").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.apdu_timeout_var = tk.StringVar()
        self.apdu_timeout_cb = ttk.Combobox(frame, textvariable=self.apdu_timeout_var, width=13)
        self.apdu_timeout_cb.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(frame, text="BBMD IP:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.bbmd_ip_var = tk.StringVar()
        self.bbmd_ip_cb = ttk.Combobox(frame, textvariable=self.bbmd_ip_var, width=28)
        self.bbmd_ip_cb.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frame, text="BBMD DNET:").grid(row=2, column=2, padx=5, pady=5, sticky=tk.W)
        self.bbmd_dnet_var = tk.StringVar()
        self.bbmd_dnet_cb = ttk.Combobox(frame, textvariable=self.bbmd_dnet_var, width=13)
        self.bbmd_dnet_cb.grid(row=2, column=3, padx=5, pady=5)

        ttk.Label(frame, text="BACnet IP Network #:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.ip_network_number_var = tk.StringVar()
        self.ip_network_number_cb = ttk.Combobox(frame, textvariable=self.ip_network_number_var, width=13)
        self.ip_network_number_cb.grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(frame, text="BBMD Port:").grid(row=3, column=2, padx=5, pady=5, sticky=tk.W)
        self.ip_port_var = tk.StringVar()
        self.ip_port_cb = ttk.Combobox(frame, textvariable=self.ip_port_var, width=13)
        self.ip_port_cb.grid(row=3, column=3, padx=5, pady=5)

    def setup_mstp_widgets(self):
        frame = self.mstp_frame
        self.mstp_mode_var = tk.StringVar(value=self.history.get('last_mstp_mode', 'local'))
        ttk.Radiobutton(frame, text="Local", variable=self.mstp_mode_var, value='local', command=self.toggle_mstp_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(frame, text="Remote", variable=self.mstp_mode_var, value='remote', command=self.toggle_mstp_fields).pack(side=tk.LEFT, padx=10)

        self.local_mstp_frame = ttk.Frame(frame)
        self.remote_mstp_frame = ttk.Frame(frame)

        # Local MS/TP Widgets
        ttk.Label(self.local_mstp_frame, text="COM Port:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.com_port_var = tk.StringVar()
        self.com_port_cb = ttk.Combobox(self.local_mstp_frame, textvariable=self.com_port_var, width=15)
        self.com_port_cb.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(self.local_mstp_frame, text="Baud Rate:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.baud_rate_var = tk.StringVar()
        self.baud_rate_cb = ttk.Combobox(self.local_mstp_frame, textvariable=self.baud_rate_var, width=15)
        self.baud_rate_cb.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(self.local_mstp_frame, text="MAC Address (for Ping):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.mac_address_var = tk.StringVar()
        self.mac_address_cb = ttk.Combobox(self.local_mstp_frame, textvariable=self.mac_address_var, width=15)
        self.mac_address_cb.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(self.local_mstp_frame, text="Instance # (for R/W):").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.mstp_instance_var = tk.StringVar()
        self.mstp_instance_cb = ttk.Combobox(self.local_mstp_frame, textvariable=self.mstp_instance_var, width=15)
        self.mstp_instance_cb.grid(row=1, column=3, padx=5, pady=5)

        # Remote MS/TP Widgets
        ttk.Label(self.remote_mstp_frame, text="Network #:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.network_number_var = tk.StringVar()
        self.network_number_cb = ttk.Combobox(self.remote_mstp_frame, textvariable=self.network_number_var, width=15)
        self.network_number_cb.grid(row=0, column=1, padx=5, pady=5)

    def setup_actions_widgets(self, actions_frame):
        # Read Property
        ttk.Label(actions_frame, text="Read Property (objType;inst;prop):").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.read_property_var = tk.StringVar()
        self.read_property_cb = ttk.Combobox(actions_frame, textvariable=self.read_property_var, width=40)
        self.read_property_cb.grid(row=0, column=2, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # Write Property
        ttk.Label(actions_frame, text="Write Property (objType;inst;prop):").grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.write_property_var = tk.StringVar()
        self.write_property_cb = ttk.Combobox(actions_frame, textvariable=self.write_property_var, width=40)
        self.write_property_cb.grid(row=1, column=2, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(actions_frame, text="Value:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.write_value_var = tk.StringVar()
        self.write_value_cb = ttk.Combobox(actions_frame, textvariable=self.write_value_var, width=15)
        self.write_value_cb.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(actions_frame, text="Data Type:").grid(row=2, column=2, padx=5, pady=5, sticky=tk.W)
        self.write_tag_var = tk.StringVar()
        self.write_tag_cb = ttk.Combobox(actions_frame, textvariable=self.write_tag_var, width=15, state='readonly')
        self.write_tag_cb['values'] = list(self.TAG_MAP.keys())
        self.write_tag_cb.grid(row=2, column=3, padx=5, pady=5, sticky=tk.W)

        ttk.Label(actions_frame, text="Priority:").grid(row=2, column=4, padx=5, pady=5, sticky=tk.W)
        self.write_priority_var = tk.StringVar()
        self.write_priority_cb = ttk.Combobox(actions_frame, textvariable=self.write_priority_var, width=10)
        self.write_priority_cb.grid(row=2, column=5, padx=5, pady=5, sticky=tk.W)


        # Buttons
        self.ping_button = ttk.Button(actions_frame, text="Ping (Who-Is)", command=self.run_ping)
        self.ping_button.grid(row=3, column=0, padx=5, pady=10)
        
        self.discover_button = ttk.Button(actions_frame, text="Discover Devices", command=self.run_discover)
        self.discover_button.grid(row=3, column=1, padx=5, pady=10)

        self.read_button = ttk.Button(actions_frame, text="Read Property", command=self.run_read_property)
        self.read_button.grid(row=3, column=2, padx=5, pady=10)

        self.write_button = ttk.Button(actions_frame, text="Write Property", command=self.run_write_property)
        self.write_button.grid(row=3, column=3, padx=5, pady=10)
        
        self.reset_button = ttk.Button(actions_frame, text="Reset to Defaults", command=self.reset_fields_to_defaults)
        self.reset_button.grid(row=3, column=4, padx=5, pady=10)


    def toggle_transport_fields(self):
        # Forget both frames first to ensure a clean slate
        if self.ip_frame.winfo_manager():
            self.ip_frame.pack_forget()
        if self.mstp_frame.winfo_manager():
            self.mstp_frame.pack_forget()

        if self.transport_var.get() == 'ip':
            self.ip_frame.pack(fill=tk.X, pady=5, before=self.actions_frame)
            self.ping_button.config(text="Ping (Who-Is)")
            self.read_button.config(state=tk.NORMAL)
            self.write_button.config(state=tk.NORMAL)
        else: # mstp
            self.mstp_frame.pack(fill=tk.X, pady=5, before=self.actions_frame)
            self.toggle_mstp_fields()

    def toggle_mstp_fields(self):
        if self.mstp_mode_var.get() == 'local':
            self.remote_mstp_frame.pack_forget()
            if self.ip_frame.winfo_manager():
                self.ip_frame.pack_forget()
            self.local_mstp_frame.pack(fill=tk.X, pady=5)
            self.ping_button.config(text="Ping (Who-Is)")
            self.read_button.config(state=tk.NORMAL)
            self.write_button.config(state=tk.NORMAL)
        else: # Remote
            self.local_mstp_frame.pack_forget()
            self.remote_mstp_frame.pack(fill=tk.X, pady=5)
            if not self.ip_frame.winfo_manager():
                self.ip_frame.pack(fill=tk.X, pady=5, after=self.mstp_frame)
            self.ip_frame.config(text="Router (BACnet/IP) Configuration")
            self.ping_button.config(text="Discover Network")
            self.read_button.config(state=tk.NORMAL) 
            self.write_button.config(state=tk.NORMAL)

    def on_closing(self):
        self.save_history()
        self.destroy()

    def load_history(self):
        history_path = get_resource_path(HISTORY_FILE)
        if os.path.exists(history_path):
            with open(history_path, 'r') as f: self.history = json.load(f)

    def save_history(self):
        self.history['last_transport'] = self.transport_var.get()
        self.history['last_mstp_mode'] = self.mstp_mode_var.get()
        history_path = get_resource_path(HISTORY_FILE)
        with open(history_path, 'w') as f: json.dump(self.history, f, indent=4)

    def update_history(self, field_key, value):
        if not value: return
        if field_key not in self.history: self.history[field_key] = []
        if value in self.history[field_key]: self.history[field_key].remove(value)
        self.history[field_key].insert(0, value)
        self.history[field_key] = self.history[field_key][:HISTORY_LIMIT]

    def populate_fields_from_history(self):
        self.ip_address_cb['values'] = self.history.get('ip_address', [])
        self.instance_number_cb['values'] = self.history.get('instance_number', [])
        self.apdu_timeout_cb['values'] = self.history.get('apdu_timeout', [self.DEFAULTS['apdu_timeout']])
        self.bbmd_ip_cb['values'] = self.history.get('bbmd_ip', [self.DEFAULTS['bbmd_ip']])
        self.bbmd_dnet_cb['values'] = self.history.get('bbmd_dnet', [])
        self.ip_network_number_cb['values'] = self.history.get('ip_network_number', [self.DEFAULTS['ip_network_number']])
        self.ip_port_cb['values'] = self.history.get('ip_port', [self.DEFAULTS['ip_port']])
        self.com_port_cb['values'] = self.history.get('com_port', ['COM1', 'COM2', 'COM3'])
        self.baud_rate_cb['values'] = self.history.get('baud_rate', ['9600', '19200', '38400', '76800'])
        self.mac_address_cb['values'] = self.history.get('mac_address', [])
        self.mstp_instance_cb['values'] = self.history.get('mstp_instance', [])
        self.network_number_cb['values'] = self.history.get('network_number', [])
        self.read_property_cb['values'] = self.history.get('read_property', [self.DEFAULTS['read_property']])
        self.write_property_cb['values'] = self.history.get('write_property', [self.DEFAULTS['write_property']])
        self.write_value_cb['values'] = self.history.get('write_value', [self.DEFAULTS['write_value']])
        self.write_tag_cb.set(self.history.get('write_tag', self.DEFAULTS['write_tag']))
        self.write_priority_cb['values'] = self.history.get('write_priority', [self.DEFAULTS['write_priority']])

        # Set current value to default if field is empty
        self.reset_fields_to_defaults(load_from_history=True)

    def reset_fields_to_defaults(self, load_from_history=False):
        # If not loading, we're explicitly resetting. Otherwise, just fill empty fields.
        if not load_from_history or not self.bbmd_ip_var.get():
            self.bbmd_ip_var.set(self.DEFAULTS['bbmd_ip'])
        if not load_from_history or not self.ip_network_number_var.get():
            self.ip_network_number_var.set(self.DEFAULTS['ip_network_number'])
        if not load_from_history or not self.ip_port_var.get():
            self.ip_port_var.set(self.DEFAULTS['ip_port'])
        if not load_from_history or not self.apdu_timeout_var.get():
            self.apdu_timeout_var.set(self.DEFAULTS['apdu_timeout'])
        if not load_from_history or not self.baud_rate_var.get():
            self.baud_rate_var.set(self.DEFAULTS['baud_rate'])
        if not load_from_history or not self.read_property_var.get():
            self.read_property_var.set(self.DEFAULTS['read_property'])
        if not load_from_history or not self.write_property_var.get():
            self.write_property_var.set(self.DEFAULTS['write_property'])
        if not load_from_history or not self.write_value_var.get():
            self.write_value_var.set(self.DEFAULTS['write_value'])
        if not load_from_history or not self.write_tag_var.get():
            self.write_tag_var.set(self.DEFAULTS['write_tag'])
        if not load_from_history or not self.write_priority_var.get():
            self.write_priority_var.set(self.DEFAULTS['write_priority'])


    def log(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.update_idletasks()

    def run_command_in_thread(self, command, cwd, env):
        thread = threading.Thread(target=self.run_command, args=(command, cwd, env))
        thread.start()

    def run_command(self, command, cwd, env):
        try:
            self.log(f"Executing: {' '.join(command)}")
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=30, env=env, cwd=cwd,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.stdout: self.log("--- SUCCESS ---\n" + result.stdout.strip())
            if result.stderr: self.log("--- ERROR ---\n" + result.stderr.strip())
        except subprocess.TimeoutExpired:
            self.log("--- ERROR: Command timed out. ---")
        except Exception as e:
            self.log(f"--- An unexpected error occurred: {e} ---")

    def execute_bacnet_command(self, command_type):
        bin_dir = get_resource_path('bin')
        if not os.path.exists(bin_dir):
            messagebox.showerror("Error", f"'bin' directory not found at: {bin_dir}")
            return

        env = os.environ.copy()
        device_identifier = ""
        
        transport = self.transport_var.get()
        if transport == 'ip' or (transport == 'mstp' and self.mstp_mode_var.get() == 'remote'):
            ip_port_value = self.ip_port_var.get()
            if self.interface_var.get(): env['BACNET_IFACE'] = self.interface_var.get()
            if self.bbmd_ip_var.get(): env['BACNET_BBMD_ADDRESS'] = self.bbmd_ip_var.get()
            if self.bbmd_dnet_var.get(): env['BACNET_BBMD_DNET'] = self.bbmd_dnet_var.get()
            if self.apdu_timeout_var.get(): env['BACNET_APDU_TIMEOUT'] = self.apdu_timeout_var.get()
            if self.ip_network_number_var.get(): env['BACNET_IP_NETWORK'] = self.ip_network_number_var.get()
            if ip_port_value:
                env['BACNET_BBMD_PORT'] = ip_port_value
            
            self.update_history('apdu_timeout', self.apdu_timeout_var.get())
            self.update_history('bbmd_ip', self.bbmd_ip_var.get())
            self.update_history('bbmd_dnet', self.bbmd_dnet_var.get())
            self.update_history('ip_network_number', self.ip_network_number_var.get())
            self.update_history('ip_port', ip_port_value)

        if transport == 'ip':
            device_identifier = self.instance_number_var.get()
            if command_type != 'discover' and not device_identifier:
                messagebox.showerror("Error", "Instance number is required for this action.")
                return
            self.update_history('instance_number', device_identifier)
        
        elif transport == 'mstp':
            mstp_mode = self.mstp_mode_var.get()
            if mstp_mode == 'local':
                if command_type == 'ping':
                    device_identifier = self.mac_address_var.get()
                    if not device_identifier:
                        messagebox.showerror("Error", "MAC Address is required for Ping.")
                        return
                elif command_type in ['read', 'write']:
                    device_identifier = self.mstp_instance_var.get()
                    if not device_identifier:
                        messagebox.showerror("Error", "Instance # is required for Read/Write.")
                        return
                
                self.update_history('com_port', self.com_port_var.get())
                self.update_history('baud_rate', self.baud_rate_var.get())
                self.update_history('mac_address', self.mac_address_var.get())
                self.update_history('mstp_instance', self.mstp_instance_var.get())
                if self.com_port_var.get(): env['BACNET_IFACE'] = self.com_port_var.get()
                if self.baud_rate_var.get(): env['BACNET_MSTP_BAUD'] = self.baud_rate_var.get()
            else: # Remote MS/TP
                if command_type == 'ping': # Discover Network
                    device_identifier = self.network_number_var.get()
                    if not device_identifier:
                        messagebox.showerror("Error", "Network Number is required for remote discovery.")
                        return
                    self.update_history('network_number', device_identifier)
                else: # Read, Write or Discover
                    device_identifier = self.instance_number_var.get()
                    if command_type != 'discover' and not device_identifier:
                        messagebox.showerror("Error", "Instance # is required for this action.\n(Discover the remote network first to find it)")
                        return
                    self.update_history('instance_number', device_identifier)


        if command_type == 'read':
            self.update_history('read_property', self.read_property_var.get())
        elif command_type == 'write':
            self.update_history('write_property', self.write_property_var.get())
            self.update_history('write_value', self.write_value_var.get())
            self.update_history('write_tag', self.write_tag_var.get())
            self.update_history('write_priority', self.write_priority_var.get())

        self.populate_fields_from_history()

        self.output_text.delete('1.0', tk.END)
        self.log("--- Starting Command ---")

        bacwi_path = os.path.join(bin_dir, 'bacwi.exe')
        if not os.path.exists(bacwi_path):
            messagebox.showerror("Error", f"bacwi.exe not found in '{bin_dir}'")
            return
            
        command = []
        if command_type == 'discover':
            command = [bacwi_path, "-1"]
        elif command_type == 'ping':
            command = [bacwi_path, device_identifier]
        elif command_type == 'read':
            read_prop_str = self.read_property_var.get()
            if not read_prop_str:
                messagebox.showerror("Error", "Read Property field cannot be empty.")
                return
            try:
                obj_type, obj_inst, prop_id = read_prop_str.split(';')
            except ValueError:
                messagebox.showerror("Error", "Invalid format for Read Property. Use 'objType;inst;prop'.")
                return
            
            bacrp_path = os.path.join(bin_dir, 'bacrp.exe')
            if not os.path.exists(bacrp_path):
                messagebox.showerror("Error", f"bacrp.exe not found in '{bin_dir}'")
                return
            
            command = [bacrp_path, device_identifier, obj_type, obj_inst, prop_id]
        
        elif command_type == 'write':
            write_prop_str = self.write_property_var.get()
            value = self.write_value_var.get()
            tag_name = self.write_tag_var.get()
            priority = self.write_priority_var.get()

            if not all([write_prop_str, value, tag_name, priority]):
                messagebox.showerror("Error", "All Write Property fields are required.")
                return
            try:
                obj_type, obj_inst, prop_id = write_prop_str.split(';')
            except ValueError:
                messagebox.showerror("Error", "Invalid format for Write Property. Use 'objType;inst;prop'.")
                return
            
            tag_value = self.TAG_MAP.get(tag_name)
            if not tag_value:
                messagebox.showerror("Error", f"Invalid tag name selected: {tag_name}")
                return

            bacwp_path = os.path.join(bin_dir, 'bacwp.exe')
            if not os.path.exists(bacwp_path):
                messagebox.showerror("Error", f"bacwp.exe not found in '{bin_dir}'")
                return
            
            # bacwp <device-instance> <obj-type> <obj-inst> <prop-id> <priority> <index> <tag> <value>
            command = [bacwp_path, device_identifier, obj_type, obj_inst, prop_id, priority, "-1", tag_value, value]


        if command:
            self.run_command_in_thread(command, bin_dir, env)

    def run_ping(self):
        self.execute_bacnet_command('ping')

    def run_discover(self):
        self.execute_bacnet_command('discover')

    def run_read_property(self):
        self.execute_bacnet_command('read')
    
    def run_write_property(self):
        self.execute_bacnet_command('write')

if __name__ == "__main__":
    app = BACnetApp()
    app.mainloop()

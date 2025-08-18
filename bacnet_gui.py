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
    def __init__(self):
        super().__init__()
        self.title("BACnet Tools GUI")
        self.geometry("800x700")

        self.history = {}
        self.load_history()

        # --- Main Frame ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Transport Selection ---
        transport_frame = ttk.LabelFrame(main_frame, text="Transport", padding="10")
        transport_frame.pack(fill=tk.X, pady=5)
        self.transport_var = tk.StringVar(value=self.history.get('last_transport', 'ip'))
        ttk.Radiobutton(transport_frame, text="BACnet/IP", variable=self.transport_var, value='ip', command=self.toggle_transport_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(transport_frame, text="BACnet MS/TP", variable=self.transport_var, value='mstp', command=self.toggle_transport_fields).pack(side=tk.LEFT, padx=10)

        # --- Configuration Frames ---
        self.ip_frame = ttk.LabelFrame(main_frame, text="BACnet/IP Configuration", padding="10")
        self.mstp_frame = ttk.LabelFrame(main_frame, text="BACnet MS/TP Configuration", padding="10")

        # --- IP Frame Widgets ---
        self.setup_ip_widgets()

        # --- MS/TP Frame Widgets ---
        self.setup_mstp_widgets()

        # --- Actions Frame ---
        self.setup_actions_widgets(main_frame)
        
        # --- Output Frame ---
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=20)
        self.output_text.pack(fill=tk.BOTH, expand=True)

        self.populate_fields_from_history()
        self.toggle_transport_fields()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ip_widgets(self):
        ttk.Label(self.ip_frame, text="Device IP:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ip_address_var = tk.StringVar()
        self.ip_address_cb = ttk.Combobox(self.ip_frame, textvariable=self.ip_address_var, width=28)
        self.ip_address_cb.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(self.ip_frame, text="Instance #:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.instance_number_var = tk.StringVar()
        self.instance_number_cb = ttk.Combobox(self.ip_frame, textvariable=self.instance_number_var, width=13)
        self.instance_number_cb.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(self.ip_frame, text="Interface:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.interface_var = tk.StringVar()
        self.interface_cb = ttk.Combobox(self.ip_frame, textvariable=self.interface_var, width=28)
        self.interface_cb['values'] = get_network_interfaces()
        self.interface_cb.grid(row=1, column=1, padx=5, pady=5)
        if self.interface_cb['values']: self.interface_cb.current(0)

        ttk.Label(self.ip_frame, text="APDU Timeout (ms):").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.apdu_timeout_var = tk.StringVar()
        self.apdu_timeout_cb = ttk.Combobox(self.ip_frame, textvariable=self.apdu_timeout_var, width=13)
        self.apdu_timeout_cb.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(self.ip_frame, text="BBMD IP:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.bbmd_ip_var = tk.StringVar()
        self.bbmd_ip_cb = ttk.Combobox(self.ip_frame, textvariable=self.bbmd_ip_var, width=28)
        self.bbmd_ip_cb.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(self.ip_frame, text="BBMD DNET:").grid(row=2, column=2, padx=5, pady=5, sticky=tk.W)
        self.bbmd_dnet_var = tk.StringVar()
        self.bbmd_dnet_cb = ttk.Combobox(self.ip_frame, textvariable=self.bbmd_dnet_var, width=13)
        self.bbmd_dnet_cb.grid(row=2, column=3, padx=5, pady=5)

    def setup_mstp_widgets(self):
        self.mstp_mode_var = tk.StringVar(value=self.history.get('last_mstp_mode', 'local'))
        ttk.Radiobutton(self.mstp_frame, text="Local", variable=self.mstp_mode_var, value='local', command=self.toggle_mstp_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.mstp_frame, text="Remote", variable=self.mstp_mode_var, value='remote', command=self.toggle_mstp_fields).pack(side=tk.LEFT, padx=10)

        self.local_mstp_frame = ttk.Frame(self.mstp_frame)
        self.remote_mstp_frame = ttk.Frame(self.mstp_frame)

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

        ttk.Label(self.local_mstp_frame, text="Instance # (for Read):").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.mstp_instance_var = tk.StringVar()
        self.mstp_instance_cb = ttk.Combobox(self.local_mstp_frame, textvariable=self.mstp_instance_var, width=15)
        self.mstp_instance_cb.grid(row=1, column=3, padx=5, pady=5)

        # Remote MS/TP Widgets
        ttk.Label(self.remote_mstp_frame, text="Network #:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.network_number_var = tk.StringVar()
        self.network_number_cb = ttk.Combobox(self.remote_mstp_frame, textvariable=self.network_number_var, width=15)
        self.network_number_cb.grid(row=0, column=1, padx=5, pady=5)

    def setup_actions_widgets(self, parent):
        actions_frame = ttk.LabelFrame(parent, text="Actions", padding="10")
        actions_frame.pack(fill=tk.X, pady=5)

        ttk.Label(actions_frame, text="Read Property (objType;inst;prop):").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.read_property_var = tk.StringVar()
        self.read_property_cb = ttk.Combobox(actions_frame, textvariable=self.read_property_var, width=28)
        self.read_property_cb.grid(row=0, column=2, columnspan=2, padx=5, pady=5, sticky=tk.W)

        self.ping_button = ttk.Button(actions_frame, text="Ping (Who-Is)", command=self.run_ping)
        self.ping_button.grid(row=1, column=0, padx=5, pady=10)
        
        self.discover_button = ttk.Button(actions_frame, text="Discover Devices", command=self.run_discover)
        self.discover_button.grid(row=1, column=1, padx=5, pady=10)

        self.read_button = ttk.Button(actions_frame, text="Read Property", command=self.run_read_property)
        self.read_button.grid(row=1, column=2, padx=5, pady=10)

    def toggle_transport_fields(self):
        if self.transport_var.get() == 'ip':
            self.mstp_frame.pack_forget()
            self.ip_frame.pack(fill=tk.X, pady=5)
            self.ping_button.config(text="Ping (Who-Is)")
            self.read_button.config(state=tk.NORMAL)
        else:
            self.ip_frame.pack_forget()
            self.mstp_frame.pack(fill=tk.X, pady=5)
            self.toggle_mstp_fields()

    def toggle_mstp_fields(self):
        if self.mstp_mode_var.get() == 'local':
            self.remote_mstp_frame.pack_forget()
            self.local_mstp_frame.pack(fill=tk.X, pady=5)
            self.ping_button.config(text="Ping (Who-Is)")
            self.read_button.config(state=tk.NORMAL)
        else: # Remote
            self.local_mstp_frame.pack_forget()
            self.remote_mstp_frame.pack(fill=tk.X, pady=5)
            self.ping_button.config(text="Discover Network")
            self.read_button.config(state=tk.DISABLED)

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
        self.apdu_timeout_cb['values'] = self.history.get('apdu_timeout', ['20000', '10000', '5000', '3000'])
        self.bbmd_ip_cb['values'] = self.history.get('bbmd_ip', [])
        self.bbmd_dnet_cb['values'] = self.history.get('bbmd_dnet', [])
        self.com_port_cb['values'] = self.history.get('com_port', ['COM1', 'COM2', 'COM3'])
        self.baud_rate_cb['values'] = self.history.get('baud_rate', ['9600', '19200', '38400', '76800'])
        self.mac_address_cb['values'] = self.history.get('mac_address', [])
        self.mstp_instance_cb['values'] = self.history.get('mstp_instance', [])
        self.network_number_cb['values'] = self.history.get('network_number', [])
        self.read_property_cb['values'] = self.history.get('read_property', ['8;12345;77'])

        if not self.apdu_timeout_var.get(): self.apdu_timeout_var.set("20000")
        if not self.read_property_var.get(): self.read_property_var.set("8;12345;77")
        if not self.baud_rate_var.get(): self.baud_rate_var.set("38400")

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
            if self.interface_var.get(): env['BACNET_IFACE'] = self.interface_var.get()
            if self.bbmd_ip_var.get(): env['BACNET_BBMD_ADDRESS'] = self.bbmd_ip_var.get()
            if self.bbmd_dnet_var.get(): env['BACNET_BBMD_DNET'] = self.bbmd_dnet_var.get()
            if self.apdu_timeout_var.get(): env['BACNET_APDU_TIMEOUT'] = self.apdu_timeout_var.get()
            self.update_history('apdu_timeout', self.apdu_timeout_var.get())
            self.update_history('bbmd_ip', self.bbmd_ip_var.get())
            self.update_history('bbmd_dnet', self.bbmd_dnet_var.get())

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
                elif command_type == 'read':
                    device_identifier = self.mstp_instance_var.get()
                    if not device_identifier:
                        messagebox.showerror("Error", "Instance # is required for Read.")
                        return
                
                self.update_history('com_port', self.com_port_var.get())
                self.update_history('baud_rate', self.baud_rate_var.get())
                self.update_history('mac_address', self.mac_address_var.get())
                self.update_history('mstp_instance', self.mstp_instance_var.get())
                if self.com_port_var.get(): env['BACNET_IFACE'] = self.com_port_var.get()
                if self.baud_rate_var.get(): env['BACNET_MSTP_BAUD'] = self.baud_rate_var.get()
            else: # Remote MS/TP
                device_identifier = self.network_number_var.get()
                if not device_identifier:
                    messagebox.showerror("Error", "Network Number is required for remote discovery.")
                    return
                self.update_history('network_number', device_identifier)
                if command_type == 'read': return

        self.update_history('read_property', self.read_property_var.get())
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

        if command:
            self.run_command_in_thread(command, bin_dir, env)

    def run_ping(self):
        self.execute_bacnet_command('ping')

    def run_discover(self):
        self.execute_bacnet_command('discover')

    def run_read_property(self):
        self.execute_bacnet_command('read')

if __name__ == "__main__":
    app = BACnetApp()
    app.mainloop()

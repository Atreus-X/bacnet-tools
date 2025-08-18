# BACnet Tools GUI Application
# This script creates a Windows application with a graphical user interface (GUI)
# to provide a user-friendly way to interact with the BACnet command-line tools.
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
import subprocess
import socket
import threading

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
        self.geometry("800x600")

        # --- Main Frame ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Configuration Frame ---
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.pack(fill=tk.X, pady=5)

        # IP Address
        ttk.Label(config_frame, text="Device IP:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ip_address = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.ip_address, width=30).grid(row=0, column=1, padx=5, pady=5)

        # Instance Number
        ttk.Label(config_frame, text="Instance #:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.instance_number = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.instance_number, width=15).grid(row=0, column=3, padx=5, pady=5)

        # Network Interface
        ttk.Label(config_frame, text="Interface:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.interface = tk.StringVar()
        self.interface_combobox = ttk.Combobox(config_frame, textvariable=self.interface, width=28)
        self.interface_combobox['values'] = get_network_interfaces()
        self.interface_combobox.grid(row=1, column=1, padx=5, pady=5)
        if self.interface_combobox['values']:
            self.interface_combobox.current(0)

        # BBMD
        ttk.Label(config_frame, text="BBMD IP:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.bbmd_ip = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.bbmd_ip, width=30).grid(row=2, column=1, padx=5, pady=5)

        # BBMD DNET
        ttk.Label(config_frame, text="BBMD DNET:").grid(row=2, column=2, padx=5, pady=5, sticky=tk.W)
        self.bbmd_dnet = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.bbmd_dnet, width=15).grid(row=2, column=3, padx=5, pady=5)

        # --- Actions Frame ---
        actions_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        actions_frame.pack(fill=tk.X, pady=5)

        # Read Property
        ttk.Label(actions_frame, text="Read Property (objType;inst;prop):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.read_property = tk.StringVar(value="8;12345;77") # Example value
        ttk.Entry(actions_frame, textvariable=self.read_property, width=30).grid(row=0, column=1, padx=5, pady=5)

        # Buttons
        self.ping_button = ttk.Button(actions_frame, text="Ping (Who-Is)", command=self.run_ping)
        self.ping_button.grid(row=1, column=0, padx=5, pady=10)

        self.read_button = ttk.Button(actions_frame, text="Read Property", command=self.run_read_property)
        self.read_button.grid(row=1, column=1, padx=5, pady=10)
        
        # --- Output Frame ---
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=20)
        self.output_text.pack(fill=tk.BOTH, expand=True)

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
                command,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                cwd=cwd,
                creationflags=subprocess.CREATE_NO_WINDOW # Hide console window on Windows
            )
            if result.stdout:
                self.log("--- SUCCESS ---")
                self.log(result.stdout.strip())
            if result.stderr:
                self.log("--- ERROR ---")
                self.log(result.stderr.strip())
        except subprocess.TimeoutExpired:
            self.log("--- ERROR: Command timed out. ---")
        except Exception as e:
            self.log(f"--- An unexpected error occurred: {e} ---")

    def execute_bacnet_command(self, command_type):
        instance = self.instance_number.get()
        if not instance:
            messagebox.showerror("Error", "Instance number is required.")
            return

        script_dir = os.path.dirname(os.path.realpath(__file__))
        bin_dir = os.path.join(script_dir, 'bin')
        
        if not os.path.exists(bin_dir):
            messagebox.showerror("Error", f"'bin' directory not found at: {bin_dir}")
            return

        env = os.environ.copy()
        if self.interface.get():
            env['BACNET_IFACE'] = self.interface.get()
        if self.bbmd_ip.get():
            env['BACNET_BBMD_ADDRESS'] = self.bbmd_ip.get()
        if self.bbmd_dnet.get():
            env['BACNET_BBMD_DNET'] = self.bbmd_dnet.get()
        env['BACNET_APDU_TIMEOUT'] = '20000'

        self.output_text.delete('1.0', tk.END)
        self.log("--- Starting Command ---")

        if command_type == 'ping':
            bacwi_path = os.path.join(bin_dir, 'bacwi.exe')
            if not os.path.exists(bacwi_path):
                messagebox.showerror("Error", f"bacwi.exe not found in '{bin_dir}'")
                return
            command = [bacwi_path, instance]
            self.run_command_in_thread(command, bin_dir, env)

        elif command_type == 'read':
            read_prop_str = self.read_property.get()
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
            command = [bacrp_path, instance, obj_type, obj_inst, prop_id]
            self.run_command_in_thread(command, bin_dir, env)

    def run_ping(self):
        self.execute_bacnet_command('ping')

    def run_read_property(self):
        self.execute_bacnet_command('read')

if __name__ == "__main__":
    app = BACnetApp()
    app.mainloop()

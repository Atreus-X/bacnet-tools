# main_app.py
# This is the main entry point for the BACnet Tools GUI application.

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os
import json
import re

import config
import ui_components
import bacnet_logic
import utils

class BACnetApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BACnet Tools GUI")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        app_width = 850
        app_height = 1032

        if screen_width < app_width or screen_height < app_height:
            app_width = screen_width // 2
            app_height = screen_height // 2

        self.geometry(f"{app_width}x{app_height}")

        self.history = {}
        # Initialize property vars before loading history
        self.read_property_vars = {'obj_type': '8', 'obj_inst': '4000037', 'prop_id': '77'}
        self.write_property_vars = {'obj_type': '8', 'obj_inst': '4000037', 'prop_id': '77', 'value': '0', 'tag': 'REAL (4)', 'priority': '16'}
        self.load_history()

        self.current_process = None
        self.last_pinged_device = None
        self.object_data = {}
        self.TAG_MAP = config.TAG_MAP
        
        ui_components.setup_menu(self)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        transport_frame = ttk.LabelFrame(main_frame, text="Transport", padding="10")
        transport_frame.pack(fill=tk.X, pady=5)
        self.transport_var = tk.StringVar(value=self.history.get('last_transport', 'ip'))
        ttk.Radiobutton(transport_frame, text="BACnet/IP", variable=self.transport_var, value='ip', command=self.toggle_transport_fields).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(transport_frame, text="BACnet MS/TP", variable=self.transport_var, value='mstp', command=self.toggle_transport_fields).pack(side=tk.LEFT, padx=10)

        self.ip_frame = ttk.LabelFrame(main_frame, text="BACnet/IP Configuration", padding="10")
        self.mstp_frame = ttk.LabelFrame(main_frame, text="BACnet MS/TP Configuration", padding="10")
        ui_components.setup_ip_widgets(self)
        ui_components.setup_mstp_widgets(self)

        self.actions_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        ui_components.setup_actions_widgets(self, self.actions_frame)
        self.actions_frame.pack(fill=tk.X, pady=5)
        
        # Create and pack the bottom frame first, anchoring it to the bottom
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        self.reset_button = ttk.Button(bottom_frame, text="Reset to Defaults", command=self.reset_fields_to_defaults)
        self.reset_button.pack(side=tk.LEFT, padx=5)

        exit_button = ttk.Button(bottom_frame, text="Exit", command=self.on_closing)
        exit_button.pack(side=tk.RIGHT, padx=5)

        # Now, create the paned window to fill the remaining space
        paned_window = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned_window.pack(fill=tk.BOTH, expand=True, pady=5)

        browser_frame = ttk.LabelFrame(paned_window, text="Device & Object Browser", padding="10")
        ui_components.setup_object_browser(self, browser_frame)
        paned_window.add(browser_frame, weight=3)

        output_frame = ttk.LabelFrame(paned_window, text="Output", padding="10")
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=5)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        paned_window.add(output_frame, weight=1)

        clear_output_button = ttk.Button(output_frame, text="Clear", command=self.clear_output)
        clear_output_button.pack(side=tk.RIGHT, pady=5)

        self.populate_fields_from_history()
        self.toggle_transport_fields()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.ip_address_var.trace_add("write", self.update_ping_state)
        self.instance_number_var.trace_add("write", self.update_all_states)
        self.mstp_instance_var.trace_add("write", self.update_read_write_state)
        self.mac_address_var.trace_add("write", self.update_ping_state)
        self.network_number_var.trace_add("write", self.update_ping_state)
        self.update_all_states()

        self.ip_address_cb.bind('<FocusOut>', lambda event: self.update_history('ip_address', self.ip_address_var.get()))
        self.ip_address_cb.bind('<<ComboboxSelected>>', lambda event: self.update_history('ip_address', self.ip_address_var.get()))
        self.instance_number_cb.bind('<FocusOut>', lambda event: self.update_history('instance_number', self.instance_number_var.get()))
        self.instance_number_cb.bind('<<ComboboxSelected>>', lambda event: self.update_history('instance_number', self.instance_number_var.get()))

    def clear_output(self):
        self.output_text.delete('1.0', tk.END)

    def toggle_transport_fields(self):
        if self.ip_frame.winfo_manager(): self.ip_frame.pack_forget()
        if self.mstp_frame.winfo_manager(): self.mstp_frame.pack_forget()
        if self.transport_var.get() == 'ip':
            self.ip_frame.pack(fill=tk.X, pady=5, before=self.actions_frame)
        else:
            self.mstp_frame.pack(fill=tk.X, pady=5, before=self.actions_frame)
            self.toggle_mstp_fields()
        self.update_all_states()

    def toggle_mstp_fields(self):
        if self.mstp_mode_var.get() == 'local':
            self.remote_mstp_frame.pack_forget()
            if self.ip_frame.winfo_manager(): self.ip_frame.pack_forget()
            self.local_mstp_frame.pack(fill=tk.X, pady=5)
        else:
            self.local_mstp_frame.pack_forget()
            self.remote_mstp_frame.pack(fill=tk.X, pady=5)
            if not self.ip_frame.winfo_manager(): self.ip_frame.pack(fill=tk.X, pady=5, after=self.mstp_frame)
            self.ip_frame.config(text="Router (BACnet/IP) Configuration")
        self.update_all_states()

    def update_all_states(self, *args):
        self.update_ping_state()
        self.update_read_write_state()

    def update_ping_state(self, *args):
        state = tk.DISABLED
        transport = self.transport_var.get()
        if transport == 'ip':
            if self.instance_number_var.get() and self.ip_address_var.get():
                state = tk.NORMAL
            self.ping_button.config(text="Ping (Who-Is)")
        elif transport == 'mstp':
            mstp_mode = self.mstp_mode_var.get()
            if mstp_mode == 'local':
                if self.mac_address_var.get():
                    state = tk.NORMAL
                self.ping_button.config(text="Ping (Who-Is)")
            else:
                if self.network_number_var.get():
                    state = tk.NORMAL
                self.ping_button.config(text="Discover Network")
        self.ping_button.config(state=state)

    def update_read_write_state(self, *args):
        state = tk.DISABLED
        transport = self.transport_var.get()
        if transport == 'ip':
            if self.instance_number_var.get():
                state = tk.NORMAL
        elif transport == 'mstp':
            mstp_mode = self.mstp_mode_var.get()
            if mstp_mode == 'local':
                if self.mstp_instance_var.get():
                    state = tk.NORMAL
            else: # Remote
                if self.instance_number_var.get():
                    state = tk.NORMAL
        
        self.read_property_button.config(state=state)
        self.write_property_button.config(state=state)

    def on_closing(self):
        self.save_history()
        self.destroy()

    def load_history(self):
        history_path = utils.get_persistent_data_path(config.HISTORY_FILE)
        if os.path.exists(history_path):
            with open(history_path, 'r') as f: self.history = json.load(f)
            self.read_property_vars = self.history.get('read_property_vars', self.read_property_vars)
            self.write_property_vars = self.history.get('write_property_vars', self.write_property_vars)

    def save_history(self):
        self.history['last_transport'] = self.transport_var.get()
        self.history['last_mstp_mode'] = self.mstp_mode_var.get()
        self.history['read_property_vars'] = self.read_property_vars
        self.history['write_property_vars'] = self.write_property_vars
        history_path = utils.get_persistent_data_path(config.HISTORY_FILE)
        with open(history_path, 'w') as f: json.dump(self.history, f, indent=4)

    def update_history(self, field_key, value):
        if not value: return
        if field_key not in self.history: self.history[field_key] = []
        if value in self.history[field_key]: self.history[field_key].remove(value)
        self.history[field_key].insert(0, value)
        self.history[field_key] = self.history[field_key][:config.HISTORY_LIMIT]

    def clear_history(self):
        self.history = {}
        self.save_history()
        self.read_property_vars = {'obj_type': '8', 'obj_inst': '4000037', 'prop_id': '77'}
        self.write_property_vars = {'obj_type': '8', 'obj_inst': '4000037', 'prop_id': '77', 'value': '0', 'tag': 'REAL (4)', 'priority': '16'}
        self.populate_fields_from_history()

    def populate_fields_from_history(self):
        self.ip_address_cb['values'] = self.history.get('ip_address', [])
        self.instance_number_cb['values'] = self.history.get('instance_number', [])
        self.apdu_timeout_cb['values'] = self.history.get('apdu_timeout', [config.DEFAULTS['apdu_timeout']])
        self.bbmd_ip_cb['values'] = self.history.get('bbmd_ip', [config.DEFAULTS['bbmd_ip']])
        self.ip_network_number_cb['values'] = self.history.get('ip_network_number', [config.DEFAULTS['ip_network_number']])
        self.ip_port_cb['values'] = self.history.get('ip_port', [config.DEFAULTS['ip_port']])
        self.bbmd_ttl_cb['values'] = self.history.get('bbmd_ttl', [config.DEFAULTS['bbmd_ttl']])
        self.com_port_cb['values'] = self.history.get('com_port', ['COM1', 'COM2', 'COM3'])
        self.baud_rate_cb['values'] = self.history.get('baud_rate', ['9600', '19200', '38400', '76800'])
        self.mac_address_cb['values'] = self.history.get('mac_address', [])
        self.mstp_instance_cb['values'] = self.history.get('mstp_instance', [])
        self.network_number_cb['values'] = self.history.get('network_number', [])
        self.reset_fields_to_defaults(load_from_history=True)

    def reset_fields_to_defaults(self, load_from_history=False):
        if not load_from_history or not self.bbmd_ip_var.get(): self.bbmd_ip_var.set(config.DEFAULTS['bbmd_ip'])
        if not load_from_history or not self.ip_network_number_var.get(): self.ip_network_number_var.set(config.DEFAULTS['ip_network_number'])
        if not load_from_history or not self.ip_port_var.get(): self.ip_port_var.set(config.DEFAULTS['ip_port'])
        if not load_from_history or not self.apdu_timeout_var.get(): self.apdu_timeout_var.set(config.DEFAULTS['apdu_timeout'])
        if not load_from_history or not self.bbmd_ttl_var.get(): self.bbmd_ttl_var.set(config.DEFAULTS['bbmd_ttl'])
        if not load_from_history or not self.baud_rate_var.get(): self.baud_rate_var.set(config.DEFAULTS['baud_rate'])
        
        if not load_from_history:
            self.read_property_vars = {'obj_type': '8', 'obj_inst': '4000037', 'prop_id': '77'}
            self.write_property_vars = {'obj_type': '8', 'obj_inst': '4000037', 'prop_id': '77', 'value': '0', 'tag': 'REAL (4)', 'priority': '16'}

    def log(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.update_idletasks()

    def set_ui_state_running(self):
        self.ping_button.config(state=tk.DISABLED)
        self.discover_button.config(state=tk.DISABLED)
        self.discover_objects_button.config(state=tk.DISABLED)
        self.read_property_button.config(state=tk.DISABLED)
        self.write_property_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

    def set_ui_state_idle(self):
        self.ping_button.config(state=tk.NORMAL)
        self.discover_button.config(state=tk.NORMAL)
        self.discover_objects_button.config(state=tk.NORMAL if self.last_pinged_device else tk.DISABLED)
        self.read_property_button.config(state=tk.NORMAL)
        self.write_property_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.update_all_states()

    def handle_ping_response(self, stdout, stderr):
        if stderr or not stdout.strip():
            self.last_pinged_device = None
            self.discover_objects_button.config(state=tk.DISABLED)
        else:
            self.last_pinged_device = self.instance_number_var.get() or self.mstp_instance_var.get()
            self.discover_objects_button.config(state=tk.NORMAL)

    def handle_discover_response(self, stdout, stderr):
        if stdout: self.parse_and_populate_device_tree(stdout)

    def handle_discover_objects_response(self, stdout, stderr):
        if stdout: self.parse_and_populate_object_tree(stdout)
    
    def parse_and_populate_device_tree(self, output):
        self.device_tree.delete(*self.device_tree.get_children())
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                instance, ip_address = parts[0], parts[2]
                device_display = f"{instance} ({ip_address})"
                self.device_tree.insert("", "end", text=device_display, iid=instance)

    def on_device_select(self, event):
        selected_item = self.device_tree.focus()
        if selected_item:
            instance = selected_item
            self.last_pinged_device = instance
            self.run_discover_objects()
    
    def parse_and_populate_object_tree(self, output):
        self.object_tree.delete(*self.object_tree.get_children())
        self.object_data.clear()
        object_type_nodes = {}

        try:
            # Isolate the object list from the output
            object_list_section = output[output.index("List of Objects in Test Device:"):]
            
            # Find all object definitions, which are enclosed in curly braces
            object_blocks = re.findall(r'\{\s*(object-identifier:[^\}]+)\}', object_list_section, re.DOTALL)

            for block in object_blocks:
                obj_id_match = re.search(r'object-identifier:\s*\(([^,]+),\s*(\d+)\)', block)
                if obj_id_match:
                    obj_type, obj_inst = obj_id_match.groups()
                    obj_type = obj_type.strip()
                    obj_inst = obj_inst.strip()
                    current_object_id = f"{obj_type}:{obj_inst}"
                    self.object_data[current_object_id] = []

                    if obj_type not in object_type_nodes:
                        object_type_nodes[obj_type] = self.object_tree.insert("", "end", text=obj_type, open=False)
                    self.object_tree.insert(object_type_nodes[obj_type], "end", text=obj_inst, values=(obj_inst,), iid=current_object_id)

                    # Now parse the properties for the current object
                    properties = re.findall(r'([\w-]+):\s*(.+)', block)
                    for prop_name, prop_value in properties:
                        self.object_data[current_object_id].append((prop_name.strip(), prop_value.strip()))

        except (ValueError, IndexError):
            # This will happen if "List of Objects in Test Device:" is not found
            # or if the parsing fails. We can log this or just silently fail.
            # For now, we will just not populate the tree.
            pass

    def on_object_select(self, event):
        self.props_tree.delete(*self.props_tree.get_children())
        selected_id = self.object_tree.focus()
        if selected_id in self.object_data:
            for prop_name, prop_value in self.object_data[selected_id]:
                self.props_tree.insert("", "end", text=prop_name, values=(prop_value,))

    def clear_browser(self):
        self.device_tree.delete(*self.device_tree.get_children())
        self.object_tree.delete(*self.object_tree.get_children())
        self.props_tree.delete(*self.props_tree.get_children())
        self.object_data.clear()

    def stop_current_command(self):
        if self.current_process:
            try:
                self.current_process.terminate()
                self.log("--- Command stopped by user. ---")
            except Exception as e:
                self.log(f"--- Error stopping command: {e} ---")

    def open_read_property_popup(self):
        ui_components.show_read_property_popup(self)

    def open_write_property_popup(self):
        ui_components.show_write_property_popup(self)

    def run_ping(self): bacnet_logic.execute_bacnet_command(self, 'ping')
    def run_discover(self): bacnet_logic.execute_bacnet_command(self, 'discover')
    def run_discover_objects(self): bacnet_logic.execute_bacnet_command(self, 'discover_objects')
    def run_read_property(self): bacnet_logic.execute_bacnet_command(self, 'read')
    def run_write_property(self): bacnet_logic.execute_bacnet_command(self, 'write')

if __name__ == "__main__":
    app = BACnetApp()
    app.mainloop()
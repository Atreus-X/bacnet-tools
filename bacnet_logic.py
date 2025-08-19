# bacnet_logic.py
# This file contains the backend logic for executing BACnet commands.

import os
import subprocess
import re
from tkinter import messagebox
import utils # <-- FIX: Changed import style for robustness

def run_command_in_thread(app_instance, command, cwd, env, callback=None):
    """Starts a new thread to run a command."""
    import threading
    thread = threading.Thread(target=run_command, args=(app_instance, command, cwd, env, callback))
    thread.start()

def run_command(app_instance, command, cwd, env, callback=None):
    """Executes a subprocess command and handles its output."""
    app_instance.after(0, app_instance.set_ui_state_running)
    try:
        app_instance.log(f"Executing: {' '.join(command)}")
        app_instance.current_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        stdout, stderr = app_instance.current_process.communicate(timeout=30)
        if stdout: app_instance.log("--- SUCCESS ---\n" + stdout.strip())
        if stderr: app_instance.log("--- ERROR ---\n" + stderr.strip())
        if callback: app_instance.after(0, callback, stdout, stderr)
    except subprocess.TimeoutExpired:
        app_instance.log("--- ERROR: Command timed out. ---")
        if app_instance.current_process:
            app_instance.current_process.kill()
            app_instance.current_process.communicate()
    except Exception as e:
        if not (app_instance.current_process and app_instance.current_process.poll() is not None):
            app_instance.log(f"--- An unexpected error occurred: {e} ---")
    finally:
        app_instance.current_process = None
        app_instance.after(0, app_instance.set_ui_state_idle)

def execute_bacnet_command(app_instance, command_type):
    """Prepares and initiates a BACnet command."""
    if app_instance.current_process:
        messagebox.showwarning("Busy", "A command is already running.")
        return
    bin_dir = utils.get_resource_path('bin') # <-- FIX: Use module prefix
    if not os.path.exists(bin_dir):
        messagebox.showerror("Error", f"'bin' directory not found at: {bin_dir}")
        return

    env = os.environ.copy()
    transport = app_instance.transport_var.get()
    
    # Set environment variables based on UI state
    if transport == 'ip' or (transport == 'mstp' and app_instance.mstp_mode_var.get() == 'remote'):
        env['BACNET_IP_PORT'] = '0'
        ip_port_value = app_instance.ip_port_var.get()
        if app_instance.interface_var.get(): env['BACNET_IFACE'] = app_instance.interface_var.get().split('(')[-1].replace(')', '')
        if app_instance.bbmd_ip_var.get(): env['BACNET_BBMD_ADDRESS'] = app_instance.bbmd_ip_var.get()
        if app_instance.apdu_timeout_var.get(): env['BACNET_APDU_TIMEOUT'] = app_instance.apdu_timeout_var.get()
        if app_instance.ip_network_number_var.get(): env['BACNET_IP_NETWORK'] = app_instance.ip_network_number_var.get()
        if ip_port_value: env['BACNET_BBMD_PORT'] = ip_port_value
        if app_instance.bbmd_ttl_var.get(): env['BACNET_BBMD_TIMETOLIVE'] = app_instance.bbmd_ttl_var.get()
        
        app_instance.update_history('apdu_timeout', app_instance.apdu_timeout_var.get())
        app_instance.update_history('bbmd_ip', app_instance.bbmd_ip_var.get())
        app_instance.update_history('ip_network_number', app_instance.ip_network_number_var.get())
        app_instance.update_history('ip_port', ip_port_value)
        app_instance.update_history('bbmd_ttl', app_instance.bbmd_ttl_var.get())

    if transport == 'ip':
        device_identifier = app_instance.instance_number_var.get()
        if command_type not in ['discover', 'discover_objects'] and not device_identifier: messagebox.showerror("Error", "Instance number is required for this action."); return
        app_instance.update_history('instance_number', device_identifier)
    elif transport == 'mstp':
        mstp_mode = app_instance.mstp_mode_var.get()
        if mstp_mode == 'local':
            if command_type == 'ping':
                device_identifier = app_instance.mac_address_var.get()
                if not device_identifier: messagebox.showerror("Error", "MAC Address is required for Ping."); return
            elif command_type in ['read', 'write', 'discover_objects']:
                device_identifier = app_instance.mstp_instance_var.get()
                if not device_identifier: messagebox.showerror("Error", "Instance # is required for this action."); return
            
            app_instance.update_history('com_port', app_instance.com_port_var.get())
            app_instance.update_history('baud_rate', app_instance.baud_rate_var.get())
            app_instance.update_history('mac_address', app_instance.mac_address_var.get())
            app_instance.update_history('mstp_instance', app_instance.mstp_instance_var.get())
            if app_instance.com_port_var.get(): env['BACNET_IFACE'] = app_instance.com_port_var.get()
            if app_instance.baud_rate_var.get(): env['BACNET_MSTP_BAUD'] = app_instance.baud_rate_var.get()
        else: # Remote
            if command_type == 'ping':
                device_identifier = app_instance.network_number_var.get()
                if not device_identifier: messagebox.showerror("Error", "Network Number is required for remote discovery."); return
                app_instance.update_history('network_number', device_identifier)
            else:
                device_identifier = app_instance.instance_number_var.get()
                if command_type not in ['discover', 'discover_objects'] and not device_identifier: messagebox.showerror("Error", "Instance # is required for this action.\n(Discover the remote network first to find it)"); return
                app_instance.update_history('instance_number', device_identifier)

    if command_type == 'read': app_instance.update_history('read_property', app_instance.read_property_var.get())
    elif command_type == 'write':
        app_instance.update_history('write_property', app_instance.write_property_var.get())
        app_instance.update_history('write_value', app_instance.write_value_var.get())
        app_instance.update_history('write_tag', app_instance.write_tag_var.get())
        app_instance.update_history('write_priority', app_instance.write_priority_var.get())
    
    app_instance.populate_fields_from_history()
    app_instance.output_text.delete('1.0', tk.END)
    app_instance.log("--- Starting Command ---")
    
    command, callback = None, None
    if command_type == 'discover':
        command = [os.path.join(bin_dir, 'bacwi.exe'), "-1"]
        callback = app_instance.handle_discover_response
    elif command_type == 'ping':
        command = [os.path.join(bin_dir, 'bacwi.exe'), device_identifier]
        callback = app_instance.handle_ping_response
    elif command_type == 'discover_objects':
        command = [os.path.join(bin_dir, 'bacepics.exe'), '-v', app_instance.last_pinged_device]
        callback = app_instance.handle_discover_objects_response
    elif command_type == 'read':
        read_prop_str = app_instance.read_property_var.get()
        if not read_prop_str: messagebox.showerror("Error", "Read Property field cannot be empty."); return
        try: obj_type, obj_inst, prop_id = read_prop_str.split(';')
        except ValueError: messagebox.showerror("Error", "Invalid format for Read Property. Use 'objType;inst;prop'."); return
        command = [os.path.join(bin_dir, 'bacrp.exe'), device_identifier, obj_type, obj_inst, prop_id]
    elif command_type == 'write':
        write_prop_str = app_instance.write_property_var.get()
        value, tag_name, priority = app_instance.write_value_var.get(), app_instance.write_tag_var.get(), app_instance.write_priority_var.get()
        if not all([write_prop_str, value, tag_name, priority]): messagebox.showerror("Error", "All Write Property fields are required."); return
        try: obj_type, obj_inst, prop_id = write_prop_str.split(';')
        except ValueError: messagebox.showerror("Error", "Invalid format for Write Property. Use 'objType;inst;prop'."); return
        tag_value = app_instance.TAG_MAP.get(tag_name)
        if not tag_value: messagebox.showerror("Error", f"Invalid tag name selected: {tag_name}"); return
        command = [os.path.join(bin_dir, 'bacwp.exe'), device_identifier, obj_type, obj_inst, prop_id, priority, "-1", tag_value, value]
    
    if command:
        run_command_in_thread(app_instance, command, bin_dir, env, callback)

# BACnet Tools Wrapper Script
# This script provides a user-friendly interface for the pre-compiled
# BACnet Stack command-line tools (bacwi.exe, bacrp.exe).
#
# Prerequisites:
# 1. Python must be installed.
# 2. The BACnet Stack executables must be downloaded and extracted.
#
# Folder Structure:
# This script assumes it is located in a folder, and the BACnet
# executables are in a 'bin' subfolder.
# C:\BACnet\
# |
# |- bacnet_wrapper.py (this script)
# |
# |- bin\
#    |- bacwi.exe
#    |- bacrp.exe
#    |- ... (other files from the zip)
#
# How to run:
# 1. Ping a device:
#    python bacnet_wrapper.py 192.168.1.55 1001
# 2. Read a property (note the quotes):
#    python bacnet_wrapper.py 192.168.1.55 1001 --read "0;1;85"
# 3. Use a BBMD with a specific network number:
#    python bacnet_wrapper.py 10.0.1.25 2002 --bbmd 10.0.0.1 --bbmd_dnet 101

import sys
import os
import argparse
import subprocess
import ipaddress
import socket # To get local IP addresses

def get_network_interfaces():
    """
    Gets a list of non-loopback IPv4 network interfaces.
    """
    interfaces = []
    try:
        # Use an empty string for the host to get all available addresses
        for info in socket.getaddrinfo(socket.gethostname(), None):
            # We are only interested in IPv4 addresses
            if info[0] == socket.AF_INET:
                ip = info[4][0]
                # Exclude loopback addresses
                if not ip.startswith("127."):
                    interfaces.append(ip)
    except socket.gaierror:
        print("\n[WARNING] Could not determine network interfaces.")
    # Return a list of unique IPs, as some methods might return duplicates
    return list(set(interfaces))

def main():
    """
    Main function to parse arguments and execute BACnet commands.
    """
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="A Python wrapper for BACnet command-line tools.",
        epilog="Example: python %(prog)s 192.168.1.55 1001 --read \"0;1;85\""
    )
    parser.add_argument("ip_address", nargs='?', default=None, help="The IP address of the target BACnet device (used for context, not directly by tools).")
    parser.add_argument("instance_number", nargs='?', default=None, type=int, help="The BACnet device instance number.")
    parser.add_argument("--bbmd", help="IP address of the BBMD for foreign device registration.")
    parser.add_argument("--read", help="Read a property. Format: \"objectType;instance;property\" (e.g., \"0;1;85\")")
    parser.add_argument("--interface", help="IP address of the local network interface to use.")
    parser.add_argument("--bbmd_dnet", help="The destination BACnet network number for the BBMD.")
    
    args = parser.parse_args()
    is_interactive = False

    # --- Determine Mode (Interactive vs. Command-Line) ---
    if args.ip_address is None or args.instance_number is None:
        is_interactive = True
        try:
            print("--- BACnet Tool Wrapper (Interactive Mode) ---")
            ip_input = input("Enter the target BACnet device IP address: ")
            if not ip_input:
                print("\n[ERROR] IP Address is required.")
                return
            args.ip_address = ip_input
            
            instance_input = input("Enter the BACnet device instance number: ")
            if not instance_input:
                print("\n[ERROR] Instance number is required.")
                return
            args.instance_number = int(instance_input)

            if not args.interface:
                interfaces = get_network_interfaces()
                if not interfaces:
                    print("\n[WARNING] No network interfaces found. You may need to specify one manually.")
                    args.interface = input("Enter local interface IP (optional, press Enter to skip): ")
                elif len(interfaces) == 1:
                    args.interface = interfaces[0]
                    print(f"\nUsing only available network interface: {args.interface}")
                else:
                    print("\nPlease select a network interface to use (press Enter for default):")
                    for i, iface in enumerate(interfaces):
                        default_marker = " (default)" if i == 0 else ""
                        print(f"  {i+1}: {iface}{default_marker}")
                    try:
                        choice_str = input(f"Enter choice (1-{len(interfaces)}): ")
                        if not choice_str:
                            args.interface = interfaces[0]
                            print(f"Defaulting to interface: {args.interface}")
                        else:
                            choice = int(choice_str) - 1
                            if 0 <= choice < len(interfaces):
                                args.interface = interfaces[choice]
                            else:
                                print("\n[ERROR] Invalid selection.")
                                return
                    except (ValueError, IndexError):
                        print("\n[ERROR] Invalid selection.")
                        return
            
            args.bbmd = input("Enter BBMD IP address (optional, press Enter to skip): ")
            if args.bbmd:
                args.bbmd_dnet = input("Enter BBMD's destination network number (DNET) (optional, press Enter to skip): ")
            args.read = input("Enter object to read (optional, format: 0;1;85): ")

        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return
        except ValueError:
            print("\n[ERROR] Invalid number format provided.")
            return
    
    # Clean up empty strings from interactive mode
    if not args.interface: args.interface = None
    if not args.bbmd: args.bbmd = None
    if not args.read: args.read = None
    if 'bbmd_dnet' in args and not args.bbmd_dnet: args.bbmd_dnet = None

    if is_interactive:
        script_name = os.path.basename(sys.argv[0])
        command_parts = [
            "python",
            script_name,
            args.ip_address,
            str(args.instance_number)
        ]
        if args.interface:
            command_parts.extend(["--interface", args.interface])
        if args.bbmd:
            command_parts.extend(["--bbmd", args.bbmd])
        if 'bbmd_dnet' in args and args.bbmd_dnet:
            command_parts.extend(["--bbmd_dnet", args.bbmd_dnet])
        if args.read:
            command_parts.extend(["--read", f'"{args.read}"'])
        
        print("\nEquivalent Command-Line:")
        print(" ".join(command_parts))

    # --- Set Environment Variables for BACnet Tools ---
    env = os.environ.copy()
    print("\n--- Configuration ---")
    if args.interface:
        env['BACNET_IFACE'] = args.interface
        print(f"Using Interface: {args.interface}")
    if args.bbmd:
        env['BACNET_BBMD_ADDRESS'] = args.bbmd
        print(f"Using BBMD IP: {args.bbmd}")
        # [MODIFIED] When using a BBMD, explicitly state that registration will occur.
        print("Attempting Foreign Device Registration via BBMD...")
    if 'bbmd_dnet' in args and args.bbmd_dnet:
        env['BACNET_BBMD_DNET'] = args.bbmd_dnet
        print(f"Using BBMD DNET: {args.bbmd_dnet}")

    # [MODIFIED] Increase the APDU timeout to be more patient on routed networks.
    # The default is 3 seconds (3000 ms), which can be too short for BBMD traffic.
    apdu_timeout_ms = 20000 # 20 seconds
    env['BACNET_APDU_TIMEOUT'] = str(apdu_timeout_ms)
    print(f"Using APDU Timeout: {apdu_timeout_ms / 1000} seconds")


    # Determine the path to the executables
    script_dir = os.path.dirname(os.path.realpath(__file__))
    bin_dir = os.path.join(script_dir, 'bin')
    bacwi_path = os.path.join(bin_dir, 'bacwi.exe')
    bacrp_path = os.path.join(bin_dir, 'bacrp.exe')

    if not os.path.exists(bin_dir):
        print(f"\n[ERROR] 'bin' directory not found. Expected at: '{bin_dir}'")
        print("Please ensure the script is in the correct folder structure.")
        return
    if not os.path.exists(bacwi_path) or not os.path.exists(bacrp_path):
        print(f"\n[ERROR] BACnet executables not found in '{bin_dir}'")
        return

    # --- Execute BACnet Who-Is (Ping) ---
    print(f"\nSending Who-Is to discover device {args.instance_number}...")
    
    try:
        ping_command = [bacwi_path, str(args.instance_number)]
        print(f"Executing command: {' '.join(ping_command)}")
        
        # Run the command from within the 'bin' directory.
        # This is crucial for the executables to find their dependent DLLs.
        ping_result = subprocess.run(
            ping_command, 
            capture_output=True, 
            text=True, 
            timeout=30, # A generous timeout for the script itself
            env=env, 
            cwd=bin_dir
        )

        if ping_result.returncode == 0 and str(args.instance_number) in ping_result.stdout:
            print("--- Ping Results ---")
            print("SUCCESS: Device responded to Who-Is.")
            print("\nDevice Details:")
            print(ping_result.stdout.strip())
            
            if args.read:
                print(f"\nAttempting to read property: {args.read}...")
                try:
                    obj_type, obj_inst, prop_id = args.read.replace("\"", "").replace("'", "").split(';')
                    
                    read_command = [bacrp_path, str(args.instance_number), obj_type, obj_inst, prop_id]
                    print(f"Executing command: {' '.join(read_command)}")
                    
                    read_result = subprocess.run(
                        read_command, 
                        capture_output=True, 
                        text=True, 
                        timeout=30, 
                        env=env, 
                        cwd=bin_dir
                    )

                    if read_result.returncode == 0 and read_result.stdout:
                        print("--- Read Success ---")
                        print(f"Value: {read_result.stdout.strip()}")
                    else:
                        print("--- Read Failed ---")
                        error_output = read_result.stderr.strip() if read_result.stderr else "No error details returned."
                        print(f"\n[!] Details from command: {error_output}")
                        print("\n[?] Possible Causes & Suggestions:")
                        if "unknown-property" in error_output.lower():
                            print("  - The Property ID is not valid for this Object Type.")
                        elif "unknown-object" in error_output.lower():
                            print("  - The Object Instance number does not exist on the device.")
                        elif "apdu-timeout" in error_output.lower():
                            print("  - The device became unresponsive after the initial discovery.")
                        else:
                            print("  - The object may not be readable, or a general communication error occurred.")

                except ValueError:
                    print(f"\n[ERROR] Invalid format for read argument: '{args.read}'.")
                    print("          Use \"objectType;instance;property\" (e.g., \"0;1;85\").")
                except subprocess.TimeoutExpired:
                    print("--- Read Failed ---")
                    print("Error: The read property command timed out.")
        else:
            print("--- Ping Results ---")
            print("FAILURE: Device did not respond to Who-Is.")
            error_details = ping_result.stderr.strip() if ping_result.stderr else ping_result.stdout.strip()
            if error_details:
                print(f"\n[!] Details from command: {error_details}")
                print("\n[?] Possible Causes & Suggestions:")
                if "APDU Timeout" in error_details:
                    print("  - The device is offline, powered down, or disconnected from the network.")
                    print("  - The device instance number is incorrect.")
                    print("  - A firewall is blocking UDP port 47808.")
                    if args.bbmd:
                        print(f"  - The BBMD at {args.bbmd} is incorrect, offline, or not configured correctly.")
                        print(f"  - Check the BBMD's network number (DNET) if applicable.")
                elif "Failed to open socket" in error_details or "bind" in error_details:
                     print(f"  - The specified local interface '{args.interface}' may be incorrect or inactive.")
                     print("  - Another application may be using the BACnet port (47808).")
                else:
                    print("  - An unknown network or configuration error occurred. Check all settings.")
            else:
                print("\n[?] No specific error details were returned. Please check basic connectivity and all parameters.")

    except FileNotFoundError:
        print(f"\n[ERROR] Could not execute '{bacwi_path}'. Make sure it exists and is executable.")
    except subprocess.TimeoutExpired:
        print("--- Ping Results ---")
        print("FAILURE: The Who-Is command timed out.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
    finally:
        print("\nScript finished.")

if __name__ == "__main__":
    main()

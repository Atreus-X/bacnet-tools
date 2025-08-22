import BAC0
import asyncio

# --- Set logging to the most detailed level ---
BAC0.log_level('debug')

# --- Configuration ---
LOCAL_IP = '172.31.236.215/16'
BBMD_ADDRESS_AND_PORT = '172.21.136.14:47808'
BBMD_TTL = 3600

TARGET_IP = '172.21.136.6'

# --- Main Script ---
async def main():
    bacnet = None
    try:
        print(f"Connecting to network {LOCAL_IP} via BBMD at {BBMD_ADDRESS_AND_PORT}...")
        
        bacnet = BAC0.connect(
            ip=LOCAL_IP,
            bbmdAddress=BBMD_ADDRESS_AND_PORT,
            bbmdTTL=BBMD_TTL
        )
        print("Connection successful. Registered as a Foreign Device.")

        print(f"\nPinging IP address {TARGET_IP}...")
        
        # This sends the Who-Is request. The response will appear in the DEBUG logs.
        await bacnet.who_is(TARGET_IP)

        print("\nWho-Is sent. Waiting 10 seconds for a response.")
        print("Look for an 'I-Am' message in the detailed log output below...")
        await asyncio.sleep(10)

        print("\n--- Ping test finished. ---")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

    finally:
        if bacnet:
            print("\nDisconnecting...")
            bacnet.disconnect()
        print("Done.")

# --- Standard asyncio entry point ---
if __name__ == "__main__":
    asyncio.run(main())
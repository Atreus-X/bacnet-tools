import asyncio
from bacpypes.core import stop
from bacpypes.app import Application

# This script relies on a bacpypes.ini file in the same directory.

async def main():
    app = None
    try:
        # This single function handles everything: argument parsing,
        # INI file loading, and building the entire BACnet stack.
        app = Application.from_args()
        
        print("Application created and running from bacpypes.ini.")
        print("Registered as a Foreign Device. Listening for I-Am responses for 15 seconds...")
        print("(Responses will be printed by the BACpypes logger below)")

        # The application runs in the background. We just need to wait.
        await asyncio.sleep(15)

        print("\nDiscovery period finished.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if app:
            app.close()
        stop()

if __name__ == "__main__":
    asyncio.run(main())
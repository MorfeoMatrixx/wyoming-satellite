#!/usr/bin/env python3
"""Runs a Wyoming server to control NeoPixel LEDs based on satellite events."""
import argparse
import asyncio
import logging
import time
import sys
import signal
from functools import partial

# Import the LED control class from our new library
from neopixel_wyoming_leds import WyomingNeoPixelLEDs

# Remove pixel_ring import
# from pixel_ring import pixel_ring

from wyoming.event import Event
from wyoming.satellite import (
    SatelliteConnected,
    SatelliteDisconnected,
    StreamingStarted,
    StreamingStopped,
)
from wyoming.server import AsyncEventHandler, AsyncServer
from wyoming.snd import Played
from wyoming.vad import VoiceStarted, VoiceStopped
from wyoming.wake import Detection

_LOGGER = logging.getLogger()

# Global instance of our LED controller
# This makes it accessible within the EventHandler instance
led_controller: WyomingNeoPixelLEDs | None = None

async def main() -> None:
    """Main entry point."""
    global led_controller # Declare global to assign the instance

    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    # Optional: Add arguments for LED configuration if you want to change defaults
    # parser.add_argument("--led-count", type=int, default=16, help="Number of LEDs")
    # parser.add_argument("--led-pin", default="D18", help="GPIO pin (e.g., D18)")
    # parser.add_argument("--led-brightness", type=float, default=0.5, help="LED brightness (0.0-1.0)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    _LOGGER.info("Ready")

    # --- Initialize the LED Controller ---
    try:
        # Pass configuration from args if added to the parser, otherwise use defaults
        led_controller = WyomingNeoPixelLEDs(
            # led_count=args.led_count,
            # led_pin=getattr(board, args.led_pin, board.D18), # Get pin from board module
            # brightness=args.led_brightness
        )
        # Emulate the initial pixel_ring startup sequence
        if led_controller.pixels is not None: # Only if initialization was successful
             led_controller.think() # Pulsing purple
             await asyncio.sleep(3)
             led_controller.off()

    except Exception as e:
        _LOGGER.error(f"Failed to initialize LED controller: {e}")
        # led_controller remains None, the event handler will check

    # Start server
    server = AsyncServer.from_uri(args.uri)

    try:
        # Pass the led_controller instance to the event handler constructor
        await server.run(partial(LEDsEventHandler, args, led_controller=led_controller))
    except asyncio.CancelledError:
        _LOGGER.info("Server task cancelled.")
    except KeyboardInterrupt:
         # Handled by outer asyncio.run wrapper
         pass
    finally:
        _LOGGER.info("Server stopped.")
        # Ensure LEDs are off on exit using the controller's cleanup method
        if led_controller:
            led_controller.cleanup()


class LEDsEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        cli_args: argparse.Namespace,
        *args,
        led_controller: WyomingNeoPixelLEDs | None, # Accept the controller instance
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.client_id = str(time.monotonic_ns())
        self.led_controller = led_controller # Store the instance

        _LOGGER.debug("Client connected: %s", self.client_id)

    async def handle_event(self, event: Event) -> bool:
        """Handle an event from the client."""
        _LOGGER.debug("Received event: %s", event)

        # Use the stored led_controller instance to call methods
        # Check if the controller was initialized successfully
        if self.led_controller is None or self.led_controller.pixels is None:
            _LOGGER.debug("LED controller not available. Skipping LED update.")
            return True # Still process the Wyoming event

        if Detection.is_type(event.type):
            _LOGGER.info("Event: Detection")
            self.led_controller.wakeup()
        elif VoiceStarted.is_type(event.type):
            _LOGGER.info("Event: VoiceStarted")
            self.led_controller.speak() # Emulate speaking state
        elif VoiceStopped.is_type(event.type):
            _LOGGER.info("Event: VoiceStopped")
            # After voice stopped, often returns to listening/thinking or off
            # Let's assume it might go into a "processing/thinking" state
            self.led_controller.think() # Emulate thinking state
        elif StreamingStopped.is_type(event.type):
            _LOGGER.info("Event: StreamingStopped")
            # After streaming stops, it should go idle
            self.led_controller.off() # Turn off LEDs
        elif SatelliteConnected.is_type(event.type):
            _LOGGER.info("Event: SatelliteConnected")
            # Initial connection sequence - handled in main() init
            # Subsequent connections might warrant a different indicator, or just off
            self.led_controller.off()

        elif Played.is_type(event.type):
            _LOGGER.info("Event: Played (Audio Response)")
            self.led_controller.speak() # Emulate speaking during playback
            # The satellite doesn't send a "PlaybackStopped" event usually.
            # You might need a timer here or rely on a subsequent StreamingStopped/VoiceStopped event.
            # For now, we'll just show speak color. Subsequent events will change it.

        elif SatelliteDisconnected.is_type(event.type):
            _LOGGER.info("Event: SatelliteDisconnected")
            self.led_controller.disconnected() # Show disconnected color (Red)

        return True


# --- Signal Handling for Clean Exit ---
def signal_handler(sig, frame):
    """Handle SIGTERM/SIGINT to perform cleanup."""
    _LOGGER.info("Received termination signal (%s). Initiating graceful shutdown.", sig)
    # Stop the asyncio event loop
    loop = asyncio.get_event_loop()
    loop.call_soon_threadsafe(loop.stop) # Signal the event loop to stop

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler) # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # Sent by systemd etc.


if __name__ == "__main__":
    # Configure basic logging
    # Change to DEBUG for verbose logs, including LED state changes from the library
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    _LOGGER.info("Starting NeoPixel LED Control Server for Wyoming Satellite...")

    try:
        # Get the current event loop or create a new one
        loop = asyncio.get_event_loop()
        # Run the main async function until completion or interruption
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        _LOGGER.info("Keyboard interrupt received, shutting down.")
    except Exception as e:
        _LOGGER.exception("An unhandled error occurred.")
    finally:
         _LOGGER.info("Event loop finished.")
         # Final cleanup - ensure LEDs are off and animation thread is stopped
         # This is also handled within the main() finally block, but good practice.
         if led_controller:
             led_controller.cleanup()
         _LOGGER.info("Script exiting.")
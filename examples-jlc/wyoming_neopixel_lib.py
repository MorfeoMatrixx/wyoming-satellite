# neopixel_wyoming_leds.py
import time
import board  # For GPIO pins
import neopixel # For WS2812 control
import threading
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

# --- NeoPixel Configuration ---
# (Moved from main script, can be passed to class init if preferred)
DEFAULT_LED_COUNT = 16
DEFAULT_LED_PIN = board.D18  # GPIO pin connected to the pixels (e.g., board.D18 for GPIO18)
DEFAULT_LED_BRIGHTNESS = 0.5 # Global brightness (0.0 to 1.0)
DEFAULT_LED_ORDER = neopixel.GRB # Order of pixel colors (neopixel.GRB or neopixel.RGB)

# --- State Colors ---
COLOR_OFF = (0, 0, 0)
COLOR_WAKEUP = (255, 255, 255)  # White flash
COLOR_LISTENING = (0, 0, 255)   # Blue for spinning
COLOR_THINKING = (128, 0, 128)  # Purple for pulsing
COLOR_SPEAKING = (0, 255, 0)   # Green solid
COLOR_DISCONNECTED = (255, 0, 0) # Red solid

class WyomingNeoPixelLEDs:
    """Controls NeoPixel LEDs based on Wyoming Satellite states."""

    def __init__(
        self,
        led_count: int = DEFAULT_LED_COUNT,
        led_pin = DEFAULT_LED_PIN,
        brightness: float = DEFAULT_LED_BRIGHTNESS,
        pixel_order = DEFAULT_LED_ORDER
    ):
        self.led_count = led_count
        self.led_pin = led_pin
        self.brightness = brightness
        self.pixel_order = pixel_order
        self.pixels: neopixel.NeoPixel | None = None
        self._animation_thread: threading.Thread | None = None
        self._stop_animation = False

        self._initialize_pixels()

    def _initialize_pixels(self):
        """Initializes the NeoPixel strip."""
        try:
            # The NeoPixel library uses rpi_ws281x internally on RPi, using DMA.
            # auto_write=False means we need to call pixels.show() after setting pixels.
            self.pixels = neopixel.NeoPixel(
                self.led_pin,
                self.led_count,
                brightness=self.brightness,
                auto_write=False,
                pixel_order=self.pixel_order
            )
            _LOGGER.info(f"NeoPixel strip initialized with {self.led_count} LEDs on GPIO {self.led_pin}.")
            # Initially turn off all LEDs
            self.pixels.fill(COLOR_OFF)
            self.pixels.show()

        except Exception as e:
            _LOGGER.error(f"Error initializing NeoPixels: {e}")
            _LOGGER.error("Ensure libraries are installed, GPIO pin is correct, and you have power/ground connected.")
            self.pixels = None # Disable NeoPixel control if initialization fails

    def _stop_current_animation(self):
        """Sets the stop flag and waits for the current animation thread to finish."""
        if self._animation_thread and self._animation_thread.is_alive():
            _LOGGER.debug("Stopping current animation...")
            self._stop_animation = True
            # Use a timeout in join in case thread is stuck
            self._animation_thread.join(timeout=1.0)
            if self._animation_thread.is_alive():
                _LOGGER.warning("Animation thread did not stop gracefully.")
            self._stop_animation = False  # Reset flag for the next animation
            self._animation_thread = None  # Clear reference
            _LOGGER.debug("Animation stop requested.")

    async def _async_neopixel_fill(self, color):
        """Helper async function to fill pixels - avoids blocking in asyncio tasks."""
        if self.pixels:
            self.pixels.fill(color)
            self.pixels.show()
        _LOGGER.debug(f"Pixels filled with {color}")

    # --- Public Methods for LED Effects (Called by event handler) ---

    def off(self):
        """Turns all LEDs off and stops any running animation."""
        self._stop_current_animation()
        if self.pixels:
            self.pixels.fill(COLOR_OFF)
            self.pixels.show()
        _LOGGER.debug("LED State: Off")

    def wakeup(self):
        """Briefly flashes LEDs white."""
        self._stop_current_animation()
        if self.pixels:
            _LOGGER.debug("LED State: Wakeup (Flash)")
            self.pixels.fill(COLOR_WAKEUP)
            self.pixels.show()
            # Schedule a task to turn them off after a short delay
            # Need to get the running event loop
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(
                    asyncio.create_task, self._async_neopixel_fill(COLOR_OFF)
                )
            except RuntimeError:
                 _LOGGER.warning("Cannot schedule async task from thread. Skipping flash off.")
                 # If called from a thread where asyncio loop isn't running/accessible

    def listen(self):
        """Starts a spinning blue animation in a background thread."""
        self._stop_current_animation()
        if self.pixels:
            _LOGGER.debug("LED State: Listening (Spin)")
            # The animation loop is blocking (uses time.sleep), so run it in a thread
            self._animation_thread = threading.Thread(target=self._listen_animation_thread, daemon=True)
            self._animation_thread.start()

    def think(self):
        """Starts a pulsing purple animation in a background thread."""
        self._stop_current_animation()
        if self.pixels:
            _LOGGER.debug("LED State: Thinking (Pulse)")
            # The animation loop is blocking (uses time.sleep), so run it in a thread
            self._animation_thread = threading.Thread(target=self._think_animation_thread, daemon=True)
            self._animation_thread.start()

    def speak(self):
        """Sets LEDs to solid green (simplified)."""
        self._stop_current_animation()
        if self.pixels:
            _LOGGER.debug("LED State: Speaking (Solid)")
            self.pixels.fill(COLOR_SPEAKING)
            self.pixels.show()

    def disconnected(self):
        """Sets LEDs to solid red."""
        self._stop_current_animation()
        if self.pixels:
            _LOGGER.debug("LED State: Disconnected (Solid Red)")
            self.pixels.fill(COLOR_DISCONNECTED)
            self.pixels.show()

    def cleanup(self):
        """Ensures animations are stopped and LEDs are turned off."""
        _LOGGER.info("Cleaning up NeoPixel LEDs...")
        self._stop_current_animation()
        if self.pixels:
            self.pixels.fill(COLOR_OFF)
            self.pixels.show()
        _LOGGER.info("NeoPixel cleanup complete.")

    # --- Animation Implementations (Run in separate threads) ---
    # These methods contain blocking loops (time.sleep) suitable for threads

    def _listen_animation_thread(self):
        """Spinning animation loop for a thread."""
        speed = 0.05 # Animation speed (lower is faster)
        head = 0 # Position of the main "head" of the spinner
        tail = 3 # Length of the trailing pixels

        _LOGGER.debug("Starting listen animation thread...")
        while not self._stop_animation:
            if self.pixels is None: break # Stop if pixels weren't initialized

            # Clear previous frame (optional, depends on animation style)
            self.pixels.fill(COLOR_OFF)

            # Draw the spinning segment
            for i in range(tail):
                # Calculate pixel index wrapping around the strip
                pixel_index = (head - i + self.led_count) % self.led_count
                # Fade the tail pixels
                fade_factor = (tail - i) / tail # Fades from 1.0 to 0.0
                color = (
                    int(COLOR_LISTENING[0] * fade_factor),
                    int(COLOR_LISTENING[1] * fade_factor),
                    int(COLOR_LISTENING[2] * fade_factor)
                )
                self.pixels[pixel_index] = color

            # neopixel library is generally thread-safe for .fill() and .show()
            # because it prepares the buffer and then sends it via DMA/SPI.
            self.pixels.show()

            head = (head + 1) % self.led_count # Move the head
            time.sleep(speed)

        _LOGGER.debug("Listen animation thread stopping.")
        # Clean up - turn off LEDs when animation stops
        if self.pixels:
             self.pixels.fill(COLOR_OFF)
             self.pixels.show()


    def _think_animation_thread(self):
        """Pulsing brightness animation loop for a thread."""
        pulse_speed = 0.02 # Speed of brightness change (lower is faster)
        direction = 1 # 1 for increasing brightness, -1 for decreasing
        brightness_level = 0 # Current brightness (0-255 range for calculation)

        _LOGGER.debug("Starting think animation thread...")
        while not self._stop_animation:
            if self.pixels is None: break # Stop if pixels weren't initialized

            # Calculate color with pulsing brightness
            # Map 0-255 to 0-1.0 for the neopixel library's fill/set
            current_brightness = brightness_level / 255.0
            # Ensure calculated brightness is within the global limit
            current_brightness = min(current_brightness, self.brightness)

            # Calculate the actual color values based on the pulse brightness
            pulsing_color = (
                int(COLOR_THINKING[0] * current_brightness),
                int(COLOR_THINKING[1] * current_brightness),
                int(COLOR_THINKING[2] * current_brightness)
            )

            self.pixels.fill(pulsing_color)
            self.pixels.show()

            # Update brightness level and direction
            brightness_level += direction * 5 # Adjust step size (5 here)
            if brightness_level >= 255:
                brightness_level = 255
                direction = -1 # Start decreasing
            elif brightness_level <= 0:
                brightness_level = 0
                direction = 1 # Start increasing

            time.sleep(pulse_speed)

        _LOGGER.debug("Think animation thread stopping.")
        # Clean up
        if self.pixels:
            self.pixels.fill(COLOR_OFF)
            self.pixels.show()

# Example usage within this file (optional, for testing the class)
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     led_controller = WyomingNeoPixelLEDs(led_count=16, led_pin=board.D18, brightness=0.3)
#     try:
#         print("Testing animations...")
#         led_controller.wakeup()
#         time.sleep(1)
#         led_controller.listen()
#         time.sleep(5)
#         led_controller.think()
#         time.sleep(5)
#         led_controller.speak()
#         time.sleep(3)
#         led_controller.disconnected()
#         time.sleep(3)
#     except KeyboardInterrupt:
#         pass
#     finally:
#         led_controller.cleanup()
#         print("Test finished.")
"""Support for driving a NeoPixel ring with Wyoming satellite events.

The API mirrors the external ``pixel_ring`` package that is used by the
``usbmic_service.py`` example but adapts the behaviour for a 12 pixel
WS2812A ring that is commonly bundled with Google Voice HAT style
hardware.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence, Tuple

RGBColor = Tuple[int, int, int]


@dataclass(slots=True)
class Palette:
    """Palette used for the various effects."""

    primary: RGBColor
    secondary: RGBColor


def _int_to_rgb(value: int) -> RGBColor:
    """Convert an integer ``0xRRGGBB`` colour to an ``(r, g, b)`` tuple."""

    red = (value >> 16) & 0xFF
    green = (value >> 8) & 0xFF
    blue = value & 0xFF
    return (red, green, blue)


def _ensure_rgb(value: int | Sequence[int]) -> RGBColor:
    """Validate and normalise a colour specification."""

    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        if len(value) != 3:
            raise ValueError("RGB sequences must contain exactly three items")
        return (int(value[0]), int(value[1]), int(value[2]))

    if isinstance(value, int):
        return _int_to_rgb(value)

    raise TypeError("Colour must be an int or a sequence of three integers")


class NeoPixelRing:
    """Convenience helper around :class:`neopixel.NeoPixel`.

    The class runs the more dynamic animations in a background thread so it can
    be interacted with from asynchronous event loops without blocking them.
    """

    def __init__(
        self,
        *,
        pin=None,
        pixel_count: int = 12,
        brightness: float = 0.4,
        pixel_order: str | None = None,
    ) -> None:
        if pin is None:
            import board  # type: ignore

            pin = board.D18

        import neopixel  # type: ignore

        kwargs = {"auto_write": False, "brightness": brightness}
        if pixel_order is not None:
            kwargs["pixel_order"] = pixel_order

        self._pixels = neopixel.NeoPixel(pin, pixel_count, **kwargs)
        self._pixel_count = pixel_count
        self._palette = Palette(primary=_int_to_rgb(0x0080FF), secondary=_int_to_rgb(0x007A37))
        self._effect_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_color_palette(self, primary: int | Sequence[int], secondary: int | Sequence[int]) -> None:
        """Set the colours used by the animations."""

        self._palette = Palette(primary=_ensure_rgb(primary), secondary=_ensure_rgb(secondary))

    def wakeup(self, *, duration: float | None = 2.0) -> None:
        """Show a wake-up animation."""

        self._start_effect(self._wakeup_frame, interval=0.08, duration=duration)

    def think(self, *, duration: float | None = None) -> None:
        """Show a waiting/"thinking" animation."""

        self._start_effect(self._think_frame, interval=0.12, duration=duration)

    def speak(self) -> None:
        """Show a solid colour indicating that speech is being recorded."""

        self._stop_effect()
        self._fill(self._palette.primary)

    def spin(self, *, duration: float | None = 1.5) -> None:
        """Show a short spinner animation, useful when processing ends."""

        self._start_effect(self._spin_frame, interval=0.06, duration=duration)

    def mono(self, color: int | Sequence[int]) -> None:
        """Display a single colour on the whole ring."""

        self._stop_effect()
        self._fill(_ensure_rgb(color))

    def pulse(self, color: int | Sequence[int], *, duration: float = 1.5) -> None:
        """Pulse a colour once."""

        rgb = _ensure_rgb(color)
        self._start_effect(lambda step: self._pulse_frame(step, rgb), interval=0.05, duration=duration)

    def off(self) -> None:
        """Turn off all LEDs."""

        self._stop_effect()
        self._fill((0, 0, 0))

    def deinit(self) -> None:
        """Stop animations and release the pixel bus."""

        self.off()
        close = getattr(self._pixels, "deinit", None)
        if callable(close):
            close()

    # ------------------------------------------------------------------
    # Animation helpers
    # ------------------------------------------------------------------
    def _start_effect(
        self,
        frame_generator: Callable[[int], List[RGBColor]],
        *,
        interval: float,
        duration: float | None,
    ) -> None:
        self._stop_effect()
        self._stop_event.clear()

        def runner() -> None:
            start = time.monotonic()
            step = 0
            while not self._stop_event.is_set():
                colors = frame_generator(step)
                self._apply_colors(colors)
                step += 1
                if duration is not None and time.monotonic() - start >= duration:
                    break
                if self._stop_event.wait(interval):
                    break

            if not self._stop_event.is_set():
                self._apply_colors([(0, 0, 0)] * self._pixel_count)

        self._effect_thread = threading.Thread(target=runner, daemon=True)
        self._effect_thread.start()

    def _stop_effect(self) -> None:
        if self._effect_thread is None:
            return

        self._stop_event.set()
        self._effect_thread.join()
        self._effect_thread = None
        self._stop_event.clear()

    def _fill(self, color: RGBColor) -> None:
        self._apply_colors([color] * self._pixel_count)

    def _apply_colors(self, colors: Iterable[RGBColor]) -> None:
        with self._lock:
            for index, color in enumerate(colors):
                if index >= self._pixel_count:
                    break
                self._pixels[index] = color
            self._pixels.show()

    # ------------------------------------------------------------------
    # Frame generators
    # ------------------------------------------------------------------
    def _wakeup_frame(self, step: int) -> List[RGBColor]:
        progress = step % (self._pixel_count * 2)
        lit = min(progress, self._pixel_count)
        colors: List[RGBColor] = []
        for index in range(self._pixel_count):
            if index < lit:
                colors.append(self._palette.primary)
            else:
                colors.append((0, 0, 0))
        return colors

    def _think_frame(self, step: int) -> List[RGBColor]:
        offset = step % self._pixel_count
        colors: List[RGBColor] = []
        for index in range(self._pixel_count):
            distance = (index - offset) % self._pixel_count
            fade = max(0.0, 1.0 - (distance / (self._pixel_count / 2)))
            colors.append(self._scale_color(self._palette.secondary, fade * 0.5))
        return colors

    def _spin_frame(self, step: int) -> List[RGBColor]:
        position = step % self._pixel_count
        colors: List[RGBColor] = []
        for index in range(self._pixel_count):
            if index == position:
                colors.append(self._palette.primary)
            else:
                colors.append((0, 0, 0))
        return colors

    def _pulse_frame(self, step: int, color: RGBColor) -> List[RGBColor]:
        cycle = 40
        phase = step % cycle
        if phase < cycle / 2:
            level = phase / (cycle / 2)
        else:
            level = 1 - ((phase - (cycle / 2)) / (cycle / 2))
        scaled = self._scale_color(color, level)
        return [scaled] * self._pixel_count

    @staticmethod
    def _scale_color(color: RGBColor, factor: float) -> RGBColor:
        r, g, b = color
        return (int(r * factor), int(g * factor), int(b * factor))

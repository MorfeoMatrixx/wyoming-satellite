#!/usr/bin/env python3
"""Control a WS2812 NeoPixel ring from Wyoming satellite events."""
import argparse
import asyncio
import logging
import time
from functools import partial

from typing import Any

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

from wyoming_satellite.neopixel_ring import NeoPixelRing

_LOGGER = logging.getLogger(__name__)


def _parse_color(value: str) -> int:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if value.startswith("0x"):
        return int(value, 16)
    return int(value, 16)


def _resolve_pin(value: str) -> Any:
    """Resolve a command-line pin description to a ``board`` pin object."""

    value = value.strip()
    if value.lower().startswith("board."):
        value = value.split(".", maxsplit=1)[1]

    try:
        import board  # type: ignore
    except ImportError as exc:  # pragma: no cover - import error is surfaced to user
        raise RuntimeError("The 'board' module from adafruit-blinka is required") from exc

    candidates = []
    direct = value
    if direct:
        candidates.append(direct)
        direct_upper = direct.upper()
        if direct_upper != direct:
            candidates.append(direct_upper)

    upper = value.upper()
    if upper.startswith("GPIO"):
        suffix = upper[4:]
        candidates.extend([f"GPIO{suffix}", f"D{suffix}"])
    elif upper.startswith("D") and upper[1:].isdigit():
        suffix = upper[1:]
        candidates.append(f"GPIO{suffix}")
    elif upper.isdigit():
        candidates.extend([f"D{upper}", f"GPIO{upper}"])

    for candidate in candidates:
        if hasattr(board, candidate):
            return getattr(board, candidate)

    raise argparse.ArgumentTypeError(
        f"Unknown board pin '{value}'. Try values like 'D18', 'GPIO18', or '18'."
    )


async def main() -> None:
    """Main entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument("--pixels", type=int, default=12, help="Number of LEDs in the ring")
    parser.add_argument(
        "--brightness",
        type=float,
        default=0.4,
        help="Brightness value passed to neopixel.NeoPixel",
    )
    parser.add_argument(
        "--pin",
        default="D18",
        help="Board pin driving the ring (e.g. 'D18', 'GPIO18', or '18'; default: D18)",
    )
    parser.add_argument(
        "--primary-color",
        default="0x0080FF",
        help="Hex colour used for the main animation (default: 0x0080FF)",
    )
    parser.add_argument(
        "--secondary-color",
        default="0x007A37",
        help="Hex colour used for the secondary animation (default: 0x007A37)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    _LOGGER.info("Initialising NeoPixel ring")

    pin = _resolve_pin(args.pin)

    ring = NeoPixelRing(pin=pin, pixel_count=args.pixels, brightness=args.brightness)
    ring.set_color_palette(_parse_color(args.primary_color), _parse_color(args.secondary_color))

    # Show a short boot sequence to indicate the controller is running
    ring.pulse(_parse_color(args.primary_color), duration=1.0)
    await asyncio.sleep(1.0)
    ring.off()

    _LOGGER.info("Ready")

    server = AsyncServer.from_uri(args.uri)

    try:
        await server.run(partial(LEDsEventHandler, args, ring))
    except KeyboardInterrupt:
        pass
    finally:
        ring.deinit()


class LEDsEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        cli_args: argparse.Namespace,
        ring: NeoPixelRing,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.ring = ring
        self.client_id = str(time.monotonic_ns())

        _LOGGER.debug("Client connected: %s", self.client_id)

    async def handle_event(self, event: Event) -> bool:
        _LOGGER.debug(event)

        if Detection.is_type(event.type):
            _LOGGER.debug("Detection")
            self.ring.wakeup()
        elif VoiceStarted.is_type(event.type):
            _LOGGER.debug("VoiceStarted")
            self.ring.speak()
        elif VoiceStopped.is_type(event.type):
            _LOGGER.debug("VoiceStopped")
            self.ring.spin()
        elif StreamingStarted.is_type(event.type):
            _LOGGER.debug("StreamingStarted")
            self.ring.speak()
        elif StreamingStopped.is_type(event.type):
            _LOGGER.debug("StreamingStopped")
            self.ring.off()
        elif SatelliteConnected.is_type(event.type):
            _LOGGER.debug("SatelliteConnected")
            self.ring.think(duration=2.0)
        elif Played.is_type(event.type):
            _LOGGER.debug("Played")
            self.ring.off()
        elif SatelliteDisconnected.is_type(event.type):
            _LOGGER.debug("SatelliteDisconnected")
            self.ring.mono(0xFF0000)

        return True


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

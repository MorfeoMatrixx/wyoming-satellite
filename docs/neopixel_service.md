# NeoPixel LED Service

This guide explains how to run `examples/neopixel_service.py` so a Wyoming
satellite can drive a WS2812/WS2812A NeoPixel ring such as the 12 LED ring
bundled with Google Voice HAT hardware.

## Prerequisites

1. Complete the main [installation](../README.md#installation) steps and set up
a Python virtual environment for the satellite.
2. Install the NeoPixel driver:

   ```sh
   .venv/bin/pip install 'adafruit-circuitpython-neopixel'
   ```

   The package pulls in `adafruit-blinka`, which provides the `board` module
   used to address the Raspberry Pi's GPIO pins.

3. Connect your NeoPixel ring to the Raspberry Pi. The default wiring expects
   the ring's data pin to be connected to GPIO18 (physical pin 12).

## Running the service manually

From the project root, start the service and point it at the same Wyoming
endpoint that your satellite uses for events:

```sh
.venv/bin/python examples/neopixel_service.py \
  --uri 'unix:///tmp/wyoming.sock' \
  --pin GPIO18 \
  --pixels 12 \
  --brightness 0.4
```

Key options:

- `--pin` chooses the GPIO that drives the LED data line. Values such as
  `D18`, `GPIO18`, or `18` are all accepted and map to `board.D18`.
- `--pixels` sets the number of LEDs in your ring.
- `--primary-color` and `--secondary-color` configure the animation colours.

Run `examples/neopixel_service.py --help` to see the full list of options.

## Creating a systemd service

To have the LED feedback start automatically, create the systemd unit
`/etc/systemd/system/wyoming-neopixel.service` with the contents below (adjust
paths to match your installation directory and user):

```ini
[Unit]
Description=Wyoming NeoPixel LED feedback
After=network-online.target
Requires=wyoming-satellite.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/wyoming-satellite
ExecStart=/home/pi/wyoming-satellite/.venv/bin/python \
  /home/pi/wyoming-satellite/examples/neopixel_service.py \
  --uri unix:///tmp/wyoming.sock \
  --pin GPIO18 \
  --pixels 12
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now wyoming-neopixel.service
```

The LEDs will now respond to the satellite's wake word, speech, and playback
states using the animations provided by `NeoPixelRing`.

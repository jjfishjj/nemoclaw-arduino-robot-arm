# EdgeSense ESP32 Firmware

PlatformIO firmware for ESP32 DevKit V1 with BME280 and MPU6050 over I²C.

## Wiring

| Signal | ESP32 | BME280 | MPU6050 |
|---|---|---|---|
| Power | 3V3 | VIN/3V3 | VCC |
| Ground | GND | GND | GND |
| I²C SDA | GPIO 21 | SDA | SDA |
| I²C SCL | GPIO 22 | SCL | SCL |

Confirm the actual breakout-board voltage and I²C address before power-on.

## Configure and build

Edit `include/config.h` with local Wi-Fi, broker address and device ID. Never commit production credentials.

```bash
cd firmware
../.venv/bin/pio run
```

Upload and monitor when a board is connected:

```bash
../.venv/bin/pio run --target upload
../.venv/bin/pio device monitor
```

Hardware upload is not part of the local software-only verification.

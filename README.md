# NemoClaw × Arduino Robot Arm

A safety-first reference project that lets a NemoClaw/OpenClaw agent control a
four-servo Arduino robot arm through a narrow, auditable host bridge.

> **Status:** prototype. NemoClaw itself is currently alpha software. Always test
> in mock mode first and keep a physical emergency stop within reach.

## Architecture

```text
User → NemoClaw sandbox → OpenClaw skill → HTTP allowlist → host bridge
                                                        ↓
                                               validation + rate limit
                                                        ↓
                                               USB serial → Arduino → servos
```

NemoClaw does not directly access USB. The bridge stays on the host and exposes
only five commands: `arm`, `disarm`, `move`, `home`, and `stop`. Movement is
blocked until explicitly armed, joint angles are bounded twice (host and
firmware), and mock mode is the default.

## Hardware

- Arduino Uno/Nano-compatible board
- 4-axis hobby servo arm (base, shoulder, elbow, gripper)
- External regulated 5–6 V servo power supply
- Common ground between the servo supply and Arduino
- Physical emergency-stop/power-cut switch (strongly recommended)

Default signal pins are D3, D5, D6, and D9. **Do not power multiple servos from
the Arduino 5 V pin.** Adjust pins and mechanical limits in
`firmware/robot_arm/robot_arm.ino` for your hardware.

Follow the [hardware setup and first-motion checklist](docs/hardware-setup.md)
before connecting servo power. It includes the wiring table, calibration sketch,
normally-closed interlock, watchdog, and staged first-motion procedure.

## 1. Try it safely in mock mode

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
arm-bridge
```

In a second terminal:

```bash
armctl arm
armctl move --base 120 --shoulder 80 --elbow 100 --gripper 60
armctl home
armctl disarm
```

## 2. Connect the Arduino

1. Install the ArduinoJson library in Arduino IDE.
2. Upload `firmware/robot_arm/robot_arm.ino`.
3. Find the serial port (`/dev/ttyACM0` on many Linux systems or
   `/dev/cu.usbmodem*` on macOS).
4. Start the real bridge with an authentication token:

```bash
export ARM_BRIDGE_TOKEN='replace-with-a-long-random-value'
arm-bridge --serial /dev/ttyACM0
```

Keep the bridge bound to `127.0.0.1`. If NemoClaw runs in a VM/container, expose
it only through the OpenShell network policy—never directly to your LAN or the
internet.

## 3. Add the OpenClaw skill

Copy `openclaw-skill` into the OpenClaw workspace's skills directory. Make the
helper executable and set the bridge URL/token through the sandbox's approved
secret/environment mechanism:

```bash
chmod +x openclaw-skill/scripts/armctl
```

Allow only the bridge endpoint in the NemoClaw/OpenShell network policy. The
exact policy commands can change while NemoClaw is in alpha, so follow the
version-matched [NemoClaw network-policy documentation](https://docs.nvidia.com/nemoclaw/latest/).

Example request to the agent:

> Move the robot arm base to 120°, shoulder to 80°, elbow to 100°, and keep the
> gripper at 60°. Ask me to confirm the workspace is clear before moving.

## Direct API

```bash
curl -X POST http://127.0.0.1:8765/command \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ARM_BRIDGE_TOKEN" \
  -d '{"command":"move","joints":{"base":120},"duration_ms":800}'
```

## Safety model

- Safe mock mode by default; serial access must be explicitly enabled.
- Explicit arming before movement and automatic disarm after `stop`.
- Joint allowlist, angle bounds, payload limit, and command rate limiting.
- Firmware repeats joint-bound checks; smooth interpolation reduces sudden moves.
- A D7 hardware interlock and five-second firmware watchdog detach servo outputs.
- Host-only bind by default and optional bearer-token authentication.

This is not safety-certified. Add hardware limit switches, current sensing, a
watchdog, collision detection, and a real emergency stop before operating near
people or valuable equipment.

## Development

```bash
python -m pytest
```

## Roadmap

- Add camera-based object selection and human confirmation.
- Add named, reviewed motion recipes instead of free-form joint commands.
- Add ROS 2 / Isaac Sim adapter for simulation before physical execution.
- Add telemetry, timeouts, and hardware watchdog support.

## References

- [NVIDIA NemoClaw](https://github.com/NVIDIA/NemoClaw)
- [NemoClaw documentation](https://docs.nvidia.com/nemoclaw/latest/)

## License

MIT

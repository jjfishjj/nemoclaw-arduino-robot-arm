# NemoClaw C1: authenticated host bridge

C1 keeps Arduino and USB outside the sandbox. OpenClaw can make one audited
request: `POST http://<host-ip>:8765/command` via `/usr/bin/curl`.

## 1. Start the host bridge

Find the host IP that the OpenShell gateway can reach. Do not use `127.0.0.1`,
`localhost`, or a public interface. Generate and protect a token:

```bash
umask 077
openssl rand -hex 32 > /tmp/arduino-arm-token
python -m arm_bridge.secure_server \
  --host 192.168.1.50 \
  --token-file /tmp/arduino-arm-token
```

The command above stays in mock mode. For real hardware, add the serial port,
`--allow-real-motion`, and keep the startup checklist enabled by default:

```bash
python -m arm_bridge.secure_server \
  --host 192.168.1.50 \
  --token-file /tmp/arduino-arm-token \
  --serial /dev/ttyACM0 \
  --allow-real-motion
```

Use the host firewall to allow port 8765 only from the OpenShell bridge subnet.
Bearer authentication is defense in depth, not a replacement for that firewall.

## 2. Preview and apply the custom preset

Confirm the actual curl path inside the sandbox:

```bash
nemoclaw my-assistant exec -- which curl
```

Preview first. The script stops if NemoClaw rejects the policy:

```bash
python scripts/configure_nemoclaw_c1.py my-assistant \
  --host 192.168.1.50 \
  --request-binary /usr/bin/curl
```

After reviewing the exact host, port, method, path, and binary, apply it:

```bash
python scripts/configure_nemoclaw_c1.py my-assistant \
  --host 192.168.1.50 \
  --request-binary /usr/bin/curl \
  --apply
```

The custom preset is recorded by NemoClaw and replayed on rebuild. It allows no
GET requests, wildcard paths, other ports, or other requesting binaries.

## 3. Install the OpenClaw skill and token

Place `openclaw-skill` in the sandbox OpenClaw workspace's skills directory.
Create a mode-0600 token file inside the sandbox and set these variables through
the sandbox's approved environment/configuration mechanism:

```bash
export ARM_BRIDGE_URL=http://192.168.1.50:8765
export ARM_BRIDGE_TOKEN_FILE=/sandbox/.secrets/arduino-arm-token
```

The agent necessarily needs permission to invoke the bridge, so it can use the
token. The network policy limits where that token can be sent; do not widen the
egress policy or reuse this token for any other service.

## 4. Verify without moving hardware

Keep the bridge in mock mode and run inside the sandbox:

```bash
openclaw-skill/scripts/armctl startup_check
openclaw-skill/scripts/armctl arm
openclaw-skill/scripts/armctl move '{"base":95}' 2000
openclaw-skill/scripts/armctl stop
```

Also verify negative cases: GET `/health`, another path, and another binary must
remain blocked by policy. Run `openshell term` to inspect denied requests.

## Removal

```bash
nemoclaw my-assistant policy-remove arduino-arm-bridge --yes
```

Then stop the host bridge and delete/rotate the dedicated token.

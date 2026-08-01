# Localhost safety console

The B1 console is a separate localhost-only process. It reads the bridge token
on the server, then gives the browser an unrelated, one-hour HttpOnly session
cookie after a one-time terminal pairing code is entered.

## Run in mock mode

Use two terminals and the same dedicated token:

```bash
export ARM_BRIDGE_TOKEN="$(openssl rand -hex 32)"
arm-bridge --require-startup-checklist
```

```bash
export ARM_BRIDGE_TOKEN='copy-the-same-value-from-terminal-one'
python -m arm_bridge.console
```

Open `http://127.0.0.1:8780` and enter the six-digit code printed by the console.

For a token file instead of an environment variable:

```bash
python -m arm_bridge.console --token-file /path/to/mode-0600-token
```

Use `--bridge-url http://<openshell-reachable-host-ip>:8765` when the C1 bridge
is bound to a specific host address rather than loopback.

## Safety behavior

- The console always binds exactly `127.0.0.1`; there is no public-bind option.
- The bridge bearer token never appears in HTML, JavaScript, cookies, or browser storage.
- Pairing codes are single-use and lock after eight failures; sessions expire after one hour.
- Mutating requests require an exact localhost Origin and JSON content type.
- Moving sliders changes only a target preview; movement needs a separate click.
- ARM stays disabled until the bridge reports the startup checklist complete.
- HOME and MOVE stay disabled unless the bridge reports armed state.
- STOP remains available and latches E-STOP in the bridge safety controller.

The browser console is not a certified safety control. The physical latching
power E-STOP remains the primary emergency stop.

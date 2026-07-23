# Hardware setup and first-motion checklist

This guide assumes a four-servo hobby arm and an Arduino Uno or Nano. Servo
wire colors vary, so verify the datasheet before applying power.

## Wiring

| Joint | Arduino signal | Servo power | Servo ground |
|---|---:|---|---|
| Base | D3 | External regulated 5–6 V | Common ground |
| Shoulder | D5 | External regulated 5–6 V | Common ground |
| Elbow | D6 | External regulated 5–6 V | Common ground |
| Gripper | D9 | External regulated 5–6 V | Common ground |
| Hardware interlock | D7 to GND through NC switch | — | Arduino GND |

```text
                  +---------------- servo V+
5–6 V supply + ---+---------------- servo V+
                  +---------------- servo V+
                  +---------------- servo V+

Supply GND --------+---------------- servo GND ×4
                   +---------------- Arduino GND

Arduino D3/D5/D6/D9 ---------------- servo signal ×4
Arduino D7 -------- normally-closed interlock -------- GND
```

The D7 interlock is a logic-level secondary stop. The primary emergency stop
should be a normally-closed, latching switch that physically interrupts servo
power. Do not route servo current through a small signal switch.

## Power sizing

Use the servo datasheets' stall-current values. Size the supply and wiring for
the sum of all possible simultaneous stall currents, with margin. Never power
four servos from the Arduino 5 V pin or USB port.

## Mechanical calibration

1. Disconnect servo horns from the arm links and remove the gripper load.
2. Upload `firmware/calibration/calibration.ino`.
3. Open Serial Monitor at 115200 baud with **no line ending**.
4. Press `1`–`4` to select a joint. Use `+` and `-` one degree at a time.
5. Record the first angles before binding or collision at each end.
6. Choose a neutral home angle and reinstall each horn without forcing the link.
7. Put the measured conservative values into `LOW_LIMITS`, `HIGH_LIMITS`, and
   `HOME` in `firmware/robot_arm/robot_arm.ino`.
8. Upload the main firmware only after all four joints are calibrated.

Leave at least 5–10 degrees of margin from every observed mechanical endpoint.

## First-motion test

- [ ] Arm is clamped to a stable surface.
- [ ] Workspace is clear; nobody is inside the motion envelope.
- [ ] External supply polarity and common ground were checked with a meter.
- [ ] Latching power emergency stop cuts servo power and is within reach.
- [ ] D7 interlock reports open when pressed.
- [ ] Calibration sketch was tested one unloaded joint at a time.
- [ ] Host bridge starts in mock mode and rejects out-of-range commands.
- [ ] Real bridge starts with `--serial` and a bearer token.
- [ ] First real move changes only one joint by 5 degrees at low speed.
- [ ] `stop` detaches outputs; the five-second watchdog also detaches them.

Suggested first command after adjusting the project's home values:

```bash
armctl arm
armctl move --base 95 --duration-ms 2000
armctl stop
```

If the servo chatters, overheats, draws excessive current, moves in the wrong
direction, or approaches a hard stop, cut servo power immediately.

## What software cannot verify

The repository tests can validate command schemas and software limits. They
cannot verify polarity, supply capacity, physical clearances, horn alignment,
real emergency-stop operation, or the correct limits for a specific arm.


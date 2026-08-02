# D1 simulation-first vision flow

D1 demonstrates a complete vision-to-action contract without connecting a
camera or allowing vision-generated commands to reach real hardware.

## Flow

1. Choose a pre-recorded scene.
2. Select a detection with at least 80% confidence.
3. Review the selected object, destination, named recipe, and every joint step.
4. Confirm the plan separately; the opaque plan ID expires after five minutes.
5. Complete the normal startup checklist and arm the mock bridge.
6. Execute the single-use named recipe.

The browser cannot submit arbitrary recipe steps through the vision endpoints.
The server looks up every step from the reviewed recipe catalog. Unknown,
low-confidence, expired, unconfirmed, already-executed, disarmed, and non-mock
requests fail closed.

## Run

```bash
export ARM_BRIDGE_TOKEN='use-the-same-dedicated-32-character-token'
arm-bridge --require-startup-checklist
```

In another terminal:

```bash
export ARM_BRIDGE_TOKEN='use-the-same-dedicated-32-character-token'
python -m arm_bridge.console
```

Open `http://127.0.0.1:8780`, pair with the terminal code, complete the startup
checklist, ARM, then use the **D1 · Simulation-first Vision** panel.

## Boundary to D2

D1 never estimates depth, camera intrinsics, hand-eye transforms, grasp poses,
or collision-free trajectories. D2 must add those calibrated measurements and
acceptance tests before any vision plan may execute on real hardware.

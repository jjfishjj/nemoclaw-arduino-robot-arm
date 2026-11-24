# Blue Vial Browser Game

A standalone browser-based 3D demo with three selectable, procedural mock scenarios: Blue Vial pick-and-place, food delivery, and a semiconductor-lab laser-coating visual. The source is isolated from the repository's Arduino, ROS 2, firmware, and host-bridge control paths.

## Run locally

From the repository root:

```bash
python3 -m http.server 8000 --directory demos/blue-vial-browser-game
```

Open <http://127.0.0.1:8000/>. The page loads its vendored Three.js runtime and scenario module from the same folder; no package installation, backend, camera, or robot is required.

## Mock scenarios and safety boundary

- **Blue Vial:** shows a blue-vial target, an amber distractor, and a synthetic bounding-box/mask HUD. The UI references a dataset contract but does not download its rows, run Isaac Sim or Replicator, use a trained model, or perform inference.
- **Food delivery:** animates a virtual delivery robot along a preset route around a mock obstacle to a mock meal tray. It does not navigate real spaces, accept orders, deliver food, or connect to elevators, access controls, delivery platforms, or hardware.
- **Semiconductor lab / laser coating:** shows a fictional wafer station and a moving visual beam/path. It is not a process simulator: it does not emit a laser, deposit material, control equipment, use process parameters, or produce experimental results.
- **Shared controls:** SIL/HIL labels and the HIL confirmation are browser-only demonstrations. E-STOP only latches the page's mock state; it is not a physical emergency stop or a safety-rated control. No scenario connects to this repository's Arduino bridge, ROS 2 stack, firmware, serial devices, external services, or physical equipment. Treat all HUD values, counters, animations, and status as mock visuals, not real-world robotics, delivery, or manufacturing results.

## Data and attribution

The Blue Vial UI references [`junbin666/isaac-blue-vial-sdg-contract`](https://huggingface.co/datasets/junbin666/isaac-blue-vial-sdg-contract) and the related [Isaac Sim-to-Real VLA Lab Space](https://huggingface.co/spaces/junbin666/isaac-sim2real-vla-lab). The dataset card describes 100 procedural 64×64 image/mask rows, with 80 blue-vial positives and 20 amber-distractor negatives. This page presents a mock visualization of that contract; it does not download or consume those rows. The delivery and semiconductor-lab scenes are independent procedural browser mocks, not dataset-backed simulations.

`demos/blue-vial-browser-game/three.min.js` is the vendored Three.js 0.159.0 browser build. Its bundled MIT license notice is retained in the file header.

# Blue Vial Browser Game

A standalone browser-based 3D portfolio demo for blue-vial localization and mock pick-and-place. The source is isolated from the repository's Arduino, ROS 2, firmware, and host-bridge control paths.

## Run locally

From the repository root:

```bash
python3 -m http.server 8000 --directory demos/blue-vial-browser-game
```

Open <http://127.0.0.1:8000/>. The page loads its vendored Three.js runtime from `./three.min.js`; no package installation, backend, camera, or robot is required.

## Demo scope and safety boundary

- The 3D arm, bottles, localization HUD, bounding box, mask, and telemetry are browser-side mock visuals. The page does not run Isaac Sim, Isaac Replicator, a trained model, or inference against the dataset.
- The HIL control is a simulated human-confirmation gate. E-STOP only latches the browser demo state; it is not a physical emergency stop or a safety-rated control.
- The page is not connected to this repository's Arduino bridge, ROS 2 stack, firmware, serial devices, or physical hardware. Do not treat its mock metrics or behavior as real-world robotics results.

## Data and attribution

The UI references [`junbin666/isaac-blue-vial-sdg-contract`](https://huggingface.co/datasets/junbin666/isaac-blue-vial-sdg-contract) and the related [Isaac Sim-to-Real VLA Lab Space](https://huggingface.co/spaces/junbin666/isaac-sim2real-vla-lab). The dataset card describes 100 procedural 64×64 image/mask rows, with 80 blue-vial positives and 20 amber-distractor negatives. This page presents a mock visualization of that contract; it does not download or consume those rows.

`demos/blue-vial-browser-game/three.min.js` is the vendored Three.js 0.159.0 browser build. Its bundled MIT license notice is retained in the file header.

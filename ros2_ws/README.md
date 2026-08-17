# Rover + SO-101 ROS 2 workspace

## Rover Forge mock differential-drive base

This workspace now includes a simulation-only mobile base built around
`ros2_control` and `mock_components/GenericSystem`. It does not require a
physical motor controller.

```text
src/
├── rover_description/  # xacro URDF, wheel joints, ros2_control block, RViz
├── rover_bringup/      # controller YAML, launch file, runtime smoke test
└── sim2real_interfaces/# existing SO-101 interfaces
```

Build and launch on Ubuntu 24.04 with ROS 2 Jazzy:

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
ros2 launch rover_bringup mock_rover.launch.py
```

For a headless session, append `use_rviz:=false`. In another sourced terminal,
run the end-to-end smoke test:

```bash
ros2 run rover_bringup smoke_test.sh
```

Or publish commands and inspect feedback manually:

```bash
ros2 topic pub --rate 10 /diff_drive_controller/cmd_vel_unstamped \
  geometry_msgs/msg/Twist "{linear: {x: 0.15}, angular: {z: 0.25}}"
ros2 topic echo /diff_drive_controller/odom
ros2 topic echo /joint_states
```

The controller times out velocity commands after 0.5 seconds and limits linear
velocity to +0.60/-0.30 m/s and angular velocity to +/-1.50 rad/s. These are
simulation defaults, not validated limits for a physical rover.

On a host without ROS 2, validate the package contracts offline:

```bash
python3 tools/validate_rover_workspace.py
```

## Gazebo Harmonic physics simulation

The Gazebo path replaces `GenericSystem` with
`gz_ros2_control/GazeboSimSystem`. It adds contact physics, wheel and caster
friction, a lower-friction calibration lane, collision geometry, and a box for
impact testing. The simulated wheel radii are intentionally asymmetric
(left 0.076 m, right 0.074 m) while the controller uses the nominal 0.075 m.
Together with contact slip, this creates a repeatable odometry-calibration task.

ROS 2 Jazzy uses Gazebo Harmonic. Install the binary integration package:

```bash
sudo apt install ros-jazzy-gz-ros2-control ros-jazzy-ros-gz
```

Build as above, then launch:

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch rover_bringup gazebo_rover.launch.py
```

For headless CI or SSH use:

```bash
ros2 launch rover_bringup gazebo_rover.launch.py headless:=true use_rviz:=false
```

In another sourced terminal, run:

```bash
ros2 run rover_bringup gazebo_smoke_test.sh
```

The smoke test verifies simulation time, both active controllers, commanded
motion, and changing odometry. To calibrate systematic error, drive a measured
distance on `calibration_lane`, compare ground-truth Gazebo pose with controller
odometry, then tune the three multiplier parameters in
`config/gazebo_controllers.yaml`.

## 2D LiDAR and obstacle detection

The Gazebo rover includes a 360-degree GPU LiDAR at `lidar_link`:

- 720 beams at 15 Hz
- 0.12–12.0 m range
- 0.01 m range resolution
- zero-mean Gaussian noise with 0.012 m standard deviation
- Gazebo `/scan` bridged one-way to ROS `sensor_msgs/msg/LaserScan`
- `SENSOR_DATA` QoS and an explicit `lidar_link` frame

RViz displays `/scan` as points. `rover_perception/obstacle_detector` monitors a
40-degree forward sector and publishes:

| Topic | Type | Meaning |
|---|---|---|
| `/obstacle_detected` | `std_msgs/msg/Bool` | `true` when the closest valid forward return is below 1.0 m |
| `/closest_obstacle_range` | `std_msgs/msg/Float32` | closest forward range, or -1 when no valid return exists |

The test world places `occlusion_panel` about 0.80 m in front of the initial
sensor position. The Gazebo smoke test now checks `/scan`, frame ID, 720-beam
shape, measurable noise, panel occlusion, the detector result, controllers,
motion, and odometry:

```bash
ros2 run rover_bringup gazebo_smoke_test.sh
```

Pure obstacle-sector math can be tested without starting Gazebo after building:

```bash
colcon test --packages-select rover_perception
colcon test-result --verbose
```

## Safety velocity filter and Nav2 local costmap

All application and teleoperation commands enter through `/cmd_vel_nav`.
`rover_perception/safety_velocity_filter` first applies scan freshness and
forward-sector fail-safe logic, then Collision Monitor performs the final
polygon safety check. Only Collision Monitor publishes `/cmd_vel_safe`, which
the Gazebo ros2_control plugin remaps to the differential drive controller.

```text
/cmd_vel_nav + /scan
       ↓
safety_velocity_filter
       ↓
/cmd_vel_safety
       ↓
Collision Monitor + /scan
       ↓
/cmd_vel_safe → diff_drive_controller
```

Safety policy:

| State | Condition | Forward output |
|---|---|---|
| `CLEAR` | closest return ≥ 1.50 m | unchanged |
| `SLOW` | 0.85–1.50 m | linearly scaled from 0–100% |
| `STOP` | closest return ≤ 0.85 m | forward zero; rotation capped at 0.60 rad/s |
| `ESCAPE` | reverse command with a fresh scan | allowed, capped at 0.15 m/s |
| `FAILSAFE` | scan >0.35 s old, command >0.50 s old, or no valid return | zero Twist |

Observe the safety decision:

```bash
ros2 topic echo /safety_state
ros2 topic echo /safety_speed_scale
ros2 topic echo /cmd_vel_safe
ros2 topic pub --rate 10 /cmd_vel_nav geometry_msgs/msg/Twist \
  "{linear: {x: 0.2}, angular: {z: 0.0}}"
```

Nav2 Controller Server hosts a 4×4 m rolling local costmap in `odom`, at
0.05 m/cell. Its obstacle layer marks and clears from `/scan`; the inflation
layer expands lethal cells by 0.48 m around the rover footprint. RViz displays
`/local_costmap/costmap` using the Nav2 costmap color scheme.

The Gazebo smoke test verifies that the front panel appears in the local
costmap, forward commands are stopped, reverse escape changes odometry, and the
controller receives commands only through the safe stream.

## SLAM Toolbox mapping and MPPI local control

The Gazebo launch now starts asynchronous SLAM Toolbox and Nav2 Controller
Server. SLAM consumes `/scan`, publishes the `map → odom` transform and builds
`/map`. MPPI follows a dense local path while its embedded local costmap uses
the same scan for obstacle and inflation costs. MPPI publishes
`/cmd_vel_nav`, so every command passes through both safety layers before
ros2_control.

Install the navigation dependencies (or let `rosdep install` resolve them):

```bash
sudo apt install ros-jazzy-slam-toolbox ros-jazzy-navigation2 ros-jazzy-nav2-bringup
```

Launch the full stack, then send the supplied closed mapping path:

```bash
ros2 launch rover_bringup gazebo_rover.launch.py
ros2 run rover_navigation follow_mapping_loop
```

Save both the occupancy map (`.yaml` and `.pgm`) and the serialized SLAM pose
graph (`.posegraph` and `.data`):

```bash
ros2 run rover_bringup save_slam_map.sh "$PWD/maps/rover_map"
```

The repeatable loop-closure test records the initial/final SLAM pose, waits for
a loop-closure event, follows the room perimeter, and saves the result:

```bash
ros2 run rover_bringup slam_loop_test.sh "$PWD/maps/loop_test"
```

For a shorter readiness and action-level test:

```bash
ros2 run rover_bringup navigation_smoke_test.sh
```

The test world has four asymmetric room walls and a cylindrical landmark so a
return to the start has recognizable geometry. Inspect `/map`, `/plan`, scans,
and the local costmap together in RViz to verify scan alignment and correction.

## Planner, BT Navigator, NavigateToPose, and AMCL

The navigation stack now adds Navfn Planner Server, a map-frame global
costmap, and BT Navigator above the existing MPPI Controller Server. The same
Gazebo launch supports two mutually exclusive sources of `map → odom`:

- `navigation_mode:=mapping` (default): SLAM Toolbox builds and updates `/map`.
- `navigation_mode:=localization`: Map Server loads a saved map and AMCL
  localizes from `/scan`.

While mapping, send a map-frame navigation goal directly through the supplied
client:

```bash
ros2 launch rover_bringup gazebo_rover.launch.py
ros2 run rover_navigation navigate_to_pose 1.5 1.2 1.57
```

After saving a map, restart in localization mode. The convenience launch
requires an absolute YAML path and fails early if it does not exist:

```bash
ros2 launch rover_bringup gazebo_localization.launch.py \
  map:="$PWD/maps/rover_map.yaml"
```

Set or correct the initial pose in RViz with **2D Pose Estimate**, then send a
goal with **Nav2 Goal** or the command-line client. The configured zero initial
pose is suitable only when Gazebo starts at the map origin.

Run the localization end-to-end check after AMCL has converged:

```bash
ros2 run rover_bringup localization_smoke_test.sh
```

The test checks lifecycle state, `/map`, `/amcl_pose`, the
`/navigate_to_pose` action, and navigation to `(1.5, 1.2, 1.57 rad)`. Choose a
different reachable test goal if the saved map does not contain that point.

## Collision Monitor final safety layer

Nav2 Collision Monitor is the last velocity-processing node before the base.
It consumes the fresh `/scan` directly rather than waiting for a costmap update:

- `velocity_stop_zone`: selects a different stop envelope for fast forward,
  slow forward, reverse, rotation, and stationary commands. Fast forward grows
  to 0.65 m; reverse extends 0.50 m behind the rover.
- `slow_zone`: 0.90 m forward, 0.45 m rearward and ±0.45 m laterally; four
  or more returns reduce velocity to 35%.
- A scan older than 0.35 s is rejected, while the upstream safety filter also
  independently fails safe on stale scan or velocity commands.

RViz displays the stop polygon in red and slowdown polygon in amber. Observe
the selected action and final output with:

```bash
ros2 topic echo /collision_monitor_state
ros2 topic echo /cmd_vel_safety
ros2 topic echo /cmd_vel_safe
```

Run the focused Gazebo check while the supplied front panel is present:

```bash
ros2 run rover_bringup collision_monitor_smoke_test.sh
```

## Multi-pose patrol, frontier exploration, and Gazebo KPI evaluation

Waypoint Follower is lifecycle-managed with the rest of Nav2. It stops at each
pose and runs the configured mission task plugin. The default five-point patrol is
installed from `rover_navigation/config/patrol_route.json`:

```bash
ros2 run rover_navigation follow_waypoints
ros2 run rover_navigation follow_waypoints /absolute/path/to/custom_route.json
```

`NavigateThroughPoses` uses the BT Navigator to plan one continuous route
through the same hard pose constraints. Unlike Waypoint Follower, it does not
stop to run a task at each intermediate pose:

```bash
ros2 run rover_navigation navigate_through_poses
```

Routes use a small, versionable JSON format:

```json
{"frame_id":"map","poses":[{"x":1.0,"y":0.5,"yaw":1.57}]}
```

During SLAM mapping mode, the frontier explorer clusters unknown cells adjacent
to known free space, projects each centroid back onto a free cell, selects a
nearby high-value frontier, and blacklists failed goals:

```bash
ros2 run rover_navigation frontier_explorer 12
```

Run the patrol smoke test:

```bash
ros2 run rover_bringup autonomy_smoke_test.sh
```

The repeatable benchmark drives the default patrol and writes a JSON report:

```bash
ros2 run rover_bringup run_navigation_benchmark.sh \
  "$PWD/reports/navigation_kpi.json"
```

Reported metrics include waypoint success rate, total time, odometry distance,
minimum LiDAR distance, minimum distance when Collision Monitor first stops,
slow/stop transition counts, and collision proxy rate. A collision proxy is a
new LaserScan episode at or below 0.27 m; it is deliberately labeled as a
proxy, not a physical contact sensor. Run repeated trials with the same world,
map, initial pose, and route before comparing controller or safety tuning.

## Contact collisions, randomized trials, and waypoint mission tasks

The Gazebo rover now has a 100 Hz contact sensor attached to its named base
collision. `/bumper/contacts` is bridged as
`ros_gz_interfaces/msg/Contacts`. The KPI evaluator counts a new physical
contact episode after a 0.5-second contact-free gap and reports maximum
penetration depth, while retaining the LiDAR proxy as a secondary diagnostic.

The custom `rover_waypoint_tasks::MissionTaskExecutor` cycles through these
tasks based on waypoint index:

1. `photo`: saves the latest 640×480 RGB frame as `waypoint_N.ppm`.
2. `lidar_snapshot`: saves all beam angles and ranges as CSV.
3. `operator_confirm`: waits up to 120 seconds for an operator confirmation
   file.

Artifacts are written to `/tmp/rover_waypoint_tasks`. To approve waypoint 2:

```bash
mkdir -p /tmp/rover_waypoint_tasks
touch /tmp/rover_waypoint_tasks/waypoint_2.confirm
```

Then execute the normal patrol:

```bash
ros2 run rover_navigation follow_waypoints
ls -l /tmp/rover_waypoint_tasks
```

For repeatable randomized testing, provide a saved static map. Each trial uses
a deterministic seed, inserts eight cylindrical obstacles away from the start
and waypoint centers, launches headless Gazebo, executes the same patrol, and
shuts the simulation down before the next trial:

```bash
ros2 run rover_bringup run_random_benchmark.sh \
  "$PWD/maps/rover_map.yaml" 5 "$PWD/reports/random_benchmark"
```

The directory contains each generated SDF world, launch log, trial KPI JSON,
and `summary.json`. The summary reports trial success rate, mean waypoint
success, elapsed time, path length, stop distance, total Gazebo contact events,
and contact collision rate per navigation goal. Seeds and generated worlds are
kept so any failure can be reproduced exactly.

## SO-101 contract

This workspace is the typed boundary between Isaac Sim, the physical-arm
safety bridge, and the presentation dashboard. It targets ROS 2 Jazzy on
Ubuntu 24.04 and remains compatible at the message level with Humble.

## Topics

| Name | Type | Producer → consumer | Contract |
|---|---|---|---|
| `/so101/joint_states` | `sensor_msgs/msg/JointState` | hardware/sim → all | six measured joints, radians, 50 Hz |
| `/so101/joint_trajectory` | `trajectory_msgs/msg/JointTrajectory` | planner → safety bridge | complete ordered trajectory, reliable |
| `/so101/estop` | `std_msgs/msg/Bool` | any safety source → bridge | `true` latches; `false` never clears |
| `/so101/telemetry` | `sim2real_interfaces/msg/Sim2RealTelemetry` | sim/HIL → dashboard | phase, metrics, backend, stop state |

`/so101/estop/reset` uses `std_srvs/srv/Trigger` and is accepted only after
workspace confirmation and release of the physical stop. For monitored motion,
prefer `/so101/follow_joint_trajectory` using
`control_msgs/action/FollowJointTrajectory`; the topic is intentionally
fire-and-forget.

## Build on the Ubuntu ROS host

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
ros2 interface show sim2real_interfaces/msg/Sim2RealTelemetry
```

## Host-only contract check

ROS does not need to be installed to validate JSON representations:

```bash
ros2-contract-check joint-trajectory examples/joint_trajectory.json
```

The authoritative mapping is `../isaac_sim/ros2_topic_mapping.yaml`. The
Python validator rejects partial/reordered joints, non-finite values,
non-increasing trajectory times, moving final points, oversized duration,
unsafe E-STOP resets, and malformed telemetry.

## C2.5 execution relay

The relay subscribes to `/so101/joint_trajectory`, sends validated six-axis
setpoints through the HTTP safety bridge, subscribes to the latched
`/so101/estop`, and publishes measured `/so101/joint_states` in radians.

Terminal 1 — safe SO-101 mock bridge:

```bash
arm-bridge --robot so101
armctl arm
```

Terminal 2 — ROS host:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
so101-ros2-relay \
  --bridge http://127.0.0.1:8765 \
  --calibration ros2_ws/config/so101_relay_calibration.json
```

Terminal 3 — observe feedback and publish a two-point test:

```bash
ros2 topic echo /so101/joint_states

ros2 topic pub --once /so101/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [Rotation, Pitch, Elbow, Wrist_Pitch, Wrist_Roll, Jaw], points: [{positions: [0.0, -0.2, 0.4, 0.1, 0.0, 0.2], time_from_start: {sec: 1}}, {positions: [0.1, -0.1, 0.3, 0.0, 0.0, 0.0], velocities: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
```

Trigger the latched stop from any ROS terminal:

```bash
ros2 topic pub --once --qos-durability transient_local \
  /so101/estop std_msgs/msg/Bool "{data: true}"
```

The included calibration converts the first five radians to LeRobot degrees
and maps a 0–0.7 rad jaw range to LeRobot 0–100. It is intentionally marked
`physical_verified: false`: mock mode accepts it, but the relay refuses a real
SO-101 until the measured scale/zero values are entered and this flag is set to
`true`. E-STOP reset stays an explicit operator action through
`armctl reset_estop --workspace-confirmed`; publishing `false` never resets it.

## C2.6 monitored trajectory action

For production-style execution, use the action endpoint instead of the
fire-and-forget topic:

```bash
ros2 action list -t
ros2 action send_goal --feedback \
  /so101/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{trajectory: {joint_names: [Rotation, Pitch, Elbow, Wrist_Pitch, Wrist_Roll, Jaw], points: [{positions: [0.0, -0.2, 0.4, 0.1, 0.0, 0.2], time_from_start: {sec: 1}}, {positions: [0.1, -0.1, 0.3, 0.0, 0.0, 0.0], velocities: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}}"
```

Each completed point publishes desired/actual/error feedback. Invalid goals
are rejected, bridge failures abort the action, and client cancellation clears
the active trajectory and disarms the arm. Cancellation does not claim to be
an E-STOP; `/so101/estop=true` remains the separate latched emergency path.

## C3 USB camera and blue-vial detection

The presentation server includes an HSV detector and annotated Real Cell feed.
It defaults to a deterministic mock camera:

```bash
sim2real-demo --fake-isaac --camera mock
```

Install the optional camera stack and select a USB camera on the Mac/Linux
host:

```bash
python3 -m pip install -e '.[vision]'
sim2real-demo --fake-isaac --camera 0
```

Open `http://127.0.0.1:8080`. The Real Cell pane reports USB/MOCK mode, blue
vial confidence, bounding box center, and an annotated JPEG feed. If OpenCV or
the camera is unavailable, it falls back to mock and reports the cause through
`/api/vision/status`.

## C3.1 pixel-to-robot calibration

`../isaac_sim/vision_calibration.json` contains four image↔table control points.
The resulting homography maps the detected vial center `(u,v)` to robot-base
`(x,y,table_z)`. Replace the preview points with measured fiducial locations;
use points that span the complete working area rather than a small cluster.

The API returns both pixel and planar positions:

```bash
curl http://127.0.0.1:8080/api/vision/status
```

## C3.2 RealSense depth

Install the optional SDK and select the aligned color/depth source:

```bash
python3 -m pip install -e '.[realsense]'
sim2real-demo --fake-isaac --camera realsense \
  --vision-calibration isaac_sim/vision_calibration.json
```

The detector takes the median valid depth in a 5×5 patch, deprojects it using
`fx/fy/cx/cy`, then applies the 4×4 `camera_to_robot` transform. The included
intrinsics/extrinsics are preview values and remain `physical_verified: false`.

## C4 safety package

Real serial bridges automatically require the startup checklist and enable a
two-second host watchdog. To demonstrate the same gate in mock mode:

```bash
arm-bridge --robot so101 --require-startup-checklist --watchdog-timeout 2
armctl startup_check --workspace-clear --physical-estop-tested \
  --joint-limits-reviewed --calibration-verified
armctl arm
```

The bridge rejects per-joint velocities above the profile limit. ROS relay
feeds the watchdog while a trajectory is active. A watchdog timeout or E-STOP
disables output, latches the stop, clears readiness, and requires both explicit
reset and a new checklist. See `../docs/c4-safety-checklist.md` before connecting
hardware.

## Benchmark HTML and Foxglove dashboards

Every benchmark now generates a standalone HTML dashboard next to its JSON.
The file embeds its data, styles, and charts, so it can be opened directly or
shared without a CDN. It supports importing replacement trial JSON files,
sorting trials, and adjusting waypoint-success and contact-rate thresholds.

Generate one manually:

```bash
ros2 run rover_navigation benchmark_dashboard \
  "$PWD/reports/dashboard.html" \
  "$PWD"/reports/random_benchmark/trial_*.json
```

Serve the dashboard locally when desired:

```bash
ros2 run rover_bringup open_benchmark_dashboard.sh \
  "$PWD/reports/random_benchmark" 8080
```

Open `http://127.0.0.1:8080/dashboard.html`.

Gazebo bringup starts `foxglove_bridge` on port 8765 by default. Connect
Foxglove to `ws://localhost:8765`, or use the robot IP for a remote machine.
`config/foxglove_dashboard.json` is the stable panel/topic manifest for a 3D
map/scan/path view, camera, velocity-chain plots, collision transitions,
closest-obstacle gauge, contacts, and topic graph. Foxglove's exported layout
JSON is deliberately not checked in because its internal panel IDs and schema
are version dependent; save the completed layout in Foxglove and share its
official `layoutId` link.

Direct desktop connection:

```text
https://app.foxglove.dev/~/view?ds=foxglove-websocket&ds.url=ws://localhost:8765&openIn=desktop
```

Disable the bridge when not needed:

```bash
ros2 launch rover_bringup gazebo_rover.launch.py use_foxglove:=false
```

## MCAP evidence and CI safety thresholds

Benchmark commands now start `ros2 bag record` with the MCAP storage plugin,
simulation timestamps, and the `zstd_fast` indexed compression profile. The
recording includes clock, TF, map, scan, camera, physical contacts, odometry,
the full velocity safety chain, costmaps, plans, and navigation feedback. Each
random seed receives its own `trial_N_mcap/` directory containing metadata and
an `.mcap` file that Foxglove can open directly.

## Self-hosted ROS/GPU GitHub runner

The offline PR gate remains on GitHub-hosted Ubuntu. Full Gazebo physics, GPU
LiDAR, randomized navigation, physical-contact KPI, HTML dashboard, and MCAP
evidence run on a dedicated Ubuntu 24.04 NVIDIA host through
`.github/workflows/ros2-rover-gpu-benchmark.yml`.

Provisioning, registration, preflight, security guidance, and recovery notes
are in `../ops/ros_gpu_runner/README.md`. The GPU workflow is intentionally
manual and scheduled only; it never executes untrusted pull-request code. Jobs
require the labels `self-hosted,linux,x64,ros2-jazzy,gpu,gazebo` and a readable
saved map on the runner.

The production workflow now additionally requires `ephemeral`. A trusted
`workflow_job` webhook provisioner creates a clean GPU VM, injects GitHub's
short-lived token, and starts `run_ephemeral_once.sh`. After exactly one job the
runner forwards diagnostics and invokes a root-owned VM teardown hook.

Each randomized trial samples NVIDIA GPU utilization, VRAM, temperature, power,
and free disk space once per second. The evaluator derives Gazebo real-time
factor from `/clock`, observes FollowWaypoints-to-`/plan` latency, and measures
the final MCAP directory. The summary and CI gate now fail closed on missing or
regressed RTF, peak VRAM, planning latency, or MCAP size in addition to the
navigation and collision limits.

Install the storage plugin on the ROS host:

```bash
sudo apt install ros-jazzy-rosbag2-storage-mcap
```

Record a standalone live session when needed:

```bash
ros2 run rover_bringup record_benchmark_mcap.sh \
  "$PWD/reports/manual_mcap"
```

Stop it with `Ctrl+C`. Output paths must be new so evidence is never silently
overwritten. Open the resulting `.mcap` directly in Foxglove with
**Open local file**.

`config/benchmark_thresholds.json` is the versioned safety policy. The defaults
require at least 90% successful trials, 95% mean waypoint completion, zero
physical contacts per goal, at least 0.30 m mean stop distance, and zero
timeouts. Both benchmark scripts run this gate after generating their reports;
failure returns a nonzero exit status suitable for CI:

```bash
ros2 run rover_navigation benchmark_gate \
  "$PWD/reports/random_benchmark/summary.json" \
  "$(ros2 pkg prefix --share rover_navigation)/config/benchmark_thresholds.json"
```

`.github/workflows/ros2-rover-benchmark-gate.yml` runs the offline unit tests,
workspace contracts, versioned baseline gate, and uploads an HTML evidence
dashboard on pushes and pull requests that affect `ros2_ws`. General GitHub
runners do not claim to execute Gazebo; run the full randomized benchmark on a
ROS 2 Jazzy/Gazebo host or a future self-hosted GPU runner, then preserve its
JSON, HTML, logs, generated worlds, and MCAP directories as CI artifacts.

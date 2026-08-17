#!/usr/bin/env python3
"""Offline contract check for hosts without ROS 2 installed."""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
URDF = ROOT / "src/rover_description/urdf/rover.urdf.xacro"
YAML = ROOT / "src/rover_bringup/config/rover_controllers.yaml"
LAUNCH = ROOT / "src/rover_bringup/launch/mock_rover.launch.py"
GZ_LAUNCH = ROOT / "src/rover_bringup/launch/gazebo_rover.launch.py"
LOCALIZATION_LAUNCH = ROOT / "src/rover_bringup/launch/gazebo_localization.launch.py"
GZ_YAML = ROOT / "src/rover_bringup/config/gazebo_controllers.yaml"
WORLD = ROOT / "src/rover_description/worlds/rover_test.sdf"
BRIDGE = ROOT / "src/rover_bringup/config/gazebo_bridge.yaml"
PERCEPTION = ROOT / "src/rover_perception/rover_perception/obstacle_detector.py"
SAFETY = ROOT / "src/rover_perception/rover_perception/safety_velocity_filter.py"
NAV2 = ROOT / "src/rover_bringup/config/nav2_controller.yaml"
SLAM = ROOT / "src/rover_bringup/config/slam_toolbox.yaml"
NAVIGATION = ROOT / "src/rover_navigation/rover_navigation/follow_mapping_loop.py"
NAVIGATE = ROOT / "src/rover_navigation/rover_navigation/navigate_to_pose.py"
MISSION = ROOT / "src/rover_navigation/rover_navigation/mission_client.py"
FRONTIER = ROOT / "src/rover_navigation/rover_navigation/frontier_explorer.py"
EVALUATOR = ROOT / "src/rover_navigation/rover_navigation/nav_evaluator.py"
RANDOM_WORLD = ROOT / "src/rover_navigation/rover_navigation/random_world.py"
SUMMARY = ROOT / "src/rover_navigation/rover_navigation/benchmark_summary.py"
DASHBOARD = ROOT / "src/rover_navigation/rover_navigation/dashboard_report.py"
DASHBOARD_TEMPLATE = ROOT / "src/rover_navigation/rover_navigation/dashboard_template.html"
FOXGLOVE = ROOT / "src/rover_bringup/config/foxglove_dashboard.json"
GATE = ROOT / "src/rover_navigation/rover_navigation/benchmark_gate.py"
PERFORMANCE = ROOT / "src/rover_navigation/rover_navigation/performance_report.py"
THRESHOLDS = ROOT / "src/rover_navigation/config/benchmark_thresholds.json"
MCAP_TOPICS = ROOT / "src/rover_navigation/config/mcap_topics.txt"
TASK_PLUGIN = ROOT / "src/rover_waypoint_tasks/src/mission_task_executor.cpp"
TASK_XML = ROOT / "src/rover_waypoint_tasks/waypoint_task_plugins.xml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    tree = ET.parse(URDF)
    root = tree.getroot()
    control = root.find("ros2_control")
    require(control is not None, "missing ros2_control block")
    urdf_text = URDF.read_text()
    require("mock_components/GenericSystem" in urdf_text, "mock hardware plugin missing")
    require("gz_ros2_control/GazeboSimSystem" in urdf_text, "Gazebo hardware plugin missing")
    require("libgz_ros2_control-system.so" in urdf_text, "Gazebo system plugin missing")
    for lidar_contract in (
        'name="lidar_link"', 'type="gpu_lidar"', '<topic>/scan</topic>',
        '<samples>720</samples>', '<stddev>0.012</stddev>',
    ):
        require(lidar_contract in urdf_text, f"LiDAR contract missing: {lidar_contract}")
    for sensor_contract in (
        'name="base_contact"', 'type="contact"', '<topic>/bumper/contacts</topic>',
        'name="front_camera"', '<topic>/camera/image_raw</topic>', '<format>R8G8B8</format>',
    ):
        require(sensor_contract in urdf_text, f"camera/contact contract missing: {sensor_contract}")
    require(
        "/diff_drive_controller/cmd_vel_unstamped:=/cmd_vel_safe" in urdf_text,
        "safe velocity output is not remapped to the controller",
    )
    controlled = {node.attrib["name"] for node in control.findall("joint")}
    expected = {"left_wheel_joint", "right_wheel_joint"}
    xacro_ns = "{http://www.ros.org/wiki/xacro}"
    wheel_macro = root.find(f"{xacro_ns}macro[@name='wheel']")
    require(wheel_macro is not None, "wheel xacro macro missing")
    macro_joint = wheel_macro.find("joint")
    require(
        macro_joint is not None and macro_joint.attrib.get("name") == "${prefix}_wheel_joint",
        "wheel macro does not generate the expected joint name",
    )
    wheel_instances = {
        node.attrib.get("prefix") for node in root.findall(f"{xacro_ns}wheel")
    }
    require(wheel_instances == {"left", "right"}, "left/right wheel instances missing")
    for instance in root.findall(f"{xacro_ns}wheel"):
        require("radius" in instance.attrib, "wheel instance radius is not configurable")
    require(controlled == expected, "ros2_control wheel joint contract mismatch")
    for joint in control.findall("joint"):
        commands = {x.attrib["name"] for x in joint.findall("command_interface")}
        states = {x.attrib["name"] for x in joint.findall("state_interface")}
        require(commands == {"velocity"}, f"{joint.attrib['name']} must use velocity commands")
        require(states == {"position", "velocity"}, f"{joint.attrib['name']} state interfaces mismatch")

    yaml_text = YAML.read_text()
    for name in expected:
        require(name in yaml_text, f"{name} missing from controller YAML")
    require("wheel_separation: 0.30" in yaml_text, "wheel separation mismatch")
    require("wheel_radius: 0.075" in yaml_text, "wheel radius mismatch")
    require("use_stamped_vel: false" in yaml_text, "unstamped cmd_vel contract missing")
    require(re.search(r"cmd_vel_timeout:\s*0\.5", yaml_text), "command timeout missing")

    launch_text = LAUNCH.read_text()
    for executable in ("robot_state_publisher", "ros2_control_node", "spawner", "rviz2"):
        require(executable in launch_text, f"{executable} missing from launch")
    compile(LAUNCH.read_text(), str(LAUNCH), "exec")
    gz_yaml = GZ_YAML.read_text()
    for name in expected:
        require(name in gz_yaml, f"{name} missing from Gazebo controller YAML")
    require("wheel_radius: 0.075" in gz_yaml, "Gazebo nominal wheel radius missing")
    gz_launch = GZ_LAUNCH.read_text()
    for contract in (
        "ros_gz_sim", "ros_gz_bridge", "use_gazebo:=true",
        "left_wheel_radius:=0.076", "right_wheel_radius:=0.074",
        "safety_velocity_filter", "controller_server", "nav2_lifecycle_manager",
        "online_async_launch.py", "slam_toolbox", "planner_server", "bt_navigator", "behavior_server",
        "collision_monitor", "waypoint_follower", "foxglove_bridge", "use_foxglove",
        "/cmd_vel_nav", "/cmd_vel_safety",
        "map_server", "amcl", "navigation_mode", "validate_navigation_mode",
    ):
        require(contract in gz_launch, f"Gazebo launch contract missing: {contract}")
    compile(gz_launch, str(GZ_LAUNCH), "exec")
    localization_launch = LOCALIZATION_LAUNCH.read_text()
    for contract in ("navigation_mode", "localization", "map"):
        require(contract in localization_launch, f"localization launch contract missing: {contract}")
    compile(localization_launch, str(LOCALIZATION_LAUNCH), "exec")

    world_root = ET.parse(WORLD).getroot()
    world = world_root.find("world")
    require(world is not None, "Gazebo world missing")
    model_names = {node.attrib.get("name") for node in world.findall("model")}
    require(
        {
            "ground_plane", "calibration_lane", "collision_box", "occlusion_panel",
            "north_wall", "south_wall", "east_wall", "west_wall", "landmark_column",
        } <= model_names,
        "Gazebo world is missing terrain or collision models",
    )
    require(world.find("physics") is not None, "Gazebo physics settings missing")
    plugins = {node.attrib.get("name") for node in world.findall("plugin")}
    require("gz::sim::systems::Sensors" in plugins, "Gazebo Sensors system missing")
    require("gz::sim::systems::Contact" in plugins, "Gazebo Contact system missing")

    bridge_text = BRIDGE.read_text()
    for contract in (
        "sensor_msgs/msg/LaserScan", "gz.msgs.LaserScan", "GZ_TO_ROS",
        "SENSOR_DATA", "frame_id: lidar_link",
        "sensor_msgs/msg/Image", "gz.msgs.Image", "ros_gz_interfaces/msg/Contacts",
        "gz.msgs.Contacts", "/bumper/contacts",
    ):
        require(contract in bridge_text, f"scan bridge contract missing: {contract}")
    compile(PERCEPTION.read_text(), str(PERCEPTION), "exec")
    compile(SAFETY.read_text(), str(SAFETY), "exec")
    safety_text = SAFETY.read_text()
    for contract in ("input_topic", "output_topic", "scan_timeout", "command_timeout"):
        require(contract in safety_text, f"safety filter contract missing: {contract}")

    nav2_text = NAV2.read_text()
    for contract in (
        'plugins: ["obstacle_layer", "inflation_layer"]',
        'plugin: "nav2_costmap_2d::ObstacleLayer"',
        'plugin: "nav2_costmap_2d::InflationLayer"',
        "topic: /scan", "global_frame: odom", "rolling_window: true",
        'plugin: "nav2_mppi_controller::MPPIController"',
        "model_dt: 0.05", 'motion_model: "DiffDrive"',
        'plugin: "nav2_navfn_planner::NavfnPlanner"',
        'plugin: "nav2_costmap_2d::StaticLayer"',
        'plugin: "nav2_bt_navigator::NavigateToPoseNavigator"',
        'plugin: "nav2_bt_navigator::NavigateThroughPosesNavigator"',
        'plugin: "rover_waypoint_tasks::MissionTaskExecutor"',
        'tasks: ["photo", "lidar_snapshot", "operator_confirm"]',
        'plugin: "nav2_behaviors::Spin"', 'plugin: "nav2_behaviors::BackUp"',
        "collision_monitor:", "cmd_vel_in_topic: /cmd_vel_safety",
        "cmd_vel_out_topic: /cmd_vel_safe", 'polygons: ["velocity_stop_zone", "slow_zone"]',
        'type: "velocity_polygon"',
        'velocity_polygons: ["forward_fast", "forward_slow", "backward", "rotation", "stopped"]',
        'action_type: "stop"', 'action_type: "slowdown"',
        "base_frame_id: base_footprint", "global_frame_id: map",
        'node_names: ["controller_server", "planner_server", "behavior_server", "bt_navigator", "waypoint_follower", "collision_monitor"]',
        'node_names: ["map_server", "amcl"]',
    ):
        require(contract in nav2_text, f"Nav2 controller contract missing: {contract}")

    slam_text = SLAM.read_text()
    for contract in (
        "scan_topic: /scan", "map_frame: map", "odom_frame: odom",
        "use_map_saver: true", "do_loop_closing: true",
        "loop_match_minimum_chain_size: 8",
    ):
        require(contract in slam_text, f"SLAM contract missing: {contract}")
    compile(NAVIGATION.read_text(), str(NAVIGATION), "exec")
    compile(NAVIGATE.read_text(), str(NAVIGATE), "exec")
    compile(MISSION.read_text(), str(MISSION), "exec")
    compile(FRONTIER.read_text(), str(FRONTIER), "exec")
    compile(EVALUATOR.read_text(), str(EVALUATOR), "exec")
    compile(RANDOM_WORLD.read_text(), str(RANDOM_WORLD), "exec")
    compile(SUMMARY.read_text(), str(SUMMARY), "exec")
    compile(DASHBOARD.read_text(), str(DASHBOARD), "exec")
    compile(GATE.read_text(), str(GATE), "exec")
    compile(PERFORMANCE.read_text(), str(PERFORMANCE), "exec")
    dashboard_text = DASHBOARD_TEMPLATE.read_text()
    for contract in ("__DASHBOARD_DATA__", "successThreshold", "collisionThreshold", "contact_collision_events"):
        require(contract in dashboard_text, f"dashboard contract missing: {contract}")
    foxglove = __import__("json").loads(FOXGLOVE.read_text())
    require(foxglove.get("connection") == "ws://localhost:8765", "Foxglove connection mismatch")
    require(len(foxglove.get("panels", [])) >= 7, "Foxglove panel manifest incomplete")
    thresholds = __import__("json").loads(THRESHOLDS.read_text())
    for name in (
        "minimum_trial_success_rate", "minimum_waypoint_success_rate",
        "maximum_contact_collision_rate_per_goal", "minimum_mean_stop_distance_m",
        "maximum_timeout_rate",
        "minimum_mean_real_time_factor", "maximum_peak_gpu_memory_mib",
        "maximum_mean_planning_latency_ms", "maximum_mcap_size_mib",
    ):
        require(name in thresholds, f"benchmark threshold missing: {name}")
    mcap_topics = set(MCAP_TOPICS.read_text().splitlines())
    for topic in ("/clock", "/tf", "/scan", "/bumper/contacts", "/cmd_vel_safe"):
        require(topic in mcap_topics, f"MCAP evidence topic missing: {topic}")
    task_text = TASK_PLUGIN.read_text()
    for contract in ("savePhoto", "saveScan", "waitForConfirmation", "PLUGINLIB_EXPORT_CLASS"):
        require(contract in task_text, f"waypoint task plugin contract missing: {contract}")
    ET.parse(TASK_XML)
    print("PASS: contact sensor, task plugin, randomized benchmark, navigation, safety, SLAM, and Gazebo contracts agree")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, ET.ParseError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

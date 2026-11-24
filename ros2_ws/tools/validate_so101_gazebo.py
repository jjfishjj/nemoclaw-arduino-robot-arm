#!/usr/bin/env python3
"""Offline structural checks for the SO-101 Gazebo scaffold."""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = ROOT / "src/so101_description/urdf/so101.urdf.xacro"
CONTROLLERS = ROOT / "src/so101_gazebo_bringup/config/so101_controllers.yaml"
LAUNCH = ROOT / "src/so101_gazebo_bringup/launch/gazebo_so101.launch.py"
WORLD = ROOT / "src/so101_gazebo_bringup/worlds/so101_demo.sdf"
EXPECTED_JOINTS = ["Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for relative in (
        "src/so101_description/package.xml",
        "src/so101_description/CMakeLists.txt",
        "src/so101_gazebo_bringup/package.xml",
        "src/so101_gazebo_bringup/CMakeLists.txt",
    ):
        require((ROOT / relative).is_file(), f"package file missing: {relative}")

    urdf_root = ET.parse(DESCRIPTION).getroot()
    require(urdf_root.tag == "robot", "Xacro root must be a URDF robot")
    movable = [
        joint for joint in urdf_root.findall("joint")
        if joint.attrib.get("type") != "fixed"
    ]
    joint_names = [joint.attrib.get("name") for joint in movable]
    require(joint_names == EXPECTED_JOINTS, "URDF joint order/names do not match SO-101 contract")
    control = urdf_root.find("ros2_control")
    require(control is not None, "ros2_control block missing")
    controlled = [joint.attrib.get("name") for joint in control.findall("joint")]
    require(controlled == EXPECTED_JOINTS, "ros2_control joint order/names mismatch")
    require(
        control.findtext("hardware/plugin") == "gz_ros2_control/GazeboSimSystem",
        "description must use GazeboSimSystem only",
    )
    require("libgz_ros2_control-system.so" in DESCRIPTION.read_text(), "Gazebo system plugin missing")
    require("/joint_states:=/so101/joint_states" in DESCRIPTION.read_text(), "SO-101 joint state remap missing")
    for joint in movable:
        require(joint.find("limit") is not None, f"joint limit missing: {joint.attrib.get('name')}")

    controller_text = CONTROLLERS.read_text()
    yaml_joints = re.search(r"^\s*joints:\s*\[([^]]+)\]", controller_text, re.MULTILINE)
    require(yaml_joints is not None, "controller joint list missing")
    parsed_joints = [item.strip() for item in yaml_joints.group(1).split(",")]
    require(parsed_joints == EXPECTED_JOINTS, "controller joint order/names mismatch")
    for contract in (
        "joint_state_broadcaster/JointStateBroadcaster",
        "joint_trajectory_controller/JointTrajectoryController",
        "allow_partial_joints_goal: false",
        "cmd_timeout: 0.5",
    ):
        require(contract in controller_text, f"controller contract missing: {contract}")

    compile(LAUNCH.read_text(), str(LAUNCH), "exec")
    launch_text = LAUNCH.read_text()
    for contract in (
        "ros_gz_sim", "ros_gz_bridge", "robot_state_publisher",
        "joint_state_broadcaster", '"so101"', "headless",
    ):
        require(contract in launch_text, f"launch contract missing: {contract}")

    world_root = ET.parse(WORLD).getroot()
    world = world_root.find("world")
    require(world is not None and world.attrib.get("name") == "so101_demo", "Gazebo world missing or misnamed")
    plugins = {plugin.attrib.get("name") for plugin in world.findall("plugin")}
    require("gz::sim::systems::Physics" in plugins, "Gazebo Physics system plugin missing")

    for package_path, expected_name in (
        (ROOT / "src/so101_description/package.xml", "so101_description"),
        (ROOT / "src/so101_gazebo_bringup/package.xml", "so101_gazebo_bringup"),
    ):
        package = ET.parse(package_path).getroot()
        require(package.findtext("name") == expected_name, f"package name mismatch: {expected_name}")

    print("PASS: six-joint SO-101 URDF, ros2_control, controller, launch, and Gazebo world contracts agree")
    print("NOTE: offline structural check only; Gazebo runtime was not executed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, ET.ParseError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

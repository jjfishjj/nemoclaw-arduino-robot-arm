from launch import LaunchDescription
from pathlib import Path

from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, IfElseSubstitution, LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def validate_navigation_mode(context):
    mode = LaunchConfiguration("navigation_mode").perform(context)
    if mode not in {"mapping", "localization"}:
        raise RuntimeError("navigation_mode must be 'mapping' or 'localization'")
    if mode == "localization":
        map_path = LaunchConfiguration("map").perform(context)
        if not map_path or not Path(map_path).is_file():
            raise RuntimeError("localization mode requires map:=/absolute/path/to/map.yaml")
    return []


def generate_launch_description():
    use_rviz = LaunchConfiguration("use_rviz")
    use_foxglove = LaunchConfiguration("use_foxglove")
    headless = LaunchConfiguration("headless")
    navigation_mode = LaunchConfiguration("navigation_mode")
    map_file = LaunchConfiguration("map")
    mapping = IfCondition(PythonExpression(["'", navigation_mode, "' == 'mapping'"]))
    localization = IfCondition(PythonExpression(["'", navigation_mode, "' == 'localization'"]))
    default_world = PathJoinSubstitution([
        FindPackageShare("rover_description"), "worlds", "rover_test.sdf"
    ])
    world = LaunchConfiguration("world")
    bridge_config = PathJoinSubstitution([
        FindPackageShare("rover_bringup"), "config", "gazebo_bridge.yaml"
    ])
    nav2_config = PathJoinSubstitution([
        FindPackageShare("rover_bringup"), "config", "nav2_controller.yaml"
    ])
    slam_config = PathJoinSubstitution([
        FindPackageShare("rover_bringup"), "config", "slam_toolbox.yaml"
    ])
    description = Command([
        FindExecutable(name="xacro"), " ",
        PathJoinSubstitution([FindPackageShare("rover_description"), "urdf", "rover.urdf.xacro"]),
        " use_mock_hardware:=false use_gazebo:=true",
        " left_wheel_radius:=0.076 right_wheel_radius:=0.074",
    ])

    return LaunchDescription([
        DeclareLaunchArgument("use_rviz", default_value="true", description="Start RViz2"),
        DeclareLaunchArgument("use_foxglove", default_value="true", description="Start Foxglove WebSocket bridge"),
        DeclareLaunchArgument("headless", default_value="false", description="Run Gazebo server without GUI"),
        DeclareLaunchArgument("world", default_value=default_world, description="Gazebo SDF world path"),
        DeclareLaunchArgument("navigation_mode", default_value="mapping", description="mapping or localization"),
        DeclareLaunchArgument("map", default_value="", description="Absolute map YAML path for localization"),
        OpaqueFunction(function=validate_navigation_mode),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"
            ])),
            launch_arguments={"gz_args": [
                IfElseSubstitution(headless, if_value=" -r -s -v 3 ", else_value=" -r -v 3 "),
                world,
            ]}.items(),
        ),
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{"robot_description": description, "use_sim_time": True}],
            output="screen",
        ),
        Node(
            package="ros_gz_sim",
            executable="create",
            arguments=["-name", "rover", "-topic", "robot_description", "-z", "0.09"],
            output="screen",
        ),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            parameters=[{"config_file": bridge_config, "use_sim_time": True}],
            output="screen",
        ),
        Node(
            package="foxglove_bridge",
            executable="foxglove_bridge",
            name="foxglove_bridge",
            parameters=[{
                "port": 8765,
                "address": "0.0.0.0",
                "send_buffer_limit": 10000000,
                "use_sim_time": True,
            }],
            condition=IfCondition(use_foxglove),
            output="screen",
        ),
        Node(
            package="rover_perception",
            executable="safety_velocity_filter",
            parameters=[{
                "use_sim_time": True,
                "input_topic": "/cmd_vel_nav",
                "output_topic": "/cmd_vel_safety",
                "slow_distance": 1.50,
                "stop_distance": 0.85,
                "forward_half_angle": 0.35,
                "minimum_valid_range": 0.12,
                "scan_timeout": 0.35,
                "command_timeout": 0.50,
                "maximum_reverse_speed": 0.15,
                "maximum_turn_speed": 0.60,
            }],
            output="screen",
        ),
        Node(
            package="nav2_controller",
            executable="controller_server",
            name="controller_server",
            parameters=[nav2_config],
            remappings=[("cmd_vel", "/cmd_vel_nav")],
            output="screen",
        ),
        Node(
            package="nav2_planner",
            executable="planner_server",
            name="planner_server",
            parameters=[nav2_config],
            output="screen",
        ),
        Node(
            package="nav2_bt_navigator",
            executable="bt_navigator",
            name="bt_navigator",
            parameters=[nav2_config],
            output="screen",
        ),
        Node(
            package="nav2_behaviors",
            executable="behavior_server",
            name="behavior_server",
            parameters=[nav2_config],
            remappings=[("cmd_vel", "/cmd_vel_nav")],
            output="screen",
        ),
        Node(
            package="nav2_collision_monitor",
            executable="collision_monitor",
            name="collision_monitor",
            parameters=[nav2_config],
            output="screen",
        ),
        Node(
            package="nav2_waypoint_follower",
            executable="waypoint_follower",
            name="waypoint_follower",
            parameters=[nav2_config],
            output="screen",
        ),
        Node(
            package="nav2_lifecycle_manager",
            executable="lifecycle_manager",
            name="lifecycle_manager_navigation",
            parameters=[nav2_config],
            output="screen",
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare("slam_toolbox"), "launch", "online_async_launch.py"
            ])),
            launch_arguments={
                "slam_params_file": slam_config,
                "use_sim_time": "true",
            }.items(),
            condition=mapping,
        ),
        Node(
            package="nav2_map_server",
            executable="map_server",
            name="map_server",
            parameters=[nav2_config, {"yaml_filename": map_file}],
            condition=localization,
            output="screen",
        ),
        Node(
            package="nav2_amcl",
            executable="amcl",
            name="amcl",
            parameters=[nav2_config],
            condition=localization,
            output="screen",
        ),
        Node(
            package="nav2_lifecycle_manager",
            executable="lifecycle_manager",
            name="lifecycle_manager_localization",
            parameters=[nav2_config],
            condition=localization,
            output="screen",
        ),
        Node(
            package="controller_manager", executable="spawner",
            arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
            output="screen",
        ),
        Node(
            package="controller_manager", executable="spawner",
            arguments=["diff_drive_controller", "--controller-manager", "/controller_manager"],
            output="screen",
        ),
        Node(
            package="rviz2", executable="rviz2",
            arguments=["-d", PathJoinSubstitution([
                FindPackageShare("rover_description"), "rviz", "rover.rviz"
            ])],
            parameters=[{"use_sim_time": True}],
            condition=IfCondition(use_rviz), output="screen",
        ),
    ])

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    IfElseSubstitution,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    headless = LaunchConfiguration("headless")
    world = LaunchConfiguration("world")
    world_default = PathJoinSubstitution([
        FindPackageShare("so101_gazebo_bringup"), "worlds", "so101_demo.sdf"
    ])
    description = Command([
        FindExecutable(name="xacro"), " ",
        PathJoinSubstitution([
            FindPackageShare("so101_description"), "urdf", "so101.urdf.xacro"
        ]),
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            "headless", default_value="false",
            description="Run Gazebo server without its GUI",
        ),
        DeclareLaunchArgument(
            "world", default_value=world_default,
            description="Gazebo SDF world path",
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"
            ])),
            launch_arguments={
                "gz_args": [
                    IfElseSubstitution(
                        headless,
                        if_value=" -r -s -v 3 ",
                        else_value=" -r -v 3 ",
                    ),
                    world,
                ]
            }.items(),
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
            arguments=["-name", "so101", "-topic", "robot_description", "-z", "0.02"],
            output="screen",
        ),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
            parameters=[{"use_sim_time": True}],
            output="screen",
        ),
        Node(
            package="controller_manager",
            executable="spawner",
            arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
            output="screen",
        ),
        Node(
            package="controller_manager",
            executable="spawner",
            arguments=["so101", "--controller-manager", "/controller_manager"],
            output="screen",
        ),
    ])

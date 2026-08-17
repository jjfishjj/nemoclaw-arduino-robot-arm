from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("map", description="Absolute path to a saved map YAML"),
        DeclareLaunchArgument("use_rviz", default_value="true"),
        DeclareLaunchArgument("use_foxglove", default_value="true"),
        DeclareLaunchArgument("headless", default_value="false"),
        DeclareLaunchArgument("world", default_value=PathJoinSubstitution([
            FindPackageShare("rover_description"), "worlds", "rover_test.sdf"
        ])),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([
                FindPackageShare("rover_bringup"), "launch", "gazebo_rover.launch.py"
            ])),
            launch_arguments={
                "navigation_mode": "localization",
                "map": LaunchConfiguration("map"),
                "use_rviz": LaunchConfiguration("use_rviz"),
                "use_foxglove": LaunchConfiguration("use_foxglove"),
                "headless": LaunchConfiguration("headless"),
                "world": LaunchConfiguration("world"),
            }.items(),
        ),
    ])

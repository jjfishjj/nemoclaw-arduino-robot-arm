from glob import glob

from setuptools import find_packages, setup

package_name = "rover_navigation"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", glob("config/*.json") + glob("config/*.txt")),
    ],
    package_data={package_name: ["dashboard_template.html"]},
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Rover Forge Maintainer",
    maintainer_email="maintainer@example.com",
    description="Navigation, patrol, frontier exploration, and KPI tools for Rover Forge.",
    license="MIT",
    entry_points={"console_scripts": [
        "follow_mapping_loop = rover_navigation.follow_mapping_loop:main",
        "navigate_to_pose = rover_navigation.navigate_to_pose:main",
        "follow_waypoints = rover_navigation.mission_client:waypoint_main",
        "navigate_through_poses = rover_navigation.mission_client:through_poses_main",
        "frontier_explorer = rover_navigation.frontier_explorer:main",
        "nav_evaluator = rover_navigation.nav_evaluator:main",
        "randomize_world = rover_navigation.random_world:main",
        "benchmark_summary = rover_navigation.benchmark_summary:main",
        "benchmark_dashboard = rover_navigation.dashboard_report:main",
        "benchmark_gate = rover_navigation.benchmark_gate:main",
        "performance_report = rover_navigation.performance_report:main",
    ]},
)

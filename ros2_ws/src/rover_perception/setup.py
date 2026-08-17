from setuptools import find_packages, setup

package_name = "rover_perception"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Rover Forge Maintainer",
    maintainer_email="maintainer@example.com",
    description="LiDAR obstacle detection for Rover Forge.",
    license="MIT",
    entry_points={"console_scripts": [
        "obstacle_detector = rover_perception.obstacle_detector:main",
        "safety_velocity_filter = rover_perception.safety_velocity_filter:main",
        "lidar_contract_test = rover_perception.lidar_contract_test:main",
    ]},
)

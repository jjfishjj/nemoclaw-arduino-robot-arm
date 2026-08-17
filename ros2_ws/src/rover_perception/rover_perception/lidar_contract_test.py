import math
import statistics

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class ScanCollector(Node):
    def __init__(self) -> None:
        super().__init__("lidar_contract_test")
        self.scans = []
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)

    def on_scan(self, msg: LaserScan) -> None:
        self.scans.append(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScanCollector()
    deadline = node.get_clock().now().nanoseconds + 5_000_000_000
    while len(node.scans) < 20 and node.get_clock().now().nanoseconds < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)

    try:
        if len(node.scans) < 10:
            raise RuntimeError(f"expected at least 10 scans, received {len(node.scans)}")
        first = node.scans[0]
        if first.header.frame_id != "lidar_link":
            raise RuntimeError(f"unexpected frame_id: {first.header.frame_id}")
        if len(first.ranges) != 720:
            raise RuntimeError(f"expected 720 beams, received {len(first.ranges)}")
        center = len(first.ranges) // 2
        front = [scan.ranges[center] for scan in node.scans if math.isfinite(scan.ranges[center])]
        if not front or min(front) >= 1.0:
            raise RuntimeError("occlusion panel was not detected within 1.0 m")
        spread = statistics.pstdev(front)
        if spread <= 0.0001:
            raise RuntimeError("scan samples show no measurable noise")
        print(f"PASS: {len(node.scans)} scans, 720 beams, front={statistics.mean(front):.3f} m, noise_std={spread:.4f} m")
    finally:
        node.destroy_node()
        rclpy.shutdown()

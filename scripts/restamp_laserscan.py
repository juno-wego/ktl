#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class LaserScanRestamper(Node):
    def __init__(self):
        super().__init__("laser_scan_restamper")
        self._publisher = self.create_publisher(LaserScan, "scan_out", 10)
        self._subscription = self.create_subscription(
            LaserScan, "scan_in", self._on_scan, qos_profile_sensor_data
        )

    def _on_scan(self, msg):
        msg.header.stamp = self.get_clock().now().to_msg()
        self._publisher.publish(msg)


def main():
    rclpy.init()
    node = LaserScanRestamper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

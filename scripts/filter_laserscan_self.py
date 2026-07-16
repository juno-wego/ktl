#!/usr/bin/env python3

"""Remove LaserScan endpoints that fall inside the Go2 body footprint."""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class LaserScanSelfFilter(Node):
    def __init__(self):
        super().__init__("go2_laser_scan_self_filter")
        self._min_x = self.declare_parameter("min_x", -0.37).value
        self._max_x = self.declare_parameter("max_x", 0.43).value
        self._min_y = self.declare_parameter("min_y", -0.24).value
        self._max_y = self.declare_parameter("max_y", 0.24).value
        self._padding = self.declare_parameter("padding", 0.02).value
        self._publisher = self.create_publisher(
            LaserScan, "scan_out", qos_profile_sensor_data
        )
        self._subscription = self.create_subscription(
            LaserScan, "scan_in", self._on_scan, qos_profile_sensor_data
        )

    def _on_scan(self, msg):
        min_x = self._min_x - self._padding
        max_x = self._max_x + self._padding
        min_y = self._min_y - self._padding
        max_y = self._max_y + self._padding

        for index, distance in enumerate(msg.ranges):
            if not math.isfinite(distance):
                continue
            angle = msg.angle_min + index * msg.angle_increment
            x = distance * math.cos(angle)
            y = distance * math.sin(angle)
            if min_x <= x <= max_x and min_y <= y <= max_y:
                # Infinite range allows the obstacle layer to clear this ray.
                msg.ranges[index] = math.inf

        self._publisher.publish(msg)


def main():
    rclpy.init()
    node = LaserScanSelfFilter()
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

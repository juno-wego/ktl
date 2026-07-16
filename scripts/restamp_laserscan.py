#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


MAX_STAMP_OFFSET_SECONDS = 0.2


class LaserScanRestamper(Node):
    def __init__(self):
        super().__init__("laser_scan_restamper")
        self._max_stamp_offset = MAX_STAMP_OFFSET_SECONDS
        self._last_warning_ns = 0
        self._publisher = self.create_publisher(LaserScan, "scan_out", 10)
        self._subscription = self.create_subscription(
            LaserScan, "scan_in", self._on_scan, qos_profile_sensor_data
        )

    def _on_scan(self, msg):
        now = self.get_clock().now()
        source_stamp_ns = (
            msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        )
        offset = abs(now.nanoseconds - source_stamp_ns) / 1_000_000_000

        # .18과 .222의 시간이 맞으면 LiDAR가 기록한 측정 시각을 그대로 쓴다.
        # 시계가 크게 어긋났거나 timestamp가 비어 있으면 Jetson 수신 시각으로 대체한다.
        if source_stamp_ns == 0 or offset > self._max_stamp_offset:
            msg.header.stamp = now.to_msg()

            if now.nanoseconds - self._last_warning_ns >= 5_000_000_000:
                self.get_logger().warn(
                    "LaserScan timestamp differs from Jetson time by "
                    f"{offset:.3f} s; using the receive time instead."
                )
                self._last_warning_ns = now.nanoseconds

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

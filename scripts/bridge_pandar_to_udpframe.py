#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Header

from hesai_lidar.msg._pandar_scan import PandarScan
from hesai_lidar.msg._udp_frame import UdpFrame
from hesai_lidar.msg._udp_packet import UdpPacket


class PandarToUdpFrameBridge(Node):
    def __init__(self):
        super().__init__("pandar_to_udpframe_bridge")
        self._frame_id = str(
            self.declare_parameter("frame_id", "hesai_lidar").value
        )

        qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
        )

        self._publisher = self.create_publisher(
            UdpFrame, "udp_frame_out", qos
        )
        self._subscription = self.create_subscription(
            PandarScan, "pandar_scan_in", self._on_scan, qos
        )

    def _on_scan(self, msg: PandarScan) -> None:
        out = UdpFrame()
        out.header = Header()
        out.header.frame_id = self._frame_id
        out.header.stamp = (
            msg.packets[0].stamp
            if msg.packets
            else self.get_clock().now().to_msg()
        )

        for packet in msg.packets:
            out_packet = UdpPacket()
            out_packet.stamp = packet.stamp
            out_packet.data = packet.data
            out_packet.size = packet.size
            out.packets.append(out_packet)

        self._publisher.publish(out)


def main():
    rclpy.init()
    node = PandarToUdpFrameBridge()
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

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ktl_share = FindPackageShare("ktl")
    default_config = PathJoinSubstitution([ktl_share, "config", "hesai", "xt16_config.yaml"])

    return LaunchDescription(
        [
            DeclareLaunchArgument("config_path", default_value=default_config),
            Node(
                package="hesai_ros_driver",
                executable="hesai_ros_driver_node",
                name="hesai_xt16_driver",
                output="screen",
                parameters=[{"config_path": LaunchConfiguration("config_path")}],
            ),
        ]
    )

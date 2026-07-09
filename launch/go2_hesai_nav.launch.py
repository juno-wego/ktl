import os
import sys
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _activate_local_debs():
    for parent in Path(__file__).resolve().parents:
        local_ros = parent / ".local_ros" / "opt" / "ros" / os.environ.get("ROS_DISTRO", "humble")
        if local_ros.exists():
            local_ubuntu = parent / ".local_ubuntu"
            _prepend_env("AMENT_PREFIX_PATH", str(local_ros))
            _prepend_env("CMAKE_PREFIX_PATH", str(local_ros))
            _prepend_env("LD_LIBRARY_PATH", str(local_ros / "lib"))
            _prepend_env("LD_LIBRARY_PATH", str(local_ros / "lib" / "aarch64-linux-gnu"))
            _prepend_env("PYTHONPATH", str(local_ros / "local" / "lib" / "python3.10" / "dist-packages"))
            _prepend_env("PYTHONPATH", str(local_ros / "lib" / "python3.10" / "site-packages"))
            sys.path.insert(0, str(local_ros / "local" / "lib" / "python3.10" / "dist-packages"))
            sys.path.insert(0, str(local_ros / "lib" / "python3.10" / "site-packages"))
            if local_ubuntu.exists():
                _prepend_env("LD_LIBRARY_PATH", str(local_ubuntu / "usr" / "lib"))
                _prepend_env("LD_LIBRARY_PATH", str(local_ubuntu / "usr" / "lib" / "aarch64-linux-gnu"))
            break


def _prepend_env(name, value):
    if not value:
        return
    current = [item for item in os.environ.get(name, "").split(":") if item]
    if value in current:
        current.remove(value)
    os.environ[name] = ":".join([value] + current)


def _cyclonedds_setup(context, *_args, **_kwargs):
    network_interface = LaunchConfiguration("network_interface").perform(context).strip()
    if not network_interface:
        return []
    return [
        SetEnvironmentVariable("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp"),
        SetEnvironmentVariable(
            "CYCLONEDDS_URI",
            "<CycloneDDS><Domain><General><Interfaces>"
            f'<NetworkInterface name="{network_interface}" priority="default" multicast="default" />'
            "</Interfaces></General></Domain></CycloneDDS>",
        ),
    ]


def _validate_nav_inputs(context, *_args, **_kwargs):
    map_path = LaunchConfiguration("map").perform(context).strip()
    if not map_path:
        raise RuntimeError(
            "Navigation requires a saved map yaml. Launch with map:=/absolute/path/to/map.yaml"
        )
    if not Path(map_path).exists():
        raise FileNotFoundError(map_path)
    return []


def generate_launch_description():
    _activate_local_debs()

    ktl_share = FindPackageShare("ktl")
    go2_base_share = FindPackageShare("go2_base")
    nav2_share = FindPackageShare("nav2_bringup")
    nav2_params = PathJoinSubstitution([ktl_share, "config", "nav2", "go2_hesai_nav2_params.yaml"])
    default_rviz = PathJoinSubstitution([nav2_share, "rviz", "nav2_default_view.rviz"])

    network_interface = LaunchConfiguration("network_interface")
    use_sim_time = LaunchConfiguration("use_sim_time")

    return LaunchDescription(
        [
            DeclareLaunchArgument("network_interface", default_value="eno1"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("enable_control", default_value="true"),
            DeclareLaunchArgument("start_rviz", default_value="true"),
            DeclareLaunchArgument("rviz_config", default_value=default_rviz),
            DeclareLaunchArgument("map", default_value=""),
            DeclareLaunchArgument("autostart", default_value="true"),
            DeclareLaunchArgument("use_composition", default_value="False"),
            DeclareLaunchArgument("hesai_cloud_topic", default_value="/rslidar_points"),
            DeclareLaunchArgument("hesai_cloud_restamped_topic", default_value="/hesai/rslidar_points_restamped"),
            DeclareLaunchArgument("scan_topic", default_value="/scan"),
            DeclareLaunchArgument("scan_raw_topic", default_value="/hesai/scan_raw"),
            DeclareLaunchArgument("scan_frame", default_value="base_link"),
            DeclareLaunchArgument("nav2_params_file", default_value=nav2_params),
            OpaqueFunction(function=_cyclonedds_setup),
            OpaqueFunction(function=_validate_nav_inputs),
            GroupAction(
                scoped=True,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            PathJoinSubstitution([go2_base_share, "launch", "go2_bringup.launch.py"])
                        ),
                        launch_arguments={
                            "network_interface": network_interface,
                            "enable_control": LaunchConfiguration("enable_control"),
                            "enable_bridge": "true",
                            "enable_description": "true",
                            "start_rviz": "false",
                            "use_sim_time": use_sim_time,
                        }.items(),
                    ),
                ],
            ),
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name="base_link_to_base_tf",
                arguments=["0", "0", "0", "0", "0", "0", "base_link", "base"],
            ),
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name="base_link_to_pandar_tf",
                arguments=["0", "0", "0", "0", "0", "0", "base_link", "pandar"],
            ),
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name="base_link_to_rslidar_tf",
                arguments=["0", "0", "0", "0", "0", "0", "base_link", "rslidar"],
            ),
            Node(
                package="ktl",
                executable="restamp_pointcloud2.py",
                name="hesai_pointcloud_restamper",
                output="screen",
                remappings=[
                    ("cloud_in", LaunchConfiguration("hesai_cloud_topic")),
                    ("cloud_out", LaunchConfiguration("hesai_cloud_restamped_topic")),
                ],
                parameters=[{"use_sim_time": use_sim_time}],
            ),
            Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="hesai_pointcloud_to_laserscan",
                output="screen",
                remappings=[
                    ("cloud_in", LaunchConfiguration("hesai_cloud_restamped_topic")),
                    ("scan", LaunchConfiguration("scan_raw_topic")),
                ],
                parameters=[
                    {
                        "target_frame": LaunchConfiguration("scan_frame"),
                        "min_height": -0.30,
                        "max_height": 0.50,
                        "angle_min": -3.14159,
                        "angle_max": 3.14159,
                        "angle_increment": 0.0087,
                        "scan_time": 0.1,
                        "range_min": 0.1,
                        "range_max": 20.0,
                        "use_inf": True,
                    }
                ],
            ),
            Node(
                package="ktl",
                executable="restamp_laserscan.py",
                name="hesai_scan_restamper",
                output="screen",
                remappings=[
                    ("scan_in", LaunchConfiguration("scan_raw_topic")),
                    ("scan_out", LaunchConfiguration("scan_topic")),
                ],
                parameters=[{"use_sim_time": use_sim_time}],
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([nav2_share, "launch", "localization_launch.py"])
                ),
                launch_arguments={
                    "map": LaunchConfiguration("map"),
                    "use_sim_time": use_sim_time,
                    "autostart": LaunchConfiguration("autostart"),
                    "params_file": LaunchConfiguration("nav2_params_file"),
                    "use_composition": LaunchConfiguration("use_composition"),
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([nav2_share, "launch", "navigation_launch.py"])
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "autostart": LaunchConfiguration("autostart"),
                    "params_file": LaunchConfiguration("nav2_params_file"),
                    "use_composition": LaunchConfiguration("use_composition"),
                }.items(),
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                arguments=["-d", LaunchConfiguration("rviz_config")],
                output="screen",
                condition=IfCondition(LaunchConfiguration("start_rviz")),
            ),
        ]
    )

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ktl_share = FindPackageShare("ktl")
    go2_base_share = FindPackageShare("go2_base")
    slam_share = FindPackageShare("slam_toolbox")

    slam_params = PathJoinSubstitution(
        [
            ktl_share,
            "config",
            "slam",
            "go2_slam_toolbox.yaml",
        ]
    )

    rviz_config = PathJoinSubstitution(
        [
            ktl_share,
            "rviz",
            "go2_mapping.rviz",
        ]
    )
    laser_scan_params = PathJoinSubstitution(
        [
            ktl_share,
            "config",
            "laser_scan",
            "go2_pointcloud_to_laserscan.yaml",
        ]
    )

    network_interface = LaunchConfiguration("network_interface")
    use_sim_time = LaunchConfiguration("use_sim_time")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "network_interface",
                default_value="eno1",
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="false",
            ),
            DeclareLaunchArgument(
                "enable_control",
                default_value="false",
            ),
            DeclareLaunchArgument(
                "rviz",
                default_value="true",
            ),
            DeclareLaunchArgument(
                "rviz_config",
                default_value=rviz_config,
            ),
            DeclareLaunchArgument(
                "slam_params_file",
                default_value=slam_params,
            ),

            # bringup에서 생성되는 PointCloud 입력
            DeclareLaunchArgument(
                "cloud_topic",
                default_value="/hesai/lidar_points",
            ),

            # pointcloud_to_laserscan 출력
            DeclareLaunchArgument(
                "scan_raw_topic",
                default_value="/hesai/scan_raw",
            ),

            # 로봇 + 센서 전체 bringup
            GroupAction(
                scoped=True,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            PathJoinSubstitution(
                                [
                                    go2_base_share,
                                    "launch",
                                    "go2_bringup.launch.py",
                                ]
                            )
                        ),
                        launch_arguments={
                            "network_interface": network_interface,
                            "enable_control": LaunchConfiguration(
                                "enable_control"
                            ),
                            "rebase_odom_on_start": "true",
                            "rviz": "false",
                            "use_sim_time": use_sim_time,
                        }.items(),
                    ),
                ],
            ),

            # LiDAR PointCloud → 2D LaserScan
            Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="go2_pointcloud_to_laserscan",
                output="screen",
                remappings=[
                    (
                        "cloud_in",
                        LaunchConfiguration("cloud_topic"),
                    ),
                    (
                        "scan",
                        LaunchConfiguration("scan_raw_topic"),
                    ),
                ],
                parameters=[
                    laser_scan_params,
                    {
                        "use_sim_time": use_sim_time,
                    }
                ],
            ),

            # LaserScan timestamp 보정
            Node(
                package="ktl",
                executable="restamp_laserscan.py",
                name="hesai_scan_restamper",
                output="screen",
                remappings=[
                    (
                        "scan_in",
                        LaunchConfiguration("scan_raw_topic"),
                    ),
                    (
                        "scan_out",
                        "/scan",
                    ),
                ],
                parameters=[
                    {
                        "use_sim_time": use_sim_time,
                    }
                ],
            ),

            # SLAM Toolbox
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [
                            slam_share,
                            "launch",
                            "online_async_launch.py",
                        ]
                    )
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "slam_params_file": LaunchConfiguration(
                        "slam_params_file"
                    ),
                }.items(),
            ),

            # Mapping 전용 RViz
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                arguments=[
                    "-d",
                    LaunchConfiguration("rviz_config"),
                ],
                output="screen",
                condition=IfCondition(
                    LaunchConfiguration("rviz")
                ),
            ),
        ]
    )

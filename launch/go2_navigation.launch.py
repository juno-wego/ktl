#!/usr/bin/env python3

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
    # ------------------------------------------------------------------
    # 저장된 맵과 RViz 실행 여부를 외부에서 조정할 수 있다.
    # ------------------------------------------------------------------
    map_yaml = LaunchConfiguration("map")

    # ------------------------------------------------------------------
    # 패키지 경로
    # ------------------------------------------------------------------
    ktl_share = FindPackageShare("ktl")
    go2_base_share = FindPackageShare("go2_base")
    nav2_bringup_share = FindPackageShare("nav2_bringup")

    # ------------------------------------------------------------------
    # 프로젝트 내부 고정 설정
    # ------------------------------------------------------------------
    nav2_params_file = PathJoinSubstitution(
        [
            ktl_share,
            "config",
            "nav2",
            "go2_nav2_params.yaml",
        ]
    )

    rviz_config_file = PathJoinSubstitution(
        [
            ktl_share,
            "rviz",
            "go2_navigation.rviz",
        ]
    )

    return LaunchDescription(
        [
            # map은 저장된 기본 맵을 사용하며, 필요하면 경로를 덮어쓸 수 있다.
            DeclareLaunchArgument(
                "map",
                default_value=PathJoinSubstitution(
                    [ktl_share, "maps", "map_260710_1.yaml"]
                ),
                description="저장된 Occupancy Grid map YAML 파일 경로",
            ),
            DeclareLaunchArgument(
                "rviz",
                default_value="true",
                description="RViz 실행 여부",
            ),

            # ----------------------------------------------------------
            # Go2 로봇 및 센서 Bringup
            #
            # 포함되는 기능:
            # - robot_state_publisher / URDF
            # - Go2 상태 브리지
            # - Go2 cmd_vel 제어 브리지
            # - LiDAR packet bridge and driver
            # - LiDAR PointCloud
            # ----------------------------------------------------------
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
                            "network_interface": "eno1",
                            "enable_control": "true",
                            "enable_bridge": "true",
                            "enable_description": "true",
                            "enable_hesai": "true",
                            "rviz": "false",
                            "use_sim_time": "false",
                        }.items(),
                    ),
                ],
            ),

            # ----------------------------------------------------------
            # LiDAR PointCloud → LaserScan
            #
            # base_link 기준 높이 범위:
            #   -0.15 m ~ 0.45 m
            #
            # Go2 특성상:
            # - 지면 노이즈를 일부 제거
            # - 낮은 장애물은 감지
            # - 로봇 상부와 천장 포인트는 제외
            # ----------------------------------------------------------
            Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="go2_pointcloud_to_laserscan",
                output="screen",
                remappings=[
                    (
                        "cloud_in",
                        "/hesai/lidar_points",
                    ),
                    (
                        "scan",
                        "/scan",
                    ),
                ],
                parameters=[
                    {
                        "target_frame": "base_link",
                        "transform_tolerance": 0.1,

                        "min_height": -0.15,
                        "max_height": 0.45,

                        "angle_min": -3.141592,
                        "angle_max": 3.141592,
                        "angle_increment": 0.0087,

                        "scan_time": 0.1,

                        "range_min": 0.20,
                        "range_max": 20.0,

                        "use_inf": True,
                        "inf_epsilon": 1.0,

                        "use_sim_time": False,
                    }
                ],
            ),

            # ----------------------------------------------------------
            # Nav2
            #
            # bringup_launch.py가 실행하는 주요 노드:
            # - map_server
            # - amcl
            # - controller_server
            # - planner_server
            # - behavior_server
            # - bt_navigator
            # - waypoint_follower
            # - lifecycle_manager
            # ----------------------------------------------------------
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [
                            nav2_bringup_share,
                            "launch",
                            "bringup_launch.py",
                        ]
                    )
                ),
                launch_arguments={
                    "map": map_yaml,
                    "params_file": nav2_params_file,
                    "use_sim_time": "false",
                    "autostart": "true",
                    # Nav2 Humble uses PythonExpression("not <value>")
                    # for these two arguments, so use Python booleans.
                    "slam": "False",
                    "use_composition": "False",
                }.items(),
            ),

            # ----------------------------------------------------------
            # Navigation 전용 RViz
            # ----------------------------------------------------------
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=[
                    "-d",
                    rviz_config_file,
                ],
                condition=IfCondition(LaunchConfiguration("rviz")),
            ),
        ]
    )

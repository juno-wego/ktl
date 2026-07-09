import os
import sys
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
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


def generate_launch_description():
    _activate_local_debs()

    ktl_share = FindPackageShare("ktl")
    nav2_share = FindPackageShare("nav2_bringup")
    default_rviz_config = PathJoinSubstitution(
        [nav2_share, "rviz", "nav2_default_view.rviz"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("network_interface", default_value="eno1"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("enable_control", default_value="true"),
            DeclareLaunchArgument("start_rviz", default_value="true"),
            DeclareLaunchArgument("rviz_config", default_value=default_rviz_config),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([ktl_share, "launch", "go2_slam.launch.py"])
                ),
                launch_arguments={
                    "network_interface": LaunchConfiguration("network_interface"),
                    "use_sim_time": LaunchConfiguration("use_sim_time"),
                    "enable_control": LaunchConfiguration("enable_control"),
                    "start_go2": "true",
                    "start_slam": "true",
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([ktl_share, "launch", "go2_nav.launch.py"])
                ),
                launch_arguments={
                    "use_sim_time": LaunchConfiguration("use_sim_time"),
                    "autostart": "true",
                    "use_composition": "False",
                    "start_nav2": "true",
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

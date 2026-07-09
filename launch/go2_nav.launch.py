import os
import sys
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
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

    nav2_share = FindPackageShare("nav2_bringup")
    ktl_share = FindPackageShare("ktl")
    nav2_params_file = PathJoinSubstitution([ktl_share, "config", "nav2", "go2_nav2_params.yaml"])

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("autostart", default_value="true"),
            DeclareLaunchArgument("nav2_params_file", default_value=nav2_params_file),
            DeclareLaunchArgument("use_composition", default_value="False"),
            DeclareLaunchArgument("start_nav2", default_value="true"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([nav2_share, "launch", "navigation_launch.py"])
                ),
                launch_arguments={
                    "use_sim_time": LaunchConfiguration("use_sim_time"),
                    "autostart": LaunchConfiguration("autostart"),
                    "params_file": LaunchConfiguration("nav2_params_file"),
                    "use_composition": LaunchConfiguration("use_composition"),
                }.items(),
                condition=IfCondition(LaunchConfiguration("start_nav2")),
            ),
        ]
    )

#!/usr/bin/env bash

# Source this after /opt/ros/humble/setup.bash when ROS debs were extracted
# under the workspace because sudo apt install is not available.

_ktl_ws_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
_local_ros_prefix="${_ktl_ws_root}/.local_ros/opt/ros/${ROS_DISTRO:-humble}"
_local_ubuntu_prefix="${_ktl_ws_root}/.local_ubuntu"

if [[ ! -d "${_local_ros_prefix}" ]]; then
  echo "Local ROS deb prefix was not found: ${_local_ros_prefix}" >&2
  if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return 1
  fi
  exit 1
fi

export AMENT_PREFIX_PATH="${_local_ros_prefix}:${AMENT_PREFIX_PATH:-}"
export CMAKE_PREFIX_PATH="${_local_ros_prefix}:${CMAKE_PREFIX_PATH:-}"
export LD_LIBRARY_PATH="${_local_ros_prefix}/lib:${_local_ros_prefix}/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="${_local_ros_prefix}/local/lib/python3.10/dist-packages:${_local_ros_prefix}/lib/python3.10/site-packages:${PYTHONPATH:-}"

if [[ -d "${_local_ubuntu_prefix}" ]]; then
  export LD_LIBRARY_PATH="${_local_ubuntu_prefix}/usr/lib:${_local_ubuntu_prefix}/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH}"
fi

echo "Local ROS deb prefix is active: ${_local_ros_prefix}"

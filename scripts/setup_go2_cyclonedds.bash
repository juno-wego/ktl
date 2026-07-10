#!/usr/bin/env bash

# Source this file, do not execute it:
#   source scripts/setup_go2_cyclonedds.bash [network_interface]

_go2_setup_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_go2_env_file="${_go2_setup_root}/config/go2/go2_network.env"

if [[ -f "${_go2_env_file}" ]]; then
  # shellcheck disable=SC1090
  source "${_go2_env_file}"
fi

GO2_ROBOT_IP="${GO2_ROBOT_IP:-192.168.123.161}"
ROS_DISTRO="${ROS_DISTRO:-humble}"
GO2_NET_IFACE="${1:-${GO2_NET_IFACE:-}}"

if [[ -z "${GO2_NET_IFACE}" ]]; then
  GO2_NET_IFACE="$(ip -o -4 route get "${GO2_ROBOT_IP}" 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}')"
fi

if [[ -z "${GO2_NET_IFACE}" ]]; then
  GO2_NET_IFACE="$(ip -o -4 addr show | awk '$4 ~ /^192\.168\.123\./ {print $2; exit}')"
fi

if [[ -z "${GO2_NET_IFACE}" ]]; then
  echo "Go2 network interface was not found."
  echo "Pass it explicitly, for example:"
  echo "  source scripts/setup_go2_cyclonedds.bash enp3s0"
  echo
  echo "Current IPv4 interfaces:"
  ip -o -4 addr show | awk '{print "  " $2 "  " $4}'
  if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return 1
  fi
  exit 1
fi

_go2_template="${_go2_setup_root}/config/cyclonedds/go2_eth.template.xml"
_go2_runtime_dir="${_go2_setup_root}/.runtime/cyclonedds"
_go2_runtime_xml="${_go2_runtime_dir}/go2_${GO2_NET_IFACE}.xml"

mkdir -p "${_go2_runtime_dir}"
sed "s/@NETWORK_INTERFACE@/${GO2_NET_IFACE}/g" "${_go2_template}" > "${_go2_runtime_xml}"

if [[ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
else
  echo "Warning: /opt/ros/${ROS_DISTRO}/setup.bash was not found."
fi

_unitree_ros2_setup="${_go2_setup_root}/../unitree_ros2/cyclonedds_ws/install/setup.bash"

if [[ -n "${GO2_EXTRA_SETUP:-}" && -f "${GO2_EXTRA_SETUP}" ]]; then
  # shellcheck disable=SC1090
  source "${GO2_EXTRA_SETUP}"
elif [[ -f "${_unitree_ros2_setup}" ]]; then
  # shellcheck disable=SC1090
  source "${_unitree_ros2_setup}"
elif [[ -f "${HOME}/ros2_ws/install/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "${HOME}/ros2_ws/install/setup.bash"
fi

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://${_go2_runtime_xml}"
export GO2_NET_IFACE
export GO2_ROBOT_IP

echo "Go2 CycloneDDS environment is ready."
echo "  interface: ${GO2_NET_IFACE}"
echo "  robot ip : ${GO2_ROBOT_IP}"
echo "  rmw      : ${RMW_IMPLEMENTATION}"
echo "  dds xml  : ${CYCLONEDDS_URI}"

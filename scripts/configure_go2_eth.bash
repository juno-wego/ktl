#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1090
source "${ROOT_DIR}/config/go2/go2_network.env"

IFACE="${1:-${GO2_NET_IFACE:-}}"
HOST_IP="${GO2_HOST_IP:-192.168.123.99}"
NETMASK_CIDR="${GO2_NETMASK_CIDR:-24}"

if [[ -z "${IFACE}" ]]; then
  echo "Usage: $0 <network_interface>"
  echo
  echo "Current IPv4 interfaces:"
  ip -o -4 addr show | awk '{print "  " $2 "  " $4}'
  exit 1
fi

if ! ip link show "${IFACE}" >/dev/null 2>&1; then
  echo "Network interface does not exist: ${IFACE}" >&2
  exit 1
fi

sudo ip link set "${IFACE}" up
sudo ip addr flush dev "${IFACE}"
sudo ip addr add "${HOST_IP}/${NETMASK_CIDR}" dev "${IFACE}"

echo "Configured ${IFACE} as ${HOST_IP}/${NETMASK_CIDR}"
echo "Test robot reachability with:"
echo "  ping ${GO2_ROBOT_IP:-192.168.123.161}"


#!/usr/bin/env bash
set -euo pipefail

# Build the Go2 ROS2 workspace with the system Python environment.
# Usage:
#   ./src/ktl/scripts/build_go2_workspace.bash
#   ./src/ktl/scripts/build_go2_workspace.bash /home/juno/ros2_ws

WORKSPACE="${1:-${HOME}/ros2_ws}"
ROS_DISTRO="${ROS_DISTRO:-humble}"
CLEAN_PYTHON_CACHE="${CLEAN_PYTHON_CACHE:-1}"

if [[ -n "${CONDA_PREFIX:-}" ]]; then
  echo "Conda environment is active: ${CONDA_PREFIX}"
  echo "Run 'conda deactivate' until '(base)' disappears, then retry."
  exit 1
fi

if [[ "$(command -v python3)" != "/usr/bin/python3" ]]; then
  echo "python3 is not /usr/bin/python3: $(command -v python3)"
  echo "ROS2 Humble build should use the system Python."
  echo "Try:"
  echo "  conda deactivate"
  echo "  export PATH=/usr/bin:/bin:/usr/sbin:/sbin:\$PATH"
  exit 1
fi

if ! /usr/bin/python3 -c "import catkin_pkg" >/dev/null 2>&1; then
  echo "Missing Python package: catkin_pkg"
  echo "Install it with:"
  echo "  sudo apt install -y python3-catkin-pkg"
  exit 1
fi

if ! dpkg-query -W -f='${Status}' ros-"${ROS_DISTRO}"-rosidl-generator-dds-idl 2>/dev/null | grep -q "install ok installed"; then
  echo "Missing ROS package: ros-${ROS_DISTRO}-rosidl-generator-dds-idl"
  echo "Install it with:"
  echo "  sudo apt install -y ros-${ROS_DISTRO}-rosidl-generator-dds-idl"
  exit 1
fi

source "/opt/ros/${ROS_DISTRO}/setup.bash"

cd "${WORKSPACE}"

if [[ "${CLEAN_PYTHON_CACHE}" == "1" && -d build ]]; then
  mapfile -t CONDA_CMAKE_CACHES < <(grep -RIl "${HOME}/anaconda3/bin/python3" build --include CMakeCache.txt 2>/dev/null || true)
  if (( ${#CONDA_CMAKE_CACHES[@]} > 0 )); then
    echo "Found CMake caches using conda Python. Removing affected package build directories:"
    for cache_file in "${CONDA_CMAKE_CACHES[@]}"; do
      package_build_dir="$(dirname "${cache_file}")"
      echo "  ${package_build_dir}"
      rm -rf "${package_build_dir}"
    done
  fi
fi

rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3

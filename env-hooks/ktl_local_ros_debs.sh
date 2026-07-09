_ktl_ws_root="$(dirname "$(dirname "$AMENT_CURRENT_PREFIX")")"
_ktl_local_ros_prefix="${_ktl_ws_root}/.local_ros/opt/ros/${ROS_DISTRO:-humble}"
_ktl_local_ubuntu_prefix="${_ktl_ws_root}/.local_ubuntu"

if [ -d "$_ktl_local_ros_prefix" ]; then
  ament_prepend_unique_value AMENT_PREFIX_PATH "$_ktl_local_ros_prefix"
  ament_prepend_unique_value CMAKE_PREFIX_PATH "$_ktl_local_ros_prefix"
  ament_prepend_unique_value LD_LIBRARY_PATH "$_ktl_local_ros_prefix/lib"
  ament_prepend_unique_value LD_LIBRARY_PATH "$_ktl_local_ros_prefix/lib/aarch64-linux-gnu"
  ament_prepend_unique_value PYTHONPATH "$_ktl_local_ros_prefix/local/lib/python3.10/dist-packages"
  ament_prepend_unique_value PYTHONPATH "$_ktl_local_ros_prefix/lib/python3.10/site-packages"
fi

if [ -d "$_ktl_local_ubuntu_prefix" ]; then
  ament_prepend_unique_value LD_LIBRARY_PATH "$_ktl_local_ubuntu_prefix/usr/lib"
  ament_prepend_unique_value LD_LIBRARY_PATH "$_ktl_local_ubuntu_prefix/usr/lib/aarch64-linux-gnu"
fi

unset _ktl_ws_root
unset _ktl_local_ros_prefix
unset _ktl_local_ubuntu_prefix

cmake_minimum_required(VERSION 3.8)
project(ktl)

find_package(ament_cmake REQUIRED)

ament_environment_hooks(
  "${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/ktl_local_ros_debs.sh"
)

install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/ament_cmake_environment_hooks/local_setup.bash"
  "${CMAKE_CURRENT_BINARY_DIR}/ament_cmake_environment_hooks/local_setup.dsv"
  "${CMAKE_CURRENT_BINARY_DIR}/ament_cmake_environment_hooks/local_setup.sh"
  "${CMAKE_CURRENT_BINARY_DIR}/ament_cmake_environment_hooks/local_setup.zsh"
  DESTINATION share/${PROJECT_NAME}
)

install(FILES
  "${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/ktl_local_ros_debs.sh"
  DESTINATION share/${PROJECT_NAME}/environment
)

install(DIRECTORY
  config
  launch
  maps
  rviz
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/configure_go2_eth.bash
  scripts/restamp_laserscan.py
  scripts/restamp_pointcloud2.py
  scripts/setup_go2_cyclonedds.bash
  scripts/setup_local_ros_debs.bash
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()

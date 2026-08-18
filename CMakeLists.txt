cmake_minimum_required(VERSION 3.8)
project(ktl)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

add_executable(stable_pointcloud_to_laserscan src/stable_pointcloud_to_laserscan.cpp)
ament_target_dependencies(stable_pointcloud_to_laserscan rclcpp sensor_msgs)

install(TARGETS
  stable_pointcloud_to_laserscan
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  behavior_trees
  config
  launch
  maps
  rviz
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/restamp_laserscan.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()

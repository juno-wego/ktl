cmake_minimum_required(VERSION 3.8)
project(ktl)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  config
  launch
  maps
  rviz
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/filter_laserscan_self.py
  scripts/restamp_laserscan.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()

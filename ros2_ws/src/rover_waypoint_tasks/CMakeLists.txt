cmake_minimum_required(VERSION 3.8)
project(rover_waypoint_tasks)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav2_core REQUIRED)
find_package(nav2_util REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(sensor_msgs REQUIRED)

add_library(mission_task_executor SHARED src/mission_task_executor.cpp)
target_include_directories(mission_task_executor PUBLIC include)
ament_target_dependencies(mission_task_executor
  geometry_msgs nav2_core nav2_util pluginlib rclcpp rclcpp_lifecycle sensor_msgs)
pluginlib_export_plugin_description_file(nav2_core waypoint_task_plugins.xml)

install(TARGETS mission_task_executor
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)
install(FILES waypoint_task_plugins.xml DESTINATION share/${PROJECT_NAME})
ament_export_include_directories(include)
ament_export_libraries(mission_task_executor)
ament_export_dependencies(geometry_msgs nav2_core nav2_util pluginlib rclcpp rclcpp_lifecycle sensor_msgs)
ament_package()

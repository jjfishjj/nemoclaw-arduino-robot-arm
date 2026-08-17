cmake_minimum_required(VERSION 3.8)
project(rover_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)
install(PROGRAMS
  scripts/smoke_test.sh
  scripts/gazebo_smoke_test.sh
  scripts/collision_monitor_smoke_test.sh
  scripts/collect_gpu_metrics.sh
  scripts/autonomy_smoke_test.sh
  scripts/localization_smoke_test.sh
  scripts/navigation_smoke_test.sh
  scripts/open_benchmark_dashboard.sh
  scripts/record_benchmark_mcap.sh
  scripts/save_slam_map.sh
  scripts/run_navigation_benchmark.sh
  scripts/run_random_benchmark.sh
  scripts/slam_loop_test.sh
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()

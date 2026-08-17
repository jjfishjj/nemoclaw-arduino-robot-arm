#pragma once

#include <mutex>
#include <string>
#include <vector>

#include "nav2_core/waypoint_task_executor.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"

namespace rover_waypoint_tasks
{
class MissionTaskExecutor : public nav2_core::WaypointTaskExecutor
{
public:
  void initialize(
    const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
    const std::string & plugin_name) override;
  bool processAtWaypoint(
    const geometry_msgs::msg::PoseStamped & pose,
    const int & waypoint_index) override;

private:
  bool savePhoto(int waypoint_index);
  bool saveScan(int waypoint_index);
  bool waitForConfirmation(int waypoint_index);
  std::string artifactPath(int waypoint_index, const std::string & suffix) const;

  rclcpp_lifecycle::LifecycleNode::SharedPtr node_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_sub_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
  sensor_msgs::msg::Image::SharedPtr latest_image_;
  sensor_msgs::msg::LaserScan::SharedPtr latest_scan_;
  std::mutex data_mutex_;
  std::vector<std::string> tasks_;
  std::string output_directory_;
  int confirmation_timeout_seconds_{120};
};
}  // namespace rover_waypoint_tasks

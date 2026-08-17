#include "rover_waypoint_tasks/mission_task_executor.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <thread>

#include "nav2_util/node_utils.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace rover_waypoint_tasks
{
void MissionTaskExecutor::initialize(
  const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
  const std::string & plugin_name)
{
  node_ = parent.lock();
  if (!node_) {
    throw std::runtime_error("Failed to lock waypoint follower node");
  }
  nav2_util::declare_parameter_if_not_declared(
    node_, plugin_name + ".tasks",
    rclcpp::ParameterValue(std::vector<std::string>{"photo", "lidar_snapshot", "operator_confirm"}));
  nav2_util::declare_parameter_if_not_declared(
    node_, plugin_name + ".output_directory", rclcpp::ParameterValue(std::string("/tmp/rover_waypoint_tasks")));
  nav2_util::declare_parameter_if_not_declared(
    node_, plugin_name + ".confirmation_timeout_seconds", rclcpp::ParameterValue(120));
  node_->get_parameter(plugin_name + ".tasks", tasks_);
  node_->get_parameter(plugin_name + ".output_directory", output_directory_);
  node_->get_parameter(plugin_name + ".confirmation_timeout_seconds", confirmation_timeout_seconds_);
  if (tasks_.empty()) {
    throw std::runtime_error("Waypoint mission task list must not be empty");
  }
  std::filesystem::create_directories(output_directory_);
  image_sub_ = node_->create_subscription<sensor_msgs::msg::Image>(
    "/camera/image_raw", rclcpp::SensorDataQoS(),
    [this](sensor_msgs::msg::Image::SharedPtr msg) {
      std::lock_guard<std::mutex> lock(data_mutex_); latest_image_ = msg;
    });
  scan_sub_ = node_->create_subscription<sensor_msgs::msg::LaserScan>(
    "/scan", rclcpp::SensorDataQoS(),
    [this](sensor_msgs::msg::LaserScan::SharedPtr msg) {
      std::lock_guard<std::mutex> lock(data_mutex_); latest_scan_ = msg;
    });
}

std::string MissionTaskExecutor::artifactPath(int index, const std::string & suffix) const
{
  return output_directory_ + "/waypoint_" + std::to_string(index) + suffix;
}

bool MissionTaskExecutor::savePhoto(int index)
{
  std::lock_guard<std::mutex> lock(data_mutex_);
  if (!latest_image_ || latest_image_->encoding != "rgb8") {
    RCLCPP_ERROR(node_->get_logger(), "No rgb8 camera frame available at waypoint %d", index);
    return false;
  }
  std::ofstream out(artifactPath(index, ".ppm"), std::ios::binary);
  out << "P6\n" << latest_image_->width << " " << latest_image_->height << "\n255\n";
  for (uint32_t row = 0; row < latest_image_->height; ++row) {
    const auto offset = static_cast<size_t>(row) * latest_image_->step;
    out.write(reinterpret_cast<const char *>(latest_image_->data.data() + offset), latest_image_->width * 3);
  }
  return out.good();
}

bool MissionTaskExecutor::saveScan(int index)
{
  std::lock_guard<std::mutex> lock(data_mutex_);
  if (!latest_scan_) {
    RCLCPP_ERROR(node_->get_logger(), "No LaserScan available at waypoint %d", index);
    return false;
  }
  std::ofstream out(artifactPath(index, "_scan.csv"));
  out << "angle_rad,range_m\n";
  for (size_t i = 0; i < latest_scan_->ranges.size(); ++i) {
    out << std::setprecision(9)
        << latest_scan_->angle_min + static_cast<double>(i) * latest_scan_->angle_increment
        << "," << latest_scan_->ranges[i] << "\n";
  }
  return out.good();
}

bool MissionTaskExecutor::waitForConfirmation(int index)
{
  const auto confirmation = artifactPath(index, ".confirm");
  RCLCPP_WARN(
    node_->get_logger(), "Waiting for operator confirmation: touch %s", confirmation.c_str());
  const auto deadline = std::chrono::steady_clock::now() +
    std::chrono::seconds(confirmation_timeout_seconds_);
  while (std::chrono::steady_clock::now() < deadline) {
    if (std::filesystem::exists(confirmation)) {
      std::filesystem::remove(confirmation);
      return true;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }
  RCLCPP_ERROR(node_->get_logger(), "Operator confirmation timed out at waypoint %d", index);
  return false;
}

bool MissionTaskExecutor::processAtWaypoint(
  const geometry_msgs::msg::PoseStamped &, const int & waypoint_index)
{
  const auto & task = tasks_.at(static_cast<size_t>(waypoint_index) % tasks_.size());
  RCLCPP_INFO(node_->get_logger(), "Waypoint %d task: %s", waypoint_index, task.c_str());
  if (task == "photo") {return savePhoto(waypoint_index);}
  if (task == "lidar_snapshot") {return saveScan(waypoint_index);}
  if (task == "operator_confirm") {return waitForConfirmation(waypoint_index);}
  RCLCPP_ERROR(node_->get_logger(), "Unknown waypoint task: %s", task.c_str());
  return false;
}
}  // namespace rover_waypoint_tasks

PLUGINLIB_EXPORT_CLASS(rover_waypoint_tasks::MissionTaskExecutor, nav2_core::WaypointTaskExecutor)

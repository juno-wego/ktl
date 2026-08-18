#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <functional>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "sensor_msgs/point_cloud2_iterator.hpp"

using namespace std::chrono_literals;

class StablePointCloudToLaserScan : public rclcpp::Node
{
public:
  StablePointCloudToLaserScan()
  : Node("go2_pointcloud_to_laserscan")
  {
    target_frame_ = declare_parameter<std::string>("target_frame", "hesai_lidar");
    transform_tolerance_ = declare_parameter<double>("transform_tolerance", 0.1);
    min_height_ = declare_parameter<double>("min_height", -0.2);
    max_height_ = declare_parameter<double>("max_height", 0.3);
    angle_min_ = declare_parameter<double>("angle_min", -3.141592);
    angle_max_ = declare_parameter<double>("angle_max", 3.141592);
    angle_increment_ = declare_parameter<double>("angle_increment", 0.0087);
    scan_time_ = declare_parameter<double>("scan_time", 0.1);
    range_min_ = declare_parameter<double>("range_min", 0.5);
    range_max_ = declare_parameter<double>("range_max", 30.0);
    use_inf_ = declare_parameter<bool>("use_inf", true);
    inf_epsilon_ = declare_parameter<double>("inf_epsilon", 1.0);
    queue_size_ = declare_parameter<int>("queue_size", 1);
    watchdog_timeout_ = declare_parameter<double>("watchdog_timeout", 2.0);

    if (angle_increment_ <= 0.0 || angle_max_ <= angle_min_) {
      throw std::invalid_argument("Invalid LaserScan angle range or increment");
    }
    if (range_min_ < 0.0 || range_max_ <= range_min_) {
      throw std::invalid_argument("Invalid LaserScan distance range");
    }
    if (min_height_ > max_height_) {
      throw std::invalid_argument("min_height must not exceed max_height");
    }

    scan_publisher_ = create_publisher<sensor_msgs::msg::LaserScan>(
      "scan", rclcpp::SensorDataQoS().keep_last(5));
    create_cloud_subscription();

    last_cloud_time_ = now();
    watchdog_timer_ = create_wall_timer(500ms, std::bind(&StablePointCloudToLaserScan::watchdog, this));

    RCLCPP_INFO(
      get_logger(),
      "Stable PointCloud->LaserScan active: cloud=%s scan=%s range=[%.2f, %.2f] m, "
      "watchdog=%.1f s",
      cloud_topic_name_.c_str(), scan_publisher_->get_topic_name(), range_min_, range_max_,
      watchdog_timeout_);
  }

private:
  void create_cloud_subscription()
  {
    const auto qos = rclcpp::SensorDataQoS().keep_last(
      static_cast<std::size_t>(std::max(1, queue_size_)));
    cloud_subscription_ = create_subscription<sensor_msgs::msg::PointCloud2>(
      "cloud_in", qos,
      std::bind(&StablePointCloudToLaserScan::on_cloud, this, std::placeholders::_1));
    cloud_topic_name_ = cloud_subscription_->get_topic_name();
  }

  void on_cloud(const sensor_msgs::msg::PointCloud2::SharedPtr cloud)
  {
    last_cloud_time_ = now();
    if (waiting_for_recovery_) {
      RCLCPP_INFO(
        get_logger(), "PointCloud subscription recovered after %zu reset(s).", reset_count_);
      waiting_for_recovery_ = false;
    }

    if (!target_frame_.empty() && cloud->header.frame_id != target_frame_) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 5000,
        "PointCloud frame is '%s', expected '%s'. Processing in the source frame.",
        cloud->header.frame_id.c_str(), target_frame_.c_str());
    }

    sensor_msgs::msg::LaserScan scan;
    scan.header = cloud->header;
    scan.angle_min = static_cast<float>(angle_min_);
    scan.angle_max = static_cast<float>(angle_max_);
    scan.angle_increment = static_cast<float>(angle_increment_);
    scan.time_increment = 0.0F;
    scan.scan_time = static_cast<float>(scan_time_);
    scan.range_min = static_cast<float>(range_min_);
    scan.range_max = static_cast<float>(range_max_);

    const auto beam_count = static_cast<std::size_t>(
      std::ceil((angle_max_ - angle_min_) / angle_increment_));
    const float empty_value = use_inf_ ?
      std::numeric_limits<float>::infinity() :
      static_cast<float>(range_max_ + inf_epsilon_);
    scan.ranges.assign(beam_count, empty_value);

    try {
      sensor_msgs::PointCloud2ConstIterator<float> iter_x(*cloud, "x");
      sensor_msgs::PointCloud2ConstIterator<float> iter_y(*cloud, "y");
      sensor_msgs::PointCloud2ConstIterator<float> iter_z(*cloud, "z");

      for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z) {
        const float x = *iter_x;
        const float y = *iter_y;
        const float z = *iter_z;
        if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
          continue;
        }
        if (z < min_height_ || z > max_height_) {
          continue;
        }

        const double range = std::hypot(static_cast<double>(x), static_cast<double>(y));
        if (range < range_min_ || range > range_max_) {
          continue;
        }

        const double angle = std::atan2(static_cast<double>(y), static_cast<double>(x));
        if (angle < angle_min_ || angle > angle_max_) {
          continue;
        }

        const auto index = static_cast<std::size_t>((angle - angle_min_) / angle_increment_);
        if (index < scan.ranges.size() && range < scan.ranges[index]) {
          scan.ranges[index] = static_cast<float>(range);
        }
      }
    } catch (const std::runtime_error & error) {
      RCLCPP_ERROR_THROTTLE(
        get_logger(), *get_clock(), 5000, "Invalid PointCloud2 layout: %s", error.what());
      return;
    }

    scan_publisher_->publish(scan);
  }

  void watchdog()
  {
    if (watchdog_timeout_ <= 0.0 || count_publishers(cloud_topic_name_) == 0U) {
      return;
    }

    const double silence = (now() - last_cloud_time_).seconds();
    if (silence <= watchdog_timeout_) {
      return;
    }

    ++reset_count_;
    waiting_for_recovery_ = true;
    RCLCPP_WARN(
      get_logger(),
      "No PointCloud callback for %.2f s while a publisher exists; resetting the DDS subscription "
      "(attempt %zu).",
      silence, reset_count_);

    cloud_subscription_.reset();
    create_cloud_subscription();
    last_cloud_time_ = now();
  }

  std::string target_frame_;
  std::string cloud_topic_name_;
  double transform_tolerance_{0.1};
  double min_height_{-0.2};
  double max_height_{0.3};
  double angle_min_{-3.141592};
  double angle_max_{3.141592};
  double angle_increment_{0.0087};
  double scan_time_{0.1};
  double range_min_{0.5};
  double range_max_{30.0};
  double inf_epsilon_{1.0};
  double watchdog_timeout_{2.0};
  int queue_size_{1};
  bool use_inf_{true};
  bool waiting_for_recovery_{false};
  std::size_t reset_count_{0};
  rclcpp::Time last_cloud_time_;

  rclcpp::Publisher<sensor_msgs::msg::LaserScan>::SharedPtr scan_publisher_;
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr cloud_subscription_;
  rclcpp::TimerBase::SharedPtr watchdog_timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<StablePointCloudToLaserScan>());
  rclcpp::shutdown();
  return 0;
}

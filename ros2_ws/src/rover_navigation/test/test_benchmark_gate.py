import json
import unittest
from pathlib import Path

from rover_navigation.benchmark_gate import attach_runner_metrics, evaluate_gate


REPO_ROOT = Path(__file__).resolve().parents[4]

THRESHOLDS = {
    "minimum_trial_success_rate": 0.9,
    "minimum_waypoint_success_rate": 0.95,
    "maximum_contact_collision_rate_per_goal": 0.0,
    "minimum_mean_stop_distance_m": 0.3,
    "maximum_timeout_rate": 0.0,
    "minimum_mean_real_time_factor": 0.75,
    "minimum_mean_gazebo_update_fps": 20.0,
    "maximum_peak_gpu_memory_mib": 12000.0,
    "maximum_mean_planning_latency_ms": 750.0,
    "maximum_mcap_size_mib": 2048.0,
    "maximum_job_queue_seconds": 1800.0,
}


class BenchmarkGateTest(unittest.TestCase):
    def test_runner_queue_metric_is_attached(self):
        merged = attach_runner_metrics(
            {"trial_count": 1}, {"job_queue_seconds": 42, "image_id": "gpu-image-1"}
        )
        self.assertEqual(merged["job_queue_seconds"], 42)
        self.assertEqual(merged["runner_image_id"], "gpu-image-1")
        queue_thresholds = {
            "maximum_timeout_rate": 0.0,
            "maximum_job_queue_seconds": 60,
        }
        self.assertEqual(evaluate_gate(merged, queue_thresholds), [])
        self.assertIn(
            "job_queue_seconds: 42 > allowed 30",
            evaluate_gate(merged, {**queue_thresholds, "maximum_job_queue_seconds": 30}),
        )

    def test_passing_summary(self):
        report = {
            "trial_count": 10, "trial_success_rate": 0.9,
            "mean_waypoint_success_rate": 0.96,
            "contact_collision_rate_per_goal": 0.0,
            "mean_minimum_stop_distance_m": 0.31, "timeout_rate": 0.0,
            "mean_real_time_factor": 0.9, "peak_gpu_memory_mib": 4096.0,
            "mean_gazebo_update_fps": 60.0, "job_queue_seconds": 42.0,
            "mean_planning_latency_ms": 150.0, "maximum_mcap_size_mib": 512.0,
        }
        self.assertEqual(evaluate_gate(report, THRESHOLDS), [])

    def test_reports_all_regressions(self):
        report = {
            "trial_count": 2, "trial_success_rate": 0.5,
            "mean_waypoint_success_rate": 0.7,
            "contact_collision_rate_per_goal": 0.1,
            "mean_minimum_stop_distance_m": 0.2, "timeout_rate": 0.5,
            "mean_real_time_factor": 0.5, "peak_gpu_memory_mib": 13000.0,
            "mean_gazebo_update_fps": 10.0, "job_queue_seconds": 2400.0,
            "mean_planning_latency_ms": 900.0, "maximum_mcap_size_mib": 2500.0,
        }
        violations = evaluate_gate(report, THRESHOLDS)
        self.assertEqual(len(violations), 11)

    def test_missing_safety_metric_fails_closed(self):
        report = {
            "trial_count": 2, "trial_success_rate": 1.0,
            "mean_waypoint_success_rate": 1.0,
            "contact_collision_rate_per_goal": 0.0, "timeout_rate": 0.0,
            "mean_real_time_factor": 0.9, "peak_gpu_memory_mib": 4096.0,
            "mean_gazebo_update_fps": 60.0,
            "mean_planning_latency_ms": 150.0, "maximum_mcap_size_mib": 512.0,
        }
        self.assertTrue(any("missing" in item for item in evaluate_gate(report, THRESHOLDS)))

    def test_performance_metric_missing_fails_closed(self):
        report = {
            "trial_count": 2, "trial_success_rate": 1.0,
            "mean_waypoint_success_rate": 1.0,
            "contact_collision_rate_per_goal": 0.0,
            "mean_minimum_stop_distance_m": 0.4, "timeout_rate": 0.0,
        }
        violations = evaluate_gate(report, THRESHOLDS)
        self.assertEqual(sum("missing" in item for item in violations), 6)

    def test_ci_offline_summary_uses_only_available_metrics(self):
        report = json.loads(
            (REPO_ROOT / "ros2_ws/test_data/benchmark/ci_baseline_summary.json").read_text()
        )
        offline_thresholds = json.loads(
            (REPO_ROOT / "ros2_ws/src/rover_navigation/config/ci_offline_thresholds.json").read_text()
        )
        runtime_thresholds = json.loads(
            (REPO_ROOT / "ros2_ws/src/rover_navigation/config/benchmark_thresholds.json").read_text()
        )

        self.assertEqual(evaluate_gate(report, offline_thresholds), [])
        self.assertNotIn("minimum_mean_gazebo_update_fps", offline_thresholds)
        self.assertNotIn("maximum_job_queue_seconds", offline_thresholds)
        self.assertIn(
            "mean_gazebo_update_fps: missing (required for gate)",
            evaluate_gate(report, runtime_thresholds),
        )
        self.assertIn("minimum_mean_gazebo_update_fps", runtime_thresholds)
        self.assertIn("maximum_job_queue_seconds", runtime_thresholds)


if __name__ == "__main__":
    unittest.main()

import unittest

from rover_navigation.benchmark_gate import evaluate_gate


THRESHOLDS = {
    "minimum_trial_success_rate": 0.9,
    "minimum_waypoint_success_rate": 0.95,
    "maximum_contact_collision_rate_per_goal": 0.0,
    "minimum_mean_stop_distance_m": 0.3,
    "maximum_timeout_rate": 0.0,
    "minimum_mean_real_time_factor": 0.75,
    "maximum_peak_gpu_memory_mib": 12000.0,
    "maximum_mean_planning_latency_ms": 750.0,
    "maximum_mcap_size_mib": 2048.0,
}


class BenchmarkGateTest(unittest.TestCase):
    def test_passing_summary(self):
        report = {
            "trial_count": 10, "trial_success_rate": 0.9,
            "mean_waypoint_success_rate": 0.96,
            "contact_collision_rate_per_goal": 0.0,
            "mean_minimum_stop_distance_m": 0.31, "timeout_rate": 0.0,
            "mean_real_time_factor": 0.9, "peak_gpu_memory_mib": 4096.0,
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
            "mean_planning_latency_ms": 900.0, "maximum_mcap_size_mib": 2500.0,
        }
        violations = evaluate_gate(report, THRESHOLDS)
        self.assertEqual(len(violations), 9)

    def test_missing_safety_metric_fails_closed(self):
        report = {
            "trial_count": 2, "trial_success_rate": 1.0,
            "mean_waypoint_success_rate": 1.0,
            "contact_collision_rate_per_goal": 0.0, "timeout_rate": 0.0,
            "mean_real_time_factor": 0.9, "peak_gpu_memory_mib": 4096.0,
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
        self.assertEqual(sum("missing" in item for item in violations), 4)


if __name__ == "__main__":
    unittest.main()

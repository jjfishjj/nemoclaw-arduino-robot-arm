import unittest

from rover_navigation.benchmark_summary import summarize
from rover_navigation.random_world import sample_obstacles


class BenchmarkTest(unittest.TestCase):
    def test_random_obstacles_are_reproducible_and_clear_of_patrol(self):
        first = sample_obstacles(7, 8)
        self.assertEqual(first, sample_obstacles(7, 8))
        self.assertEqual(len(first), 8)

    def test_summary_uses_real_contact_events(self):
        reports = [
            {"navigation_success": True, "success_rate": 1.0, "elapsed_seconds": 10,
             "path_length_m": 4, "minimum_stop_distance_m": 0.4,
             "goal_count": 5, "contact_collision_events": 0,
             "real_time_factor": 0.9, "mean_planning_latency_ms": 100,
             "peak_gpu_memory_mib": 3000, "peak_gpu_memory_utilization_ratio": 0.4,
             "peak_gpu_temperature_c": 60, "mean_gpu_utilization_percent": 50,
             "minimum_disk_free_gib": 80, "mcap_size_mib": 400},
            {"navigation_success": False, "success_rate": 0.6, "elapsed_seconds": 20,
             "path_length_m": 3, "minimum_stop_distance_m": None,
             "goal_count": 5, "contact_collision_events": 2,
             "real_time_factor": 0.8, "mean_planning_latency_ms": 200,
             "peak_gpu_memory_mib": 4000, "peak_gpu_memory_utilization_ratio": 0.5,
             "peak_gpu_temperature_c": 65, "mean_gpu_utilization_percent": 70,
             "minimum_disk_free_gib": 70, "mcap_size_mib": 500},
        ]
        result = summarize(reports)
        self.assertEqual(result["trial_success_rate"], 0.5)
        self.assertEqual(result["mean_waypoint_success_rate"], 0.8)
        self.assertEqual(result["contact_collision_rate_per_goal"], 0.2)
        self.assertAlmostEqual(result["mean_real_time_factor"], 0.85)
        self.assertEqual(result["mean_planning_latency_ms"], 150.0)
        self.assertEqual(result["peak_gpu_memory_mib"], 4000.0)
        self.assertEqual(result["maximum_mcap_size_mib"], 500.0)

    def test_empty_summary_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == "__main__":
    unittest.main()

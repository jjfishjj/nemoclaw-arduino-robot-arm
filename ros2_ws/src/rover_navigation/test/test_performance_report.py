import tempfile
import unittest
from pathlib import Path

from rover_navigation.performance_report import (
    directory_size_bytes,
    enrich_report,
    summarize_gpu_csv,
)


class PerformanceReportTest(unittest.TestCase):
    def test_gpu_csv_and_mcap_are_summarized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "gpu.csv"
            csv_path.write_text(
                "epoch_seconds,gpu_index,gpu_utilization_percent,memory_used_mib,"
                "memory_total_mib,temperature_c,power_draw_w,disk_free_gib\n"
                "1,0,20,1000,8000,55,80,90\n"
                "2,0,80,3000,8000,65,120,89\n"
            )
            bag = root / "bag"
            bag.mkdir()
            (bag / "sample.mcap").write_bytes(b"x" * 1024)
            gpu = summarize_gpu_csv(csv_path)
            report = enrich_report({"schema_version": 2}, gpu, directory_size_bytes(bag))
            self.assertEqual(report["mean_gpu_utilization_percent"], 50.0)
            self.assertEqual(report["peak_gpu_memory_mib"], 3000.0)
            self.assertEqual(report["peak_gpu_memory_utilization_ratio"], 0.375)
            self.assertEqual(report["minimum_disk_free_gib"], 89.0)
            self.assertEqual(report["mcap_size_bytes"], 1024)
            self.assertEqual(report["schema_version"], 3)

    def test_empty_gpu_csv_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gpu.csv"
            path.write_text("gpu_utilization_percent\n")
            with self.assertRaises(ValueError):
                summarize_gpu_csv(path)


if __name__ == "__main__":
    unittest.main()

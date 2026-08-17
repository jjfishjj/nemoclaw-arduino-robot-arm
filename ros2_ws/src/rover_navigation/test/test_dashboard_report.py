import json
import tempfile
import unittest
from pathlib import Path

from rover_navigation.dashboard_report import load_reports, render_dashboard


REPORT = {
    "goal_count": 5, "completed_goals": 5, "navigation_success": True,
    "success_rate": 1.0, "elapsed_seconds": 10.0, "path_length_m": 4.0,
    "contact_collision_events": 0,
}


class DashboardReportTest(unittest.TestCase):
    def test_standalone_dashboard_embeds_report(self):
        report = dict(REPORT, trial_name="seed_1")
        output = render_dashboard([report], "<Rover>")
        self.assertIn("<!doctype html>", output)
        self.assertIn("&lt;Rover&gt;", output)
        self.assertIn('"trial_name":"seed_1"', output)
        self.assertNotIn("__DASHBOARD_DATA__", output)

    def test_load_reports_validates_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trial.json"
            path.write_text(json.dumps(REPORT))
            loaded = load_reports([path])
            self.assertEqual(loaded[0]["trial_name"], "trial")
            path.write_text("{}")
            with self.assertRaises(ValueError):
                load_reports([path])


if __name__ == "__main__":
    unittest.main()

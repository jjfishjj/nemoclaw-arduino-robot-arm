import json
import tempfile
import unittest
from pathlib import Path

from rover_navigation.mission_math import load_route, success_rate


class MissionMathTest(unittest.TestCase):
    def write_route(self, value):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "route.json"
        path.write_text(json.dumps(value))
        return directory, path

    def test_loads_valid_route(self):
        directory, path = self.write_route({"poses": [{"x": 1, "y": 2, "yaw": 0}]})
        try:
            self.assertEqual(load_route(path), ("map", [(1.0, 2.0, 0.0)]))
        finally:
            directory.cleanup()

    def test_rejects_empty_route(self):
        directory, path = self.write_route({"poses": []})
        try:
            with self.assertRaises(ValueError):
                load_route(path)
        finally:
            directory.cleanup()

    def test_success_rate_boundaries(self):
        self.assertEqual(success_rate(3, 4), 0.75)
        with self.assertRaises(ValueError):
            success_rate(5, 4)


if __name__ == "__main__":
    unittest.main()

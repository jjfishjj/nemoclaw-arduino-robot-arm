import math
import unittest

from rover_perception.scan_math import forward_ranges, obstacle_detected


class ScanMathTest(unittest.TestCase):
    def test_forward_sector_filters_invalid_and_rear_ranges(self):
        ranges = [0.5, math.inf, 0.08, 0.7, 0.4]
        values = forward_ranges(ranges, -2.0, 1.0, 1.1, 0.12)
        self.assertEqual(values, [0.7])

    def test_obstacle_threshold_is_strict_and_empty_is_safe(self):
        self.assertEqual(obstacle_detected([0.8, 1.4], 1.0), (True, 0.8))
        self.assertEqual(obstacle_detected([1.0, 1.2], 1.0), (False, 1.0))
        detected, closest = obstacle_detected([], 1.0)
        self.assertFalse(detected)
        self.assertTrue(math.isinf(closest))


if __name__ == "__main__":
    unittest.main()

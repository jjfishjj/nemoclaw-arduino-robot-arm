import math
import unittest

from rover_navigation.path_math import densify_polyline


class PathMathTest(unittest.TestCase):
    def test_densified_path_has_bounded_spacing_and_final_point(self):
        samples = densify_polyline([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)], 0.2)
        self.assertEqual(samples[-1][:2], (1.0, 1.0))
        for left, right in zip(samples, samples[1:]):
            self.assertLessEqual(math.hypot(right[0] - left[0], right[1] - left[1]), 0.200001)

    def test_invalid_path_is_rejected(self):
        with self.assertRaises(ValueError):
            densify_polyline([(0.0, 0.0)])


if __name__ == "__main__":
    unittest.main()

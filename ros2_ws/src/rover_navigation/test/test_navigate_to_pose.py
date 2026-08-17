import math
import unittest

from rover_navigation.path_math import yaw_quaternion


class NavigatePoseMathTest(unittest.TestCase):
    def test_zero_yaw(self):
        self.assertEqual(yaw_quaternion(0.0), (0.0, 1.0))

    def test_half_turn(self):
        z, w = yaw_quaternion(math.pi)
        self.assertAlmostEqual(z, 1.0)
        self.assertAlmostEqual(w, 0.0, places=7)

    def test_non_finite_yaw_is_rejected(self):
        with self.assertRaises(ValueError):
            yaw_quaternion(float("nan"))


if __name__ == "__main__":
    unittest.main()

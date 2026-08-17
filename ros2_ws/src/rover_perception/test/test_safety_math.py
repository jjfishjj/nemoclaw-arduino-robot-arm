import math
import unittest

from rover_perception.safety_math import filter_velocity


class SafetyMathTest(unittest.TestCase):
    def run_filter(self, distance, linear=0.4, angular=0.2, scan=True, command=True):
        return filter_velocity(linear, angular, distance, scan, command, 0.85, 1.50, 0.15, 0.60)

    def test_clear_keeps_command(self):
        result = self.run_filter(2.0)
        self.assertEqual((result.linear_x, result.angular_z, result.state), (0.4, 0.2, "CLEAR"))

    def test_slow_scales_linear_and_angular(self):
        result = self.run_filter(1.175)
        self.assertAlmostEqual(result.scale, 0.5)
        self.assertAlmostEqual(result.linear_x, 0.2)
        self.assertAlmostEqual(result.angular_z, 0.1)
        self.assertEqual(result.state, "SLOW")

    def test_stop_blocks_forward_but_reverse_can_escape(self):
        self.assertEqual(self.run_filter(0.8).state, "STOP")
        rotate = self.run_filter(0.8, linear=0.0, angular=0.5)
        self.assertEqual((rotate.linear_x, rotate.angular_z, rotate.state), (0.0, 0.5, "STOP"))
        capped = self.run_filter(0.8, linear=0.2, angular=1.2)
        self.assertEqual((capped.linear_x, capped.angular_z), (0.0, 0.6))
        reverse = self.run_filter(0.8, linear=-0.4)
        self.assertEqual(reverse.state, "ESCAPE")
        self.assertEqual(reverse.linear_x, -0.15)

    def test_stale_missing_or_invalid_scan_is_failsafe(self):
        for result in (
            self.run_filter(2.0, scan=False),
            self.run_filter(2.0, command=False),
            self.run_filter(math.inf),
        ):
            self.assertEqual((result.linear_x, result.angular_z, result.state), (0.0, 0.0, "FAILSAFE"))


if __name__ == "__main__":
    unittest.main()

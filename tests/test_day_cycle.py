import unittest
import time
from worldreader import calculate_day_cycle, DAY_CYCLE_LENGTH_SECONDS


class TestDayCycle(unittest.TestCase):
    def test_day_cycle_structure(self):
        cycle = calculate_day_cycle(36, time.time() - 100.0)
        self.assertIn("day_count", cycle)
        self.assertIn("progress_percent", cycle)
        self.assertIn("phase", cycle)
        self.assertIn("phase_icon", cycle)
        self.assertIn("needle_angle_deg", cycle)
        self.assertIn("seconds_in_day", cycle)
        self.assertIn("cycle_duration_seconds", cycle)
        self.assertIn("is_night", cycle)

        self.assertEqual(cycle["day_count"], 36)
        self.assertTrue(0.0 <= cycle["progress_percent"] <= 100.0)
        self.assertTrue(0.0 <= cycle["needle_angle_deg"] < 360.0)

    def test_zero_and_invalid_day_count(self):
        c_zero = calculate_day_cycle(0)
        self.assertEqual(c_zero["day_count"], 0)
        self.assertEqual(c_zero["progress_percent"], 0.0)
        self.assertEqual(c_zero["phase"], "Unknown")
        self.assertEqual(c_zero["needle_angle_deg"], 0.0)

        c_none = calculate_day_cycle(None)
        self.assertEqual(c_none["day_count"], 0)
        self.assertEqual(c_none["phase"], "Unknown")

        c_neg = calculate_day_cycle(-5)
        self.assertEqual(c_neg["day_count"], 0)
        self.assertEqual(c_neg["phase"], "Unknown")

        c_str = calculate_day_cycle("invalid")
        self.assertEqual(c_str["day_count"], 0)
        self.assertEqual(c_str["phase"], "Unknown")

    def test_fractional_day_count(self):
        # 42.0 (start of cycle) -> 210 deg (Dawn)
        c_dawn = calculate_day_cycle(42.0)
        self.assertEqual(c_dawn["progress_percent"], 0.0)
        self.assertEqual(c_dawn["needle_angle_deg"], 210.0)
        self.assertEqual(c_dawn["phase"], "Dawn / Early Morning")
        self.assertFalse(c_dawn["is_night"])

        # 42.5 (50% through cycle) -> 210 + 180 = 390 % 360 = 30 deg (Afternoon / Sunset)
        c_half = calculate_day_cycle(42.5)
        self.assertEqual(c_half["progress_percent"], 50.0)
        self.assertEqual(c_half["needle_angle_deg"], 30.0)
        self.assertEqual(c_half["phase"], "Afternoon / Sunset")
        self.assertFalse(c_half["is_night"])

    def test_day_phases(self):
        # Progress at 0s (cycle_pos = 0) -> angle 210 -> Dawn
        c_dawn = calculate_day_cycle(1, time.time())
        self.assertEqual(c_dawn["phase"], "Dawn / Early Morning")
        self.assertFalse(c_dawn["is_night"])

        # 25% through cycle (210s) -> 210 + 90 = 300 deg -> Midday / Noon
        c_midday = calculate_day_cycle(1, time.time() - 210.0)
        self.assertEqual(c_midday["phase"], "Midday / Noon")
        self.assertFalse(c_midday["is_night"])

        # 66.7% through cycle (560s) -> 210 + 240 = 450 % 360 = 90 deg -> Dusk / Early Night
        c_dusk = calculate_day_cycle(1, time.time() - 560.0)
        self.assertEqual(c_dusk["phase"], "Dusk / Early Night")
        self.assertTrue(c_dusk["is_night"])

        # 85% through cycle (714s) -> 210 + 306 = 516 % 360 = 156 deg -> Midnight
        c_midnight = calculate_day_cycle(1, time.time() - 714.0)
        self.assertEqual(c_midnight["phase"], "Midnight")
        self.assertTrue(c_midnight["is_night"])

    def test_cycle_wraparound(self):
        # Multi-cycle elapsed time
        c_wrap = calculate_day_cycle(1, time.time() - (DAY_CYCLE_LENGTH_SECONDS * 3 + 210.0))
        self.assertEqual(c_wrap["phase"], "Midday / Noon")
        self.assertAlmostEqual(c_wrap["needle_angle_deg"], 300.0, delta=1.5)


if __name__ == "__main__":
    unittest.main()

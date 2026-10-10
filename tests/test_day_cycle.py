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
        # 0
        c_zero = calculate_day_cycle(0)
        self.assertEqual(c_zero["day_count"], 0)
        self.assertEqual(c_zero["progress_percent"], 0.0)
        self.assertEqual(c_zero["phase"], "Unknown")
        self.assertEqual(c_zero["needle_angle_deg"], 0.0)

        # None
        c_none = calculate_day_cycle(None)
        self.assertEqual(c_none["day_count"], 0)
        self.assertEqual(c_none["phase"], "Unknown")

        # Negative
        c_neg = calculate_day_cycle(-5)
        self.assertEqual(c_neg["day_count"], 0)
        self.assertEqual(c_neg["phase"], "Unknown")

        # Non-numeric
        c_str = calculate_day_cycle("invalid")
        self.assertEqual(c_str["day_count"], 0)
        self.assertEqual(c_str["phase"], "Unknown")

    def test_fractional_day_count(self):
        # 42.5 means 50% through day -> 180 deg (Dusk / Twilight)
        c_half = calculate_day_cycle(42.5)
        self.assertEqual(c_half["progress_percent"], 50.0)
        self.assertEqual(c_half["needle_angle_deg"], 180.0)
        self.assertEqual(c_half["phase"], "Dusk / Twilight")
        self.assertTrue(c_half["is_night"])

        # 10.25 means 25% through day -> 90 deg (Midday)
        c_quarter = calculate_day_cycle(10.25)
        self.assertEqual(c_quarter["progress_percent"], 25.0)
        self.assertEqual(c_quarter["needle_angle_deg"], 90.0)
        self.assertEqual(c_quarter["phase"], "Midday")
        self.assertFalse(c_quarter["is_night"])

    def test_day_phases(self):
        # Progress at 0s (0 deg) -> Morning
        c_morning = calculate_day_cycle(1, time.time())
        self.assertEqual(c_morning["phase"], "Morning")
        self.assertFalse(c_morning["is_night"])

        # Progress at 210s (90 deg) -> Midday
        c_midday = calculate_day_cycle(1, time.time() - 210.0)
        self.assertEqual(c_midday["phase"], "Midday")
        self.assertFalse(c_midday["is_night"])

        # Progress at 350s (150 deg) -> Afternoon
        c_afternoon = calculate_day_cycle(1, time.time() - 350.0)
        self.assertEqual(c_afternoon["phase"], "Afternoon")
        self.assertFalse(c_afternoon["is_night"])

        # Progress at 490s (210 deg) -> Dusk / Twilight
        c_dusk = calculate_day_cycle(1, time.time() - 490.0)
        self.assertEqual(c_dusk["phase"], "Dusk / Twilight")
        self.assertTrue(c_dusk["is_night"])

        # Progress at 700s (300 deg) -> Night
        c_night = calculate_day_cycle(1, time.time() - 700.0)
        self.assertEqual(c_night["phase"], "Night")
        self.assertTrue(c_night["is_night"])

    def test_cycle_wraparound(self):
        # After 2 full cycles (1680s) + 105s (45 deg)
        c_wrap = calculate_day_cycle(1, time.time() - (DAY_CYCLE_LENGTH_SECONDS * 2 + 105.0))
        self.assertEqual(c_wrap["phase"], "Midday")
        self.assertAlmostEqual(c_wrap["needle_angle_deg"], 45.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()

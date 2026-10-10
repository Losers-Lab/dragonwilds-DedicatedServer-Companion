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

    def test_zero_day_count(self):
        cycle = calculate_day_cycle(0)
        self.assertEqual(cycle["day_count"], 0)
        self.assertEqual(cycle["progress_percent"], 0.0)
        self.assertEqual(cycle["phase"], "Unknown")
        self.assertEqual(cycle["needle_angle_deg"], 0.0)

    def test_day_phases(self):
        # Progress at 0s (0 deg) -> Morning
        c_morning = calculate_day_cycle(1, time.time())
        self.assertEqual(c_morning["phase"], "Morning")
        self.assertFalse(c_morning["is_night"])

        # Progress at 210s (90 deg) -> Midday
        c_midday = calculate_day_cycle(1, time.time() - 210.0)
        self.assertEqual(c_midday["phase"], "Midday")
        self.assertFalse(c_midday["is_night"])

        # Progress at 490s (210 deg) -> Dusk / Twilight
        c_dusk = calculate_day_cycle(1, time.time() - 490.0)
        self.assertEqual(c_dusk["phase"], "Dusk / Twilight")
        self.assertTrue(c_dusk["is_night"])

        # Progress at 700s (300 deg) -> Night
        c_night = calculate_day_cycle(1, time.time() - 700.0)
        self.assertEqual(c_night["phase"], "Night")
        self.assertTrue(c_night["is_night"])


if __name__ == "__main__":
    unittest.main()

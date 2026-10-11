import unittest
import time
from respawns import (
    format_actor_label,
    parse_duration_seconds,
    parse_log_timestamp,
    RespawnTracker
)


class TestRespawns(unittest.TestCase):
    def test_format_actor_label(self):
        # Known chest
        name1 = format_actor_label("BP_Dungeon_Treasure_Chest_BM_Cook_World_Cache_C_UAID_00BE4395530E7E0C02_1510875401")
        self.assertIn("Cook", name1)
        self.assertIn("Brynmoore", name1)
        self.assertIn("Dungeon Cache", name1)
        self.assertNotIn("BP_", name1)

        # Mining Rock
        name2 = format_actor_label("BP_MiningRock_Luminite_Static_D_C")
        self.assertIn("Luminite", name2)

        # Ore Node
        name3 = format_actor_label("BP_OreNode_Adamantite_Large_A1_C_UAID_4CD717762D110FC902_1196341990")
        self.assertIn("Adamantite", name3)

        # Edge cases
        self.assertEqual(format_actor_label(None), "Unknown Target")
        self.assertEqual(format_actor_label(""), "Unknown Target")

    def test_parse_duration_seconds(self):
        # 5 days
        s1 = parse_duration_seconds("+5.00:00:00.000")
        self.assertEqual(s1, 5 * 86400.0)

        # 1 day 23h 16m 7.741s
        s2 = parse_duration_seconds("+1.23:16:07.741")
        self.assertAlmostEqual(s2, 86400.0 + 23 * 3600.0 + 16 * 60.0 + 7.741, places=2)

        # 19 hours 20m 22.095s
        s3 = parse_duration_seconds("+19:20:22.095")
        self.assertAlmostEqual(s3, 19 * 3600.0 + 20 * 60.0 + 22.095, places=2)

        # 8 hours 56m 4.654s
        s4 = parse_duration_seconds("+08:56:04.654")
        self.assertAlmostEqual(s4, 8 * 3600.0 + 56 * 60.0 + 4.654, places=2)

        # Defensive null / invalid handling
        self.assertEqual(parse_duration_seconds(None), 0.0)
        self.assertEqual(parse_duration_seconds(""), 0.0)
        self.assertEqual(parse_duration_seconds("invalid"), 0.0)

    def test_parse_log_timestamp(self):
        ts = parse_log_timestamp("2026.10.10-19.05.28:209")
        self.assertGreater(ts, 0.0)
        self.assertEqual(parse_log_timestamp("invalid"), 0.0)
        self.assertEqual(parse_log_timestamp(None), 0.0)

    def test_respawn_tracker_filtering(self):
        tracker = RespawnTracker(logs_dir="non_existent_dir", saves_dir="non_existent_dir")
        items = tracker.get_respawns()
        self.assertIsInstance(items, list)

        # Search query
        chests = tracker.get_respawns(search_query="chest")
        for c in chests:
            self.assertTrue(
                "chest" in c["name"].lower() or "chest" in c["id"].lower() or "chest" in c["category"].lower()
            )


if __name__ == "__main__":
    unittest.main()

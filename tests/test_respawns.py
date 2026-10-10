import unittest
import time
from respawns import (
    format_actor_name,
    parse_duration_seconds,
    parse_log_timestamp,
    RespawnTracker,
    CAT_CHEST,
    CAT_FISHING,
    CAT_ORE,
    CAT_BOSS
)


class TestRespawns(unittest.TestCase):
    def test_format_actor_name(self):
        # Known chest
        name1 = format_actor_name("BP_Dungeon_Treasure_Chest_BM_Cook_World_Cache_C_UAID_00BE4395530E7E0C02_1510875401")
        self.assertEqual(name1, "Brinemoor Cook's Cache")

        # Known vault
        name2 = format_actor_name("BP_Dungeon_Treasure_Chest_BM_Weapon_Vault_Cache_C_UAID_18C04D97CB3D6B0D02_2032330069")
        self.assertEqual(name2, "Brinemoor Weapon Vault (Vault)")

        # Fishing Net
        name3 = format_actor_name("BP_FishingNodeV2_Net_Brynmoor_C_UAID_DC97BA249CD400C502_1824877563")
        self.assertEqual(name3, "Fishing Net Spot (Brynmoor)")

        # High-tier Ore
        name4 = format_actor_name("BP_OreNode_Adamantite_Large_A1_C_UAID_4CD717762D110FC902_1196341990")
        self.assertEqual(name4, "Adamantite Ore Vein")

        # Mining Rock
        name5 = format_actor_name("BP_MiningRock_Luminite_Static_D_C")
        self.assertEqual(name5, "Luminite Mining Node")

        # World Boss
        name6 = format_actor_name("BP_KalphiteQueenSpawnTrigger_C")
        self.assertEqual(name6, "Kalphite Queen")

        # Edge cases
        self.assertEqual(format_actor_name(None), "Unknown Target")
        self.assertEqual(format_actor_name(""), "Unknown Target")

    def test_parse_duration_seconds(self):
        # 5 days
        s1 = parse_duration_seconds("+5.00:00:00.000")
        self.assertEqual(s1, 5 * 86400.0)

        # 1 day 23h 16m 7.741s
        s2 = parse_duration_seconds("+1.23:16:07.741")
        self.assertAlmostEqual(s2, 86400.0 + 23 * 3600.0 + 16 * 60.0 + 7.741, places=2)

        # 19 hours 20m 22.095s (no days prefix)
        s3 = parse_duration_seconds("+19:20:22.095")
        self.assertAlmostEqual(s3, 19 * 3600.0 + 20 * 60.0 + 22.095, places=2)

        # Invalid
        self.assertEqual(parse_duration_seconds("invalid"), 0.0)

    def test_parse_log_timestamp(self):
        ts = parse_log_timestamp("2026.10.10-19.05.28:209")
        self.assertGreater(ts, 0.0)
        self.assertEqual(parse_log_timestamp("invalid"), 0.0)

    def test_respawn_tracker_filtering(self):
        tracker = RespawnTracker(logs_dir="non_existent_dir", saves_dir="non_existent_dir")
        all_items = tracker.get_respawns()
        self.assertGreater(len(all_items), 0)

        # Test category filter
        chests = tracker.get_respawns(category_filter=CAT_CHEST)
        for c in chests:
            self.assertEqual(c["category"], CAT_CHEST)

        bosses = tracker.get_respawns(category_filter=CAT_BOSS)
        self.assertGreater(len(bosses), 0)
        for b in bosses:
            self.assertEqual(b["category"], CAT_BOSS)

        # Test search query
        lumi = tracker.get_respawns(search_query="luminite")
        self.assertTrue(any("luminite" in x["name"].lower() for x in lumi))


if __name__ == "__main__":
    unittest.main()

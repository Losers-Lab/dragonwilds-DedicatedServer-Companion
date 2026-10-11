"""
Unit tests for World Actors and POI Manager with in-memory caching.
Verifies binary CORA extraction, classification, map coordinates, and cache performance.
"""

import os
import struct
import tempfile
import time
import unittest
from unittest.mock import patch

from worldactors import (
    format_actor_label,
    parse_lvl_actors,
    world_to_map_coords,
    WorldActorManager,
    get_world_actor_manager
)


def create_mock_lvl_bytes(actors_data):
    """
    Helper to synthesize binary .lvl bytes containing BP_<Class>_C_UAID_<Id>
    followed by a realistic SPUD CORA chunk with double IEEE 754 coordinates.
    """
    buffer = bytearray(b"SPUD_LVL_HEADER_DUMMY_DATA_0123456789")
    for cls_name, uaid, (x, y, z) in actors_data:
        actor_name = f"BP_{cls_name}_C_UAID_{uaid}".encode("latin1")
        buffer.extend(b"\x00\x01\x00\x00")
        buffer.extend(actor_name)
        buffer.extend(b"\x00\x00\x00\x00\x01\x00\x00\x00")

        # Synthesize CORA chunk (15 bytes header)
        cora_payload = bytearray(b"CORA\x9f\x00\x00\x00\x9b\x00\x00\x00\x01\x00\x00")
        # 32 bytes Quaternion (0, 0, 0, 1.0)
        cora_payload.extend(struct.pack("<4d", 0.0, 0.0, 0.0, 1.0))
        # 24 bytes Position (X, Y, Z)
        cora_payload.extend(struct.pack("<3d", float(x), float(y), float(z)))
        # 24 bytes Scale (1.0, 1.0, 1.0)
        cora_payload.extend(struct.pack("<3d", 1.0, 1.0, 1.0))
        # Additional padding to make up chunk
        cora_payload.extend(b"\x00" * 30)

        buffer.extend(cora_payload)
        buffer.extend(b"PROPF_DUMMY_TAIL")

    return bytes(buffer)


class TestWorldActors(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lvl_path = os.path.join(self.temp_dir.name, "RSACell12800_X0_Y13.lvl")

        # Create sample level with fishing node and NPCs
        sample_actors = [
            ("FishingNodeV2_Net_Brynmoor", "111111111111111111_1234567890", (3406.0, 178721.0, -3167.7)),
            ("FishingNodeV2_Rod_Brynmoor", "222222222222222222_2345678901", (5213.0, 178404.0, -3167.7)),
            ("NPC_WiseOldMan_FTUE", "333333333333333333_3456789012", (6133.3, 187356.6, -3546.7)),
            ("NPC_Doric_FTUE", "444444444444444444_4567890123", (10908.5, 184631.9, -3131.3)),
            ("NPC_Zanik", "555555555555555555_5678901234", (26688.3, 182395.1, -4126.5)),
            ("HealthShrine", "666666666666666666_6789012345", (52124.5, 172224.7, 500.0)),
            ("Agility_Shortcut_KebbitBurrow_Common_BM", "777777777777777777_7890123456", (73772.4, 186935.5, 800.0)),
        ]
        with open(self.lvl_path, "wb") as f:
            f.write(create_mock_lvl_bytes(sample_actors))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_format_actor_label(self):
        net_info = format_actor_label("BP_FishingNodeV2_Net_Brynmoor_C")
        self.assertEqual(net_info["category"], "fishing")
        self.assertIn("Net", net_info["title"])

        rod_info = format_actor_label("BP_FishingNodeV2_Rod_Brynmoor_C")
        self.assertEqual(rod_info["category"], "fishing")
        self.assertIn("Rod", rod_info["title"])

        wom_info = format_actor_label("BP_NPC_WiseOldMan_FTUE_C")
        self.assertEqual(wom_info["category"], "npcs")
        self.assertIn("Wise Old Man", wom_info["title"])

        doric_info = format_actor_label("BP_NPC_Doric_FTUE_C")
        self.assertEqual(doric_info["category"], "npcs")
        self.assertIn("Doric", doric_info["title"])

        shrine_info = format_actor_label("BP_HealthShrine_C")
        self.assertEqual(shrine_info["category"], "shrines")

        burrow_info = format_actor_label("BP_Agility_Shortcut_KebbitBurrow_Common_BM_C")
        self.assertEqual(burrow_info["category"], "shortcuts")

    def test_world_to_map_coords(self):
        # 1. Brynmoore Starter Shoreline landmark
        coords = world_to_map_coords(6000.0, 187000.0, 0.0)
        self.assertAlmostEqual(coords["x"], 210.0, places=1)
        self.assertAlmostEqual(coords["y"], 500.0, places=1)

        # 2. Subterranean Brynmoore Catacombs / Dungeon Chest (Z < -20000)
        bm_dungeon = world_to_map_coords(-164981.1, 93812.8, -41811.0)
        self.assertAlmostEqual(bm_dungeon["x"], 287.5, delta=1.0)
        self.assertAlmostEqual(bm_dungeon["y"], 498.9, delta=1.0)
        # Ensure not clamped to edge!
        self.assertGreater(bm_dungeon["x"], 200.0)

        # 3. Subterranean Kalphite Queen Arena (Z < -20000, X < -350000)
        kq_arena = world_to_map_coords(-456588.1, 194378.3, -36210.0)
        self.assertAlmostEqual(kq_arena["x"], 647.6, delta=1.0)
        self.assertAlmostEqual(kq_arena["y"], 627.9, delta=1.0)
        self.assertGreater(kq_arena["x"], 600.0)

        # 4. Eastern Desert Gravestone / Continental Reach
        east_point = world_to_map_coords(369817.3, 39546.5, 3104.1)
        self.assertAlmostEqual(east_point["x"], 755.7, delta=1.0)
        self.assertAlmostEqual(east_point["y"], 234.6, delta=1.0)

        # 5. Boundary Clamping Safeguard
        extreme = world_to_map_coords(-9999999.0, 9999999.0, 0.0)
        self.assertEqual(extreme["x"], 20.0)
        self.assertEqual(extreme["y"], 980.0)

    def test_parse_lvl_actors(self):
        actors = parse_lvl_actors(self.lvl_path)
        self.assertEqual(len(actors), 7)

        categories = {a["category"] for a in actors}
        self.assertIn("fishing", categories)
        self.assertIn("npcs", categories)
        self.assertIn("shrines", categories)
        self.assertIn("shortcuts", categories)

        # Verify coordinates parsed
        wom = next(a for a in actors if "WiseOldMan" in a["class_name"])
        self.assertAlmostEqual(wom["world_pos"]["x"], 6133.3, places=1)
        self.assertAlmostEqual(wom["world_pos"]["y"], 187356.6, places=1)
        self.assertAlmostEqual(wom["world_pos"]["z"], -3546.7, places=1)

    def test_in_memory_caching_performance(self):
        manager = WorldActorManager(spud_dir=self.temp_dir.name, ttl_seconds=60.0)

        # First call: cold load (reads from disk)
        res1 = manager.get_actors()
        self.assertFalse(res1["cached"])
        self.assertEqual(res1["counts"]["fishing"], 2)
        self.assertEqual(res1["counts"]["npcs"], 3)

        # Second call: warm load (served directly from RAM memory)
        t0 = time.time()
        res2 = manager.get_actors()
        t_elapsed = (time.time() - t0) * 1000
        self.assertTrue(res2["cached"])
        self.assertLess(t_elapsed, 5.0)  # Must be sub-millisecond in memory
        self.assertEqual(res2["counts"], res1["counts"])

    def test_filter_by_category(self):
        manager = WorldActorManager(spud_dir=self.temp_dir.name, ttl_seconds=60.0)
        res = manager.get_actors(categories=["fishing"])
        self.assertIn("fishing", res["actors"])
        self.assertNotIn("npcs", res["actors"])
        self.assertEqual(len(res["actors"]["fishing"]), 2)

    def test_empty_or_missing_directory(self):
        manager = WorldActorManager(spud_dir="/non_existent_directory_12345", ttl_seconds=60.0)
        res = manager.get_actors()
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["total_returned"], 0)


if __name__ == "__main__":
    unittest.main()

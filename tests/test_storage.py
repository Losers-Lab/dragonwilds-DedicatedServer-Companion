import unittest
import os
import tempfile
import shutil
import json
from storage import parse_storage_data, search_stored_items, get_storage_units, format_container_name


class TestStorageTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_saves_directory(self):
        res = parse_storage_data(saves_dir=self.temp_dir)
        self.assertEqual(res["total_containers"], 0)
        self.assertEqual(res["total_stored_items"], 0)
        self.assertEqual(res["unique_items_count"], 0)
        self.assertEqual(len(res["containers"]), 0)
        self.assertEqual(len(res["items"]), 0)

    def test_format_container_name(self):
        self.assertEqual(
            format_container_name("BP_PlayerGraveyard_8Slots_C_UAID_123", "Arham"),
            "Arham's Gravestone / Remains"
        )
        self.assertEqual(
            format_container_name("BP_PlayerGraveyard_8Slots_C_UAID_123", "World / Unowned"),
            "Player Grave Stash"
        )
        self.assertEqual(
            format_container_name("BP_BaseBuilding_Chest_Iron_C_UAID_456", "Mango"),
            "Mango's Base Chest Iron"
        )
        self.assertEqual(
            format_container_name("BP_LootChest_Prefab_Tier7_World_C_UAID_789"),
            "Tier7 World"
        )

    def test_storage_parsing_with_sample_save(self):
        save_path = os.path.join(self.temp_dir, "TestWorld.sav")
        # Build dummy binary data containing:
        # 1. An unowned loot chest
        # 2. An Arham chest with EOS ID
        loot_inv_json = json.dumps({
            "Version": 83,
            "MaxSlotIndex": 3,
            "0": {"GUID": "guid-1", "ItemData": "item-iron-ore", "Count": 50},
            "1": {"GUID": "guid-2", "ItemData": "item-coal", "Count": 20},
        }).encode("utf-8")

        arham_inv_json = json.dumps({
            "Version": 83,
            "MaxSlotIndex": 7,
            "0": {"GUID": "guid-3", "ItemData": "item-iron-ore", "Count": 150},
            "1": {"GUID": "guid-4", "ItemData": "item-gold-bar", "Count": 10},
        }).encode("utf-8")

        content = (
            b"HeaderData...BP_LootChest_Prefab_Tier6_World_C_UAID_111...PROP..." +
            loot_inv_json +
            b"...more_data...BP_BaseBuilding_Chest_Iron_C_UAID_222...RedpointEOS:000225fad0314f69844ceb408bada617...PROP..." +
            arham_inv_json
        )

        with open(save_path, "wb") as f:
            f.write(content)

        data = parse_storage_data(saves_dir=self.temp_dir)
        self.assertEqual(data["total_containers"], 2)
        self.assertEqual(data["unique_items_count"], 3)  # iron-ore, coal, gold-bar
        self.assertEqual(data["total_stored_items"], 230)  # 50 + 20 + 150 + 10

        # Check iron-ore aggregation
        iron = next(it for it in data["items"] if it["item_id"] == "item-iron-ore")
        self.assertEqual(iron["total_count"], 200)
        self.assertEqual(iron["container_count"], 2)

        # Check containers
        arham_cont = next(c for c in data["containers"] if c["owner"] == "Arham")
        self.assertIn("Arham", arham_cont["name"])
        self.assertEqual(arham_cont["occupied_slots"], 2)
        self.assertEqual(arham_cont["total_items"], 160)

    def test_search_stored_items(self):
        save_path = os.path.join(self.temp_dir, "TestSearch.sav")
        inv_json = json.dumps({
            "Version": 83,
            "MaxSlotIndex": 1,
            "0": {"GUID": "guid-1", "ItemData": "item-magic-staff", "Count": 1},
        }).encode("utf-8")
        content = b"BP_BaseBuilding_Chest_C_UAID_999...RedpointEOS:000239b86c6a4c048d2fba065f6a408a..." + inv_json

        with open(save_path, "wb") as f:
            f.write(content)

        # Search by item ID
        results_id = search_stored_items("magic-staff", saves_dir=self.temp_dir)
        self.assertEqual(len(results_id), 1)
        self.assertEqual(results_id[0]["item_id"], "item-magic-staff")

        # Search by owner name
        results_owner = search_stored_items("Mango", saves_dir=self.temp_dir)
        self.assertEqual(len(results_owner), 1)

        # Search with non-matching query
        results_none = search_stored_items("nonexistent-item", saves_dir=self.temp_dir)
        self.assertEqual(len(results_none), 0)

    def test_get_storage_units(self):
        units = get_storage_units(saves_dir=self.temp_dir)
        self.assertIsInstance(units, list)


if __name__ == '__main__':
    unittest.main()

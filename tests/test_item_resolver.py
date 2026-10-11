import unittest
import os
import tempfile
import shutil
import json
from item_resolver import resolve_item, get_item_name
from storage import parse_storage_data, search_stored_items


class TestItemResolver(unittest.TestCase):
    def test_known_guid_resolution(self):
        # Top active save items
        ash_wood = resolve_item("2rxJ495rm0GDn4h5OWKiyQ")
        self.assertEqual(ash_wood["name"], "Ash Logs")
        self.assertEqual(ash_wood["raw_id"], "res_wood_ash")
        self.assertEqual(ash_wood["category"], "Resources")

        rune_essence = resolve_item("qOY004ZJaEaR8DmcDqB2KA")
        self.assertEqual(rune_essence["name"], "Essence Rune")
        self.assertEqual(rune_essence["raw_id"], "res_rune_essence")
        self.assertEqual(rune_essence["category"], "Runes")

        redberry = resolve_item("sGZHV0IIuJLCDIyGNNBMbA")
        self.assertEqual(redberry["name"], "Fruit Dried Redberry")
        self.assertEqual(redberry["raw_id"], "food_fruit_dried_redberry")
        self.assertEqual(redberry["category"], "Food")

        clean_water = resolve_item("hKYyX0vQ_pgLRAi2ugGK3w")
        self.assertEqual(clean_water["name"], "Clean Water")
        self.assertEqual(clean_water["raw_id"], "food_water_clean")
        self.assertEqual(clean_water["category"], "Food")

        stone_block = resolve_item("_R44FI_bhEm8Gx61swlzpA")
        self.assertEqual(stone_block["name"], "Stone")
        self.assertEqual(stone_block["raw_id"], "res_stone")

    def test_identifier_fallbacks(self):
        item = resolve_item("tool_farming_seed_potato")
        self.assertEqual(item["name"], "Potato Seed")
        self.assertEqual(item["category"], "Farming")

        item2 = resolve_item("res_rune_chaos")
        self.assertEqual(item2["name"], "Chaos Rune")
        self.assertEqual(item2["category"], "Runes")

        item3 = resolve_item("food_fish_trout")
        self.assertEqual(item3["name"], "Cooked Trout")
        self.assertEqual(item3["category"], "Food")

        item4 = resolve_item("res_fish_salmon")
        self.assertEqual(item4["name"], "Raw Salmon")
        self.assertEqual(item4["category"], "Fishing")

    def test_unknown_guid_graceful_handling(self):
        unknown = resolve_item("XyZ1234567890abcdefABC")
        self.assertTrue(unknown["name"].startswith("Item (XyZ123...)"))
        self.assertEqual(unknown["category"], "Item")

        empty = resolve_item("")
        self.assertEqual(empty["name"], "Unknown Item")

    def test_storage_data_integration(self):
        temp_dir = tempfile.mkdtemp()
        try:
            save_path = os.path.join(temp_dir, "TestResolver.sav")
            inv_json = json.dumps({
                "Version": 83,
                "MaxSlotIndex": 1,
                "0": {"GUID": "slot-0", "ItemData": "2rxJ495rm0GDn4h5OWKiyQ", "Count": 100},
                "1": {"GUID": "slot-1", "ItemData": "qOY004ZJaEaR8DmcDqB2KA", "Count": 25},
            }).encode("utf-8")
            content = b"BP_BaseBuilding_Chest_C_UAID_111...RedpointEOS:000225fad0314f69844ceb408bada617..." + inv_json

            with open(save_path, "wb") as f:
                f.write(content)

            data = parse_storage_data(saves_dir=temp_dir)
            self.assertEqual(data["total_containers"], 1)
            self.assertEqual(data["unique_items_count"], 2)

            # Check resolved slot entries
            slots = data["containers"][0]["slots"]
            self.assertEqual(slots[0]["name"], "Ash Logs")
            self.assertEqual(slots[0]["raw_id"], "res_wood_ash")
            self.assertEqual(slots[0]["category"], "Resources")
            self.assertEqual(slots[1]["name"], "Essence Rune")
            self.assertEqual(slots[1]["category"], "Runes")

            # Check human-readable search
            results_ash = search_stored_items("Ash", saves_dir=temp_dir)
            self.assertEqual(len(results_ash), 1)
            self.assertEqual(results_ash[0]["name"], "Ash Logs")

            results_essence = search_stored_items("Essence", saves_dir=temp_dir)
            self.assertEqual(len(results_essence), 1)
            self.assertEqual(results_essence[0]["name"], "Essence Rune")

            results_runes = search_stored_items("Runes", saves_dir=temp_dir)
            self.assertEqual(len(results_runes), 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()

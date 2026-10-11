import unittest
import os
import tempfile
import shutil
import json
from farming import get_farming_status
from items import get_master_items


class TestFarmingAndMasterItems(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_farming_empty_saves(self):
        res = get_farming_status(saves_dir=self.temp_dir)
        self.assertIn("summary", res)
        self.assertEqual(res["summary"]["total_water_barrels"], 0)
        self.assertEqual(res["summary"]["total_rain_catchers"], 0)
        self.assertEqual(res["summary"]["total_composters"], 0)
        self.assertEqual(res["summary"]["total_growing_trees"], 0)
        self.assertEqual(len(res["structures"]), 0)

    def test_farming_save_parsing(self):
        save_path = os.path.join(self.temp_dir, "World_Test.sav")
        # Simulate binary save data containing farming archetypes
        dummy_content = (
            b"HeaderData...BP_Farm_Barrel_Water...more_data..."
            b"BP_Farm_Barrel_Water...BP_Farm_RainCatcher..."
            b"BP_Station_Composter_New...FarmingGrowingTree_StageIndex_ServerOnly"
        )
        with open(save_path, "wb") as f:
            f.write(dummy_content)

        res = get_farming_status(saves_dir=self.temp_dir)
        self.assertEqual(res["summary"]["total_water_barrels"], 2)
        self.assertEqual(res["summary"]["total_rain_catchers"], 1)
        self.assertEqual(res["summary"]["total_composters"], 1)
        self.assertEqual(res["summary"]["total_growing_trees"], 1)
        self.assertEqual(len(res["structures"]), 3)
        self.assertEqual(len(res["growing_trees"]), 1)

    def test_farming_save_parsing_zero_trees(self):
        save_path = os.path.join(self.temp_dir, "World_Test_Zero.sav")
        with open(save_path, "wb") as f:
            f.write(b"HeaderData...BP_Farm_Barrel_Water...BP_Farm_RainCatcher")

        res = get_farming_status(saves_dir=self.temp_dir)
        self.assertEqual(res["summary"]["total_water_barrels"], 1)
        self.assertEqual(res["summary"]["total_growing_trees"], 0)
        self.assertEqual(len(res["growing_trees"]), 0)
        self.assertEqual(len(res["structures"]), 2)

    def test_master_items_filtering(self):
        # Master items loads 1,704 items from data/master_items.json
        items = get_master_items()
        self.assertGreater(len(items), 1000)

        # Ensure cache defensive copy
        items.clear()
        self.assertGreater(len(get_master_items()), 1000)

        # Verify all UI dropdown categories return items
        ui_categories = ["Ammo", "Armor", "Weapons", "Resources", "Consumables", "Tools"]
        for cat in ui_categories:
            cat_items = get_master_items(category=cat)
            self.assertGreater(len(cat_items), 0, f"Category '{cat}' should return matching items")

        # Filter by search query
        arrows = get_master_items(category="Ammo", search_query="Fire")
        self.assertTrue(all("fire" in it["name"].lower() or "fire" in it["id"].lower() for it in arrows))
        self.assertGreater(len(arrows), 0)

    def test_master_items_empty_query(self):
        items = get_master_items(category="all", search_query="")
        self.assertGreaterEqual(len(items), 1700)


if __name__ == "__main__":
    unittest.main()

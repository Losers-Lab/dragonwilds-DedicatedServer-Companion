"""
Dragonwilds Farming & Agriculture Tracking Module.

Extracts objective farming states and crop telemetry from the game world:
1. Placed Farm Structures: Rain Catchers, Water Storage Barrels, Composters.
2. Active In-World Crops & Herbs: Tracks live planted and growing agricultural instances
   including Flax (Linen), Onions, Potatoes, Cabbages, Pumpkins, Swamp Weed, and Medicinal Herbs
   (Snapdragon, Sagewort, Toadflax, Bittercap Mushrooms).
3. Growing Saplings & Trees: Tracks growing tree stages (`FarmingGrowingTree_StageIndex_ServerOnly`)
   and placed saplings across all biomes.
4. Strictly Read-Only: Directly extracts actual world instances from the active `.sav` save file.
"""

import os
import glob
import re
from config import SAVES_DIR


def get_farming_status(saves_dir: str = SAVES_DIR) -> dict:
    """Scans latest world save for farming infrastructure, planted crops, herbs, and growing trees."""
    save_files = glob.glob(os.path.join(saves_dir, "*.sav"))
    if not save_files:
        return {
            "structures": [],
            "crops": [],
            "growing_trees": [],
            "summary": {
                "total_water_barrels": 0,
                "total_rain_catchers": 0,
                "total_composters": 0,
                "total_growing_trees": 0,
                "total_crops": 0,
                "total_saplings": 0
            }
        }

    newest_save = max(save_files, key=os.path.getmtime)
    try:
        with open(newest_save, "rb") as f:
            data = f.read()

        # 1. Agriculture Structures
        barrels = len(re.findall(rb'BP_Farm_Barrel_Water[A-Za-z0-9_]*_UAID_', data))
        if barrels == 0:
            barrels = data.count(b'BP_Farm_Barrel_Water')

        rain_catchers = len(re.findall(rb'BP_Farm_RainCatcher[A-Za-z0-9_]*_UAID_', data))
        if rain_catchers == 0:
            rain_catchers = data.count(b'BP_Farm_RainCatcher')

        composters = len(re.findall(rb'BP_Station_Composter_New[A-Za-z0-9_]*_UAID_', data))
        if composters == 0:
            composters = data.count(b'BP_Station_Composter_New')

        structures = []
        if barrels > 0:
            structures.append({
                "name": "Water Storage Barrel",
                "type": "Hydration / Storage",
                "count": barrels,
                "status": "Active Infrastructure"
            })
        if rain_catchers > 0:
            structures.append({
                "name": "Rain Catcher",
                "type": "Hydration / Collection",
                "count": rain_catchers,
                "status": "Active Infrastructure"
            })
        if composters > 0:
            structures.append({
                "name": "Composting Station",
                "type": "Soil & Fertilizer",
                "count": composters,
                "status": "Active Infrastructure"
            })

        # 2. Crops, Vegetables & Medicinal Herbs
        crop_catalog = [
            ("Flax (Linen)", "Textile / Crafting Crop", rb'BP_Spawner_Flax_C_UAID_|BP_Spawner_Flax_C\x00', "Harvestable / Growing"),
            ("Onions", "Vegetable Crop", rb'BP_Spawner_Onion_C_UAID_|BP_Spawner_Onion_C\x00', "Harvestable / Growing"),
            ("Potatoes", "Vegetable Crop", rb'BP_Spawner_Potato_C_UAID_|BP_Spawner_Potato_C\x00', "Harvestable / Growing"),
            ("Cabbages", "Vegetable Crop", rb'BP_Spawner_Cabbage_C_UAID_|BP_Spawner_Cabbage_C\x00', "Harvestable / Growing"),
            ("Pumpkins", "Vegetable Crop", rb'BP_Spawner_Pumpkin_[0-9]+_C_UAID_|BP_Spawner_Pumpkin_C\x00', "Harvestable / Growing"),
            ("Swamp Weed", "Herbaceous Agriculture", rb'BP_Spawner_SwampWeedPlant_C_UAID_|BP_Spawner_SwampWeedPlant_C\x00', "Active Growth"),
            ("Snapdragon", "High-Tier Medicinal Herb", rb'BP_Spawner_Snapdragon_C_UAID_|BP_Spawner_Snapdragon_C\x00', "Active Growth"),
            ("Sagewort", "Medicinal Herb", rb'BP_Spawner_Sagewort_C_UAID_|BP_Spawner_Sagewort_C\x00', "Active Growth"),
            ("Toadflax", "Medicinal Herb", rb'BP_Spawner_Toadflax_C_UAID_|BP_Spawner_Toadflax_C\x00', "Active Growth"),
            ("Bittercap Mushroom", "Fungi & Spores", rb'BP_Spawner_BittercapMushroom_C_UAID_|BP_Spawner_BittercapMushroom_C\x00', "Active Growth"),
        ]

        crops = []
        total_crops = 0
        for name, category, pattern, status in crop_catalog:
            count = len(re.findall(pattern, data))
            if count > 0:
                crops.append({
                    "name": name,
                    "category": category,
                    "count": count,
                    "status": status
                })
                total_crops += count

        # 3. Growing Saplings & Stage-Tracked Trees
        growing_trees = data.count(b'FarmingGrowingTree_StageIndex_ServerOnly')
        saplings = len(re.findall(rb'BP_[A-Za-z0-9_]*Sapling_[A-Za-z0-9_]*_UAID_', data))

        growing_list = []
        if growing_trees > 0:
            growing_list.append({
                "name": "Planted Agriculture Trees & Crops (Active Stage)",
                "category": "Arboriculture",
                "count": growing_trees,
                "stage_tracking": "FarmingGrowingTree_StageIndex_ServerOnly",
                "status": "Active In-World Stage Tracking"
            })
        if saplings > 0:
            growing_list.append({
                "name": "Growing Saplings (Ash / Maple / Oak)",
                "category": "Arboriculture",
                "count": saplings,
                "stage_tracking": "BP_Sapling_UAID",
                "status": "Maturing Saplings"
            })

        return {
            "structures": structures,
            "crops": crops,
            "growing_trees": growing_list,
            "summary": {
                "total_water_barrels": barrels,
                "total_rain_catchers": rain_catchers,
                "total_composters": composters,
                "total_growing_trees": growing_trees,
                "total_crops": total_crops,
                "total_saplings": saplings
            }
        }
    except Exception:
        return {
            "structures": [],
            "crops": [],
            "growing_trees": [],
            "summary": {
                "total_water_barrels": 0,
                "total_rain_catchers": 0,
                "total_composters": 0,
                "total_growing_trees": 0,
                "total_crops": 0,
                "total_saplings": 0
            }
        }

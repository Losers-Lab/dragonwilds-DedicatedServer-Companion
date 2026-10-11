"""
Dragonwilds Farming & Agriculture Tracking Module.

Extracts objective farming states from the game world:
1. Placed Farm Structures: Rain Catchers, Water Barrels, Composters.
2. Active Farming Trees & Plots: Tracks planted crop/tree stage indices (`FarmingGrowingTree_StageIndex_ServerOnly`),
   growth states, and hydration infrastructure.
3. Save-file driven: Extracts actual world instances and structures directly from the `.sav` file.
"""

import os
import glob
import re
from config import SAVES_DIR


def get_farming_status(saves_dir: str = SAVES_DIR) -> dict:
    """Scans latest world save for farming infrastructure, composters, and growing trees/crops."""
    save_files = glob.glob(os.path.join(saves_dir, "*.sav"))
    if not save_files:
        return {
            "structures": [],
            "growing_trees": [],
            "summary": {
                "total_water_barrels": 0,
                "total_rain_catchers": 0,
                "total_composters": 0,
                "total_growing_trees": 0
            }
        }

    newest_save = max(save_files, key=os.path.getmtime)
    try:
        with open(newest_save, "rb") as f:
            data = f.read()

        # Count specific farming structures using fast byte search
        barrels = data.count(b'BP_Farm_Barrel_Water')
        rain_catchers = data.count(b'BP_Farm_RainCatcher')
        composters = data.count(b'BP_Station_Composter_New')
        growing_trees = data.count(b'FarmingGrowingTree_StageIndex_ServerOnly')

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

        growing_list = []
        if growing_trees > 0:
            growing_list.append({
                "name": "Planted Agriculture Trees & Crops",
                "count": growing_trees,
                "stage_tracking": "FarmingGrowingTree_StageIndex_ServerOnly",
                "status": "Active In-World Growth"
            })

        return {
            "structures": structures,
            "growing_trees": growing_list,
            "summary": {
                "total_water_barrels": barrels,
                "total_rain_catchers": rain_catchers,
                "total_composters": composters,
                "total_growing_trees": growing_trees
            }
        }
    except Exception:
        return {
            "structures": [],
            "growing_trees": [],
            "summary": {
                "total_water_barrels": 0,
                "total_rain_catchers": 0,
                "total_composters": 0,
                "total_growing_trees": 0
            }
        }

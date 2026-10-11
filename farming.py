"""
Dragonwilds Farming & Agriculture Tracking Module.

Extracts objective farming states, crops, botanical flora, and forestry telemetry:
1. Placed Farm Structures: Rain Catchers, Water Storage Barrels, Composters.
2. Active In-World Crops, Vegetables & Medicinal Herbs:
   Tracks all harvestable, planted, and wild agricultural instances:
   - Vegetables & Fiber: Flax (Linen), Onions, Potatoes, Cabbages, Pumpkins, Swamp Weed.
   - Medicinal Herbs: Snapdragon, Sagewort, Toadflax, Thorny Root (Irit).
   - Wild Berry Bushes: Dwellberry Bushes, Redberry Bushes.
   - Botanical Flora: Corpse Cotton Plants, Desert Barrel Cacti, Bunny Cacti, Bittercap Mushrooms.
3. Growing Saplings & Arboriculture:
   - Maturing Saplings (Ash, Maple, Oak).
   - Active Stage-Tracked Trees (`FarmingGrowingTree_StageIndex_ServerOnly`).
   - Mature Forestry Trees (Ash, Oak, Maple, Willow).
4. Strictly Read-Only: Directly extracts actual world instances from the active `.sav` save file.
"""

import os
import glob
import re
from config import SAVES_DIR


def get_farming_status(saves_dir: str = SAVES_DIR) -> dict:
    """Scans latest world save for farming infrastructure, crops, herbs, flora, saplings, and trees."""
    save_files = glob.glob(os.path.join(saves_dir, "*.sav"))
    if not save_files:
        return {
            "structures": [],
            "crops": [],
            "growing_trees": [],
            "trees": [],
            "summary": {
                "total_water_barrels": 0,
                "total_rain_catchers": 0,
                "total_composters": 0,
                "total_growing_trees": 0,
                "total_crops": 0,
                "total_saplings": 0,
                "total_trees": 0
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

        # 2. Crops, Vegetables, Herbs, Berry Bushes & Botanical Flora
        crop_catalog = [
            ("Flax (Linen)", "Textile / Crafting Crop", rb'BP_Spawner_Flax_C_UAID_|BP_Spawner_Flax_C\x00', "Harvestable / Growing"),
            ("Onions", "Vegetable Crop", rb'BP_Spawner_Onion_C_UAID_|BP_Spawner_Onion_C\x00', "Harvestable / Growing"),
            ("Potatoes", "Vegetable Crop", rb'BP_Spawner_Potato_C_UAID_|BP_Spawner_Potato_C\x00', "Harvestable / Growing"),
            ("Cabbages", "Vegetable Crop", rb'BP_Spawner_Cabbage_C_UAID_|BP_Spawner_Cabbage_C\x00', "Harvestable / Growing"),
            ("Pumpkins", "Vegetable Crop", rb'BP_Spawner_Pumpkin_[0-9]+_C_UAID_|BP_Spawner_Pumpkin_[0-9]+_C\x00|BP_Spawner_Pumpkin_C\x00', "Harvestable / Growing"),
            ("Swamp Weed", "Herbaceous Agriculture", rb'BP_Spawner_SwampWeedPlant_C_UAID_|BP_Spawner_SwampWeedPlant_C\x00', "Active Growth"),
            ("Snapdragon", "High-Tier Medicinal Herb", rb'BP_Spawner_Snapdragon_C_UAID_|BP_Spawner_Snapdragon_C\x00', "Active Growth"),
            ("Sagewort", "Medicinal Herb", rb'BP_Spawner_Sagewort_C_UAID_|BP_Spawner_Sagewort_C\x00', "Active Growth"),
            ("Toadflax", "Medicinal Herb", rb'BP_Spawner_Toadflax_C_UAID_|BP_Spawner_Toadflax_C\x00', "Active Growth"),
            ("Thorny Root (Irit)", "Medicinal Herb & Defense Flora", rb'BP_ThornyRoot_Irit_C_UAID_|BP_ThornyRoot_Irit_C\x00', "Active Growth"),
            ("Dwellberry Bushes", "Fruit & Berry Bush", rb'BP_DwellberryBush_C_UAID_|BP_DwellberryBush_C\x00', "Harvestable Bush"),
            ("Redberry Bushes", "Fruit & Berry Bush", rb'BP_RedberryBush_C_UAID_|BP_RedberryBush_C\x00', "Harvestable Bush"),
            ("Corpse Cotton Plants", "Botanical & Explosive Flora", rb'BP_Plant_Explosive_CorpseCotton_C_UAID_|BP_Plant_Explosive_CorpseCotton_C\x00', "Active Growth"),
            ("Barrel Cactus", "Desert Flora & Hydration", rb'BP_Cactus_Barrel_C_UAID_|BP_Cactus_Barrel_C\x00', "Active Growth"),
            ("Bunny Cactus", "Desert Flora & Hydration", rb'BP_Cactus_Bunny_C_UAID_|BP_Cactus_Bunny_C\x00', "Active Growth"),
            ("Bittercap Mushroom", "Fungi & Spores", rb'BP_Spawner_BittercapMushroom_C_UAID_|BP_Spawner_BittercapMushroom_C\x00', "Active Growth"),
        ]

        crops = []
        total_crops = 0
        for name, category, pattern, status in crop_catalog:
            matches = re.findall(pattern, data)
            count = len(matches)
            if count > 0:
                # Find all unique UAID instances for this crop to populate individual plot breakdowns
                uaid_pattern = pattern.split(b'|')[0]
                if b'_UAID_' in uaid_pattern:
                    base_prefix = uaid_pattern.split(b'_UAID_')[0]
                    inst_matches = re.findall(base_prefix + rb'[A-Za-z0-9_]*_UAID_[A-Za-z0-9_]+', data)
                    unique_plots = sorted(set(m.decode('latin1') for m in inst_matches))
                else:
                    unique_plots = []

                plot_details = []
                for idx, plot_id in enumerate(unique_plots, 1):
                    # Guess region or zone from UAID prefix if known
                    zone = "World Spawner"
                    if "BM" in plot_id:
                        zone = "Brynmoore"
                    elif "FH" in plot_id:
                        zone = "Fellhollow"
                    elif "DR" in plot_id:
                        zone = "Dowdun Reach"
                    elif "Desert" in plot_id or "Sand" in plot_id:
                        zone = "Umbral Sands"
                    
                    clean_id = plot_id.split('_UAID_')[-1] if '_UAID_' in plot_id else plot_id
                    plot_details.append({
                        "plot_number": idx,
                        "instance_id": plot_id,
                        "short_id": clean_id,
                        "zone": zone,
                        "status": status
                    })

                crops.append({
                    "name": name,
                    "category": category,
                    "count": count,
                    "status": status,
                    "plots": plot_details
                })
                total_crops += count

        # 3. Growing Saplings & Stage-Tracked Trees
        growing_stage_trees = data.count(b'FarmingGrowingTree_StageIndex_ServerOnly')

        sapling_types = [
            ("Ash Saplings", rb'BP_(?:BM_)?Sapling_Ash_[0-9]+_C_UAID_|BP_Sapling_Ash_01_C_UAID_', "Maturing Sapling"),
            ("Maple Saplings", rb'BP_(?:DR_)?Sapling_Maple_[0-9]+_C_UAID_', "Maturing Sapling"),
            ("Oak Saplings", rb'BP_(?:BM_|FH_)?Sapling_Oak_[0-9]+_C_UAID_', "Maturing Sapling"),
        ]

        growing_list = []
        total_saplings = 0
        for sap_name, sap_pattern, sap_status in sapling_types:
            sap_count = len(re.findall(sap_pattern, data))
            if sap_count > 0:
                growing_list.append({
                    "name": sap_name,
                    "category": "Arboriculture (Sapling)",
                    "count": sap_count,
                    "stage_tracking": "Maturing Sapling (Placed)",
                    "status": sap_status
                })
                total_saplings += sap_count

        # Fallback if specific sapling regex didn't catch all
        all_saplings_count = len(re.findall(rb'BP_[A-Za-z0-9_]*Sapling_[A-Za-z0-9_]*_UAID_', data))
        if all_saplings_count > total_saplings:
            diff = all_saplings_count - total_saplings
            growing_list.append({
                "name": "Other Saplings",
                "category": "Arboriculture (Sapling)",
                "count": diff,
                "stage_tracking": "Maturing Sapling",
                "status": "Maturing Sapling"
            })
            total_saplings = all_saplings_count

        if growing_stage_trees > 0:
            growing_list.append({
                "name": "Planted Agriculture Trees & Crops (Active Growth Stage)",
                "category": "Arboriculture",
                "count": growing_stage_trees,
                "stage_tracking": "FarmingGrowingTree_StageIndex_ServerOnly",
                "status": "Active In-World Stage Tracking"
            })

        # 4. Forestry & Mature Trees Overview
        tree_catalog = [
            ("Ash Trees", "Forestry / Deciduous", rb'BP_(?:BM_|FH_|HL_)?Tree_Ash_[A-Za-z0-9_]*_UAID_', "Mature Forestry"),
            ("Oak Trees", "Forestry / Hardwood", rb'BP_(?:BM_|FH_)?Tree_Oak_[A-Za-z0-9_]*_UAID_', "Mature Forestry"),
            ("Maple Trees", "Forestry / Hardwood", rb'BP_(?:DR_)?Tree_Maple_[A-Za-z0-9_]*_UAID_', "Mature Forestry"),
            ("Willow Trees", "Forestry / Wetland", rb'BP_(?:FH_)?Tree_Willow_[A-Za-z0-9_]*_UAID_', "Mature Forestry"),
        ]

        trees = []
        total_trees = 0
        for t_name, t_cat, t_pattern, t_status in tree_catalog:
            t_count = len(re.findall(t_pattern, data))
            if t_count > 0:
                trees.append({
                    "name": t_name,
                    "category": t_cat,
                    "count": t_count,
                    "status": t_status
                })
                total_trees += t_count

        return {
            "structures": structures,
            "crops": crops,
            "growing_trees": growing_list,
            "trees": trees,
            "summary": {
                "total_water_barrels": barrels,
                "total_rain_catchers": rain_catchers,
                "total_composters": composters,
                "total_growing_trees": growing_stage_trees,
                "total_crops": total_crops,
                "total_saplings": total_saplings,
                "total_trees": total_trees
            }
        }
    except Exception:
        return {
            "structures": [],
            "crops": [],
            "growing_trees": [],
            "trees": [],
            "summary": {
                "total_water_barrels": 0,
                "total_rain_catchers": 0,
                "total_composters": 0,
                "total_growing_trees": 0,
                "total_crops": 0,
                "total_saplings": 0,
                "total_trees": 0
            }
        }

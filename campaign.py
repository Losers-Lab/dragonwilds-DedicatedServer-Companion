"""
Dragonwilds Campaign Milestones & World Markers Module.

Extracts objective world progress, player achievements, and in-world structures directly
from dedicated server saves:
1. Campaign Progression:
   - Ancient Teleport Shrines activated
   - Arcane Spells discovered and mastered
   - Architectural Blueprints and Building Pieces researched
   - Crafting Recipes unlocked
   - Story & Quest Hooks completed
   - Elite Monsters and Bosses slain
2. In-World Player Markers:
   - Player Death Gravestones (BP_PlayerGraveyard_8Slots_C)
   - Claimed Player Bedrolls & Camps (BP_BaseBuilding_BedRoll_C)
   - Active Quest NPCs (Restless Ghost, Candle in the Dark)
3. Strictly Read-Only: Directly parses active server .sav files without modifying disk.
"""

import os
import glob
import json
import re
import time
from threading import Lock
from config import SAVES_DIR

_lock = Lock()
_cache = {
    "mtime": 0.0,
    "path": None,
    "data": None
}


def find_newest_save(saves_dir: str = SAVES_DIR) -> str:
    """Finds newest .sav file in saves directory."""
    if not saves_dir or not os.path.exists(saves_dir):
        return None

    newest_path = None
    newest_mtime = -1.0
    try:
        for root, _, files in os.walk(saves_dir):
            for file in files:
                if file.endswith(".sav"):
                    path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(path)
                        if mtime > newest_mtime:
                            newest_mtime = mtime
                            newest_path = path
                    except OSError:
                        pass
    except Exception:
        pass
    return newest_path


def get_campaign_status(saves_dir: str = SAVES_DIR) -> dict:
    """Extracts objective campaign progression and world markers from newest save file."""
    save_path = find_newest_save(saves_dir)
    if not save_path or not os.path.exists(save_path):
        return {
            "summary": {
                "shrines_unlocked": 0,
                "spells_unlocked": 0,
                "buildings_unlocked": 0,
                "recipes_unlocked": 0,
                "story_hooks": 0,
                "bosses_and_elites": 0,
                "player_gravestones": 0,
                "player_bedrolls": 0,
                "active_world_save": "None"
            },
            "shrines": [],
            "spells": [],
            "death_markers": [],
            "camps": [],
            "quests": []
        }

    try:
        cur_mtime = os.path.getmtime(save_path)
    except OSError:
        cur_mtime = 0.0

    global _cache
    with _lock:
        if _cache["path"] == save_path and _cache["mtime"] == cur_mtime and _cache["data"]:
            return _cache["data"]

    try:
        with open(save_path, "rb") as f:
            data = f.read()

        active_save_name = os.path.basename(os.path.dirname(save_path)) or os.path.basename(save_path)

        # 1. Parse Embedded Progress JSON Block
        progress_json = {}
        idx = data.find(b'"KilledOnceAIs"')
        if idx != -1:
            start = data.rfind(b'{', 0, idx)
            end = data.find(b'}', idx)
            if start != -1 and end != -1:
                try:
                    progress_json = json.loads(data[start:end+1].decode('latin1', errors='ignore'))
                except Exception:
                    pass

        shrines = progress_json.get("ShrinesUnlocked", [])
        spells = progress_json.get("SpellsUnlocked", [])
        buildings_count = len(progress_json.get("BuildingsUnlocked", []))
        recipes_count = len(progress_json.get("RecipesUnlocked", []))
        hooks_count = len(progress_json.get("PlayerHooksTriggered", []))
        elites = progress_json.get("KilledOnceAIs", [])

        # 2. Extract In-World Death Gravestones
        graves_raw = re.findall(rb'BP_PlayerGraveyard_8Slots_C_UAID_[A-Za-z0-9_]+', data)
        unique_graves = sorted(set(g.decode('latin1') for g in graves_raw))
        death_markers = []
        for idx_g, g_id in enumerate(unique_graves, 1):
            short_id = g_id.split('_UAID_')[-1] if '_UAID_' in g_id else g_id
            zone = "Overworld"
            if "BM" in g_id:
                zone = "Brynmoore"
            elif "GF" in g_id:
                zone = "Ghornefell"
            elif "DR" in g_id:
                zone = "Dowdun Reach"
            elif "FH" in g_id:
                zone = "Fellhollow"
            elif "Desert" in g_id or "Sand" in g_id:
                zone = "Umbral Sands"

            death_markers.append({
                "index": idx_g,
                "id": g_id,
                "short_id": short_id,
                "name": f"Player Gravestone #{idx_g}",
                "zone": zone,
                "type": "Death Gravestone"
            })

        # 3. Extract Claimed Player Bedrolls / Camps
        bedroll_matches = re.findall(rb'BP_BaseBuilding_BedRoll_C', data)
        total_bedrolls = len(bedroll_matches)
        camps = []
        for idx_b in range(1, total_bedrolls + 1):
            camps.append({
                "index": idx_b,
                "name": f"Settlement Bedroll #{idx_b}",
                "zone": "Central Ashenfall (Overworld)",
                "type": "Player Camp / Claimed Bed"
            })

        # 4. In-World Quest NPCs
        quests = []
        if b'BP_NPC_RestlessGhost_Quest' in data:
            quests.append({
                "name": "The Restless Ghost",
                "category": "Spirit Quest",
                "status": "In-World Quest NPC",
                "lore": "Restless apparition seeking spectral peace in the Ashen Crypts."
            })
        if b'BP_NPC_Quest_CandleLight2' in data:
            quests.append({
                "name": "Candle in the Dark",
                "category": "Sanctuary Quest",
                "status": "In-World Quest NPC",
                "lore": "Guiding flame ritual illuminating forgotten sanctuary ruins."
            })

        result = {
            "summary": {
                "shrines_unlocked": len(shrines),
                "spells_unlocked": len(spells),
                "buildings_unlocked": buildings_count,
                "recipes_unlocked": recipes_count,
                "story_hooks": hooks_count,
                "bosses_and_elites": len(elites),
                "player_gravestones": len(death_markers),
                "player_bedrolls": total_bedrolls,
                "active_world_save": active_save_name
            },
            "shrines": shrines,
            "spells": spells,
            "death_markers": death_markers,
            "camps": camps,
            "quests": quests
        }

        with _lock:
            _cache = {
                "mtime": cur_mtime,
                "path": save_path,
                "data": result
            }
        return result

    except Exception:
        return {
            "summary": {
                "shrines_unlocked": 0,
                "spells_unlocked": 0,
                "buildings_unlocked": 0,
                "recipes_unlocked": 0,
                "story_hooks": 0,
                "bosses_and_elites": 0,
                "player_gravestones": 0,
                "player_bedrolls": 0,
                "active_world_save": "Error"
            },
            "shrines": [],
            "spells": [],
            "death_markers": [],
            "camps": [],
            "quests": []
        }

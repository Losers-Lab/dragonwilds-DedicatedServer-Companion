"""
World Actors and POI Manager for Dragonwilds Dedicated Server Companion.
Extracts persistent actor transforms (NPCs, Fishing Nodes, Shrines, Shortcuts)
from Unreal Engine SPUD level cache (.lvl files) with high-performance in-memory caching.
Strictly READ-ONLY.
"""

import glob
import logging
import os
import re
import struct
import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Bounding box calibration: Unreal Engine (cm) -> Ashenfall Canvas (1000x1000)
# Calibrated against canonical Brynmoore and Ashenfall continental landmarks:
# Starter Shoreline (X=6,133, Y=187,356)   -> (210, 500)
# Village Center (X=48,499, Y=177,605)     -> (274, 483)
# Castle Stronghold (X=81,070, Y=154,387)  -> (323, 441)
# Granite Maul Vault (X=131,958, Y=83,849) -> (399, 314)
# Desert Dunes / Uzer (X=320,000, Y=230,000) -> (681, 577)
CALIBRATION_BASE_X = 6000.0
CALIBRATION_BASE_Y = 187000.0
CALIBRATION_SCALE_X = 0.0015
CALIBRATION_SCALE_Y = 0.0018


def world_to_map_coords(x: float, y: float, z: float = 0.0) -> Dict[str, float]:
    """
    Convert Unreal Engine world units (cm) to Ashenfall 1000x1000 map coordinates.
    Correctly maps global overworld coordinates and resolves subterranean instanced dungeons
    (Brynmoore Catacombs, Kalphite Queen subterranean hive) back to their canonical surface regions.
    """
    # 1. Kalphite Queen Arena / Subterranean Desert Hive (Z < -20000, X < -350000)
    # Lair is anchored beneath Dunes of Uzer / Umbral Sands (Canvas: 650, 620)
    if x < -350000.0 and z < -20000.0:
        map_x = 650.0 + (x - (-455000.0)) * 0.0015
        map_y = 620.0 + (y - 190000.0) * 0.0018
    # 2. Brynmoore Subterranean Catacombs & Dungeons (Z < -20000, -250000 <= X <= -100000)
    # Dungeon is anchored beneath Brynmoore Ancient Courtyard / Crypts (Canvas: 280, 510)
    elif -250000.0 <= x <= -100000.0 and z < -20000.0:
        map_x = 280.0 + (x - (-170000.0)) * 0.0015
        map_y = 510.0 + (y - 100000.0) * 0.0018
    # 3. Standard Overworld Transformation
    else:
        map_x = 210.0 + (x - CALIBRATION_BASE_X) * CALIBRATION_SCALE_X
        map_y = 500.0 + (y - CALIBRATION_BASE_Y) * CALIBRATION_SCALE_Y

    map_x = max(20.0, min(980.0, round(map_x, 1)))
    map_y = max(20.0, min(980.0, round(map_y, 1)))
    return {"x": map_x, "y": map_y}


def format_actor_label(class_name: str) -> Dict[str, str]:
    """Return human-readable title, category, and action hint for an actor class."""
    low = class_name.lower()
    
    # 1. Fishing spots
    if "fishingnodev2_net" in low:
        return {
            "title": "Net Fishing Spot",
            "category": "fishing",
            "category_label": "Fishing Spots",
            "icon": "fishing_net",
            "hint": "Requires Small Fishing Net. Harvests trout, salmon, and river fish."
        }
    if "fishingnodev2_rod" in low:
        return {
            "title": "Rod Fishing Spot",
            "category": "fishing",
            "category_label": "Fishing Spots",
            "icon": "fishing_rod",
            "hint": "Requires Fishing Rod and Bait. Harvests pike, bass, and deepwater fish."
        }
    if "fishing" in low or "fish" in low:
        return {
            "title": "Fishing Node",
            "category": "fishing",
            "category_label": "Fishing Spots",
            "icon": "fishing",
            "hint": "Active fishing location."
        }

    # 2. NPCs & Quests
    if "wiseoldman_ftue" in low:
        return {
            "title": "Wise Old Man (Tutorial Camp)",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_elder",
            "hint": "First-Time User Experience guide and starter quest giver."
        }
    if "wiseoldman_village" in low:
        return {
            "title": "Wise Old Man (Village Elder)",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_elder",
            "hint": "Village Elder offering lore and campaign guidance."
        }
    if "doric" in low:
        return {
            "title": "Doric the Dwarf (Blacksmith)",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_blacksmith",
            "hint": "Master blacksmith offering smithing quests and anvil services."
        }
    if "zanik" in low:
        return {
            "title": "Zanik (Cave Goblin Explorer)",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_goblin",
            "hint": "Cave Goblin ally and subterranean quest explorer."
        }
    if "bilegut" in low:
        return {
            "title": "Bilegut (Goblin Guard)",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_goblin",
            "hint": "Goblin outpost sentry."
        }
    if "wormelbow" in low:
        return {
            "title": "Wormelbow (Goblin Guard)",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_goblin",
            "hint": "Goblin outpost sentry."
        }
    if "reliquarycastle" in low:
        return {
            "title": "Castle Reliquary Steward",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_noble",
            "hint": "Steward managing castle artifacts and regional relics."
        }
    if "reliquaryguild" in low:
        return {
            "title": "Guild Reliquary Master",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc_guild",
            "hint": "Guild quartermaster for rare curios and trade."
        }
    if "restlessghostmemorial" in low:
        return {
            "title": "Restless Ghost Memorial",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "quest_ghost",
            "hint": "Memorial gravestone tying into the Restless Ghost questline."
        }
    if "restlessghostwell" in low:
        return {
            "title": "Restless Ghost Haunted Well",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "quest_ghost",
            "hint": "Haunted well landmark with quest clues."
        }
    if "restlessghost" in low:
        return {
            "title": "Restless Ghost",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "quest_ghost",
            "hint": "Supernatural quest apparition."
        }
    if "saradomin_statue" in low:
        return {
            "title": "Saradomin Holy Statue",
            "category": "shrines",
            "category_label": "Shrines & Relics",
            "icon": "statue_holy",
            "hint": "Sacred monument radiating protective energy."
        }
    if "vault_granitemauled" in low or "statue_puzzle" in low:
        return {
            "title": "Granite Maul Vault Puzzle Statue",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "puzzle_statue",
            "hint": "Interactive stone statue controlling vault locking mechanism."
        }
    if "npc" in low or "quest" in low:
        cleaned = re.sub(r"^BP_NPC_|_C$", "", class_name).replace("_", " ")
        return {
            "title": f"NPC: {cleaned}",
            "category": "npcs",
            "category_label": "NPCs & Quests",
            "icon": "npc",
            "hint": "Interactive world NPC."
        }

    # 3. Shrines & Relics
    if "healthshrine" in low:
        return {
            "title": "Health Shrine",
            "category": "shrines",
            "category_label": "Shrines & Relics",
            "icon": "shrine_health",
            "hint": "Ancient shrine offering health restoration and blessings."
        }
    if "shrine" in low:
        return {
            "title": "World Shrine",
            "category": "shrines",
            "category_label": "Shrines & Relics",
            "icon": "shrine",
            "hint": "Ancient stone altar."
        }

    # 4. Agility & Shortcuts
    if "shortcut" in low or "burrow" in low or "agility" in low:
        return {
            "title": "Kebbit Agility Burrow",
            "category": "shortcuts",
            "category_label": "Agility Shortcuts",
            "icon": "burrow",
            "hint": "Underground shortcut requiring Agility to squeeze through."
        }

    # 5. Anima Vents & Geysers
    if "animavent" in low:
        return {
            "title": "Anima Vent",
            "category": "geysers",
            "category_label": "Anima & Geysers",
            "icon": "anima_vent",
            "hint": "High-pressure vent surging with raw Anima essence."
        }
    if "runeessencegeyser" in low or "geyser" in low:
        return {
            "title": "Rune Essence Geyser",
            "category": "geysers",
            "category_label": "Anima & Geysers",
            "icon": "rune_geyser",
            "hint": "Active geyser fissure harvesting pure rune essence."
        }

    # 6. Chests
    if "chest" in low:
        cleaned = re.sub(r"^BP_(Dungeon_Treasure_)?Chest_|_World_Cache|_Vault_Cache|_C$", "", class_name).replace("_", " ")
        return {
            "title": f"{cleaned.strip()} Chest",
            "category": "chests",
            "category_label": "Chests & Vaults",
            "icon": "chest",
            "hint": "World treasure cache."
        }

    # 7. Other / default
    cleaned = re.sub(r"^BP_|_C$", "", class_name).replace("_", " ")
    return {
        "title": cleaned,
        "category": "other",
        "category_label": "Other Interactives",
        "icon": "pin",
        "hint": "World object."
    }


def parse_lvl_actors(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse actors and their FTransform positions from a SPUD .lvl file.
    Extracts coordinates from the binary CORA (Core Actor) chunk following each actor.
    Strictly READ-ONLY.
    """
    actors = []
    if not os.path.exists(filepath):
        return actors

    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except Exception as e:
        logger.error(f"Failed to read .lvl file {filepath}: {e}")
        return actors

    cell_name = os.path.basename(filepath).replace(".lvl", "")

    # Regex matches Unreal Blueprint Persistent Actors: BP_<ClassName>_C_UAID_<InstanceID>
    matches = list(re.finditer(rb"BP_([A-Za-z0-9_]+)_C_UAID_([A-Za-z0-9_]+)", data))
    for m in matches:
        cls_name = m.group(1).decode("latin1")
        uaid = m.group(2).decode("latin1")
        actor_id = f"UAID_{uaid}"
        full_actor_name = f"BP_{cls_name}_C_{actor_id}"

        # Find CORA chunk within 300 bytes following actor name
        pos = m.start()
        cora_idx = data.find(b"CORA", pos, pos + 300)
        if cora_idx == -1:
            continue

        chunk = data[cora_idx:cora_idx + 120]
        if len(chunk) < 71:
            continue

        try:
            # CORA structure: 15 bytes header, 32 bytes Quaternion, 24 bytes Position (X, Y, Z)
            x = struct.unpack("<d", chunk[47:55])[0]
            y = struct.unpack("<d", chunk[55:63])[0]
            z = struct.unpack("<d", chunk[63:71])[0]

            # Discard invalid/infinite coordinates
            if abs(x) > 2000000 or abs(y) > 2000000:
                continue

            info = format_actor_label(cls_name)
            map_pt = world_to_map_coords(x, y, z)

            actors.append({
                "id": actor_id,
                "full_name": full_actor_name,
                "class_name": f"BP_{cls_name}_C",
                "title": info["title"],
                "category": info["category"],
                "category_label": info["category_label"],
                "icon": info["icon"],
                "hint": info["hint"],
                "cell": cell_name,
                "world_pos": {
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "z": round(z, 1)
                },
                "map_coords": map_pt
            })
        except Exception:
            continue

    return actors


class WorldActorManager:
    """
    High-performance in-memory manager for Dragonwilds World Actors & POIs.
    Maintains cached actor dictionaries in memory to guarantee instant UI response times.
    Only checks file mtimes upon TTL expiry.
    """

    def __init__(self, spud_dir: Optional[str] = None, ttl_seconds: float = 60.0):
        self.spud_dir = spud_dir
        self.ttl_seconds = ttl_seconds
        self.lock = threading.Lock()
        self._cached_by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._cached_by_id: Dict[str, Dict[str, Any]] = {}
        self._file_mtimes: Dict[str, float] = {}
        self._last_scan_time: float = 0.0
        self._is_initialized: bool = False

    def get_actors(self, categories: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieve actors grouped by category.
        Uses in-memory cache if within TTL, else verifies file mtimes before parsing.
        """
        now = time.time()

        with self.lock:
            # Fast path: Serve directly from memory without touching disk if within TTL
            if self._is_initialized and not force_refresh and (now - self._last_scan_time < self.ttl_seconds):
                return self._build_response(categories, cached=True)

            spud_path = self.spud_dir
            if not spud_path or not os.path.exists(spud_path):
                # Return whatever is in cache or empty
                return self._build_response(categories, cached=True)

            # Check directory file mtimes (fast stat, does not read file contents)
            current_files = {}
            try:
                for entry in os.scandir(spud_path):
                    if entry.name.endswith(".lvl") and entry.is_file():
                        current_files[entry.path] = entry.stat().st_mtime
            except Exception as e:
                logger.warning(f"Error scanning spud directory {spud_path}: {e}")
                return self._build_response(categories, cached=True)

            # If files have not changed and we already have cache, extend TTL and serve
            if self._is_initialized and not force_refresh and current_files == self._file_mtimes:
                self._last_scan_time = now
                return self._build_response(categories, cached=True)

            # Cache is cold or files changed: re-parse
            new_by_category = defaultdict(list)
            new_by_id = {}

            for filepath in current_files.keys():
                parsed = parse_lvl_actors(filepath)
                for actor in parsed:
                    cat = actor["category"]
                    new_by_category[cat].append(actor)
                    new_by_id[actor["id"]] = actor

            self._cached_by_category = new_by_category
            self._cached_by_id = new_by_id
            self._file_mtimes = current_files
            self._last_scan_time = now
            self._is_initialized = True

            return self._build_response(categories, cached=False)

    def _build_response(self, categories: Optional[List[str]], cached: bool) -> Dict[str, Any]:
        """Format the response payload with filtered categories and summary counts."""
        res_actors = {}
        counts = {}
        all_cats = set(self._cached_by_category.keys())

        target_cats = set(c.lower() for c in categories) if categories else all_cats

        total = 0
        for cat, items in self._cached_by_category.items():
            counts[cat] = len(items)
            if cat in target_cats or "all" in target_cats:
                res_actors[cat] = items
                total += len(items)

        now = time.time()
        age = round(now - self._last_scan_time, 2) if self._last_scan_time > 0 else 0.0

        return {
            "status": "ok",
            "cached": cached,
            "cache_age_seconds": age,
            "counts": counts,
            "total_returned": total,
            "actors": res_actors
        }


# Global singleton instance
_world_actor_manager: Optional[WorldActorManager] = None
_manager_lock = threading.Lock()


def get_world_actor_manager(spud_dir: Optional[str] = None) -> WorldActorManager:
    """Retrieve or initialize the global thread-safe WorldActorManager singleton."""
    global _world_actor_manager
    if not spud_dir:
        try:
            import config
            spud_dir = getattr(config, "SPUD_CACHE_PATH", "")
        except Exception:
            spud_dir = ""

    with _manager_lock:
        if _world_actor_manager is None:
            _world_actor_manager = WorldActorManager(spud_dir=spud_dir)
        elif spud_dir and _world_actor_manager.spud_dir != spud_dir:
            _world_actor_manager.spud_dir = spud_dir
        return _world_actor_manager

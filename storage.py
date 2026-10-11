"""
Dragonwilds Storage & Item Inventory Tracking Module.

Provides objective server-wide storage container tracking and item lookup:
1. Parses all active storage units and containers from latest save file.
2. Identifies container type, location/owner, capacity, slot usage, and contents.
3. Aggregates server-wide totals per item, showing total stored count and container locations.
4. Strictly Read-Only: Directly extracts actual world instances from the active .sav save file.
"""

import os
import glob
import re
import json
from config import SAVES_DIR
from item_resolver import resolve_item

_storage_cache = None
_storage_cache_mtime = 0

KNOWN_PLAYER_EOS_IDS = {
    "000225fad0314f69844ceb408bada617": "Arham",
    "000239b86c6a4c048d2fba065f6a408a": "Mango",
    "000210b5cf4541ecb7c1afbd1531881c": "slayingmerch",
    "00027bf163a34b1890e53fba2f987749": "Hector First",
    "00022ef6635e4d538914b423d8bb18c3": "Player",
}


def format_container_name(actor_raw: str, owner: str = None) -> str:
    """Formats an Unreal Blueprint container actor into a human-friendly label."""
    if not actor_raw:
        return f"{owner}'s Storage" if owner and owner != "World / Unowned" else "Storage Unit"

    # Strip UAID and instance suffix
    base = actor_raw.split("_UAID_")[0].strip()
    if base.startswith("BP_"):
        base = base[3:]
    if base.endswith("_C"):
        base = base[:-2]

    # Handle common patterns
    if "PlayerGraveyard" in base or "PlayerGravestone" in base:
        return f"{owner}'s Gravestone / Remains" if owner and owner != "World / Unowned" else "Player Grave Stash"

    if "BaseBuilding" in base:
        # e.g. BaseBuilding_Chest_Iron -> Base Chest Iron
        cleaned = base.replace("BaseBuilding_", "Base ")
        cleaned = cleaned.replace("_", " ")
        cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if owner and owner != "World / Unowned":
            return f"{owner}'s {cleaned}"
        return cleaned

    # Loot chests and Buried chests
    if "LootChest_Prefab_" in base:
        base = base.replace("LootChest_Prefab_", "")
    if "Dungeon_Treasure_Chest_" in base:
        base = base.replace("Dungeon_Treasure_Chest_", "Dungeon Cache ")
    if "BuriedChest_" in base:
        base = base.replace("BuriedChest_", "Buried Chest ")
    if "DR_BuriedChest" in base:
        base = "Buried Treasure Chest"
    if "SpectralChest" in base:
        base = "Spectral Chest"

    # Clean underscores and camelCase
    cleaned = base.replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if owner and owner != "World / Unowned":
        return f"{owner}'s {cleaned}"
    return cleaned


def parse_storage_data(saves_dir: str = SAVES_DIR, save_filename: str = None) -> dict:
    """Parses all storage containers and aggregates stored items from the latest or specified world save."""
    global _storage_cache, _storage_cache_mtime

    save_files = glob.glob(os.path.join(saves_dir, "*.sav"))
    if not save_files:
        return {
            "containers": [],
            "items": [],
            "total_containers": 0,
            "total_stored_items": 0,
            "unique_items_count": 0,
            "save_file": None,
        }

    target_save = None
    if save_filename:
        for s in save_files:
            if os.path.basename(s).lower() == save_filename.lower():
                target_save = s
                break
    if not target_save:
        target_save = max(save_files, key=os.path.getmtime)

    current_mtime = os.path.getmtime(target_save)
    cache_key = f"{target_save}_{current_mtime}"

    if _storage_cache is not None and getattr(_storage_cache, "get", lambda k: None)("cache_key") == cache_key:
        return _storage_cache

    try:
        with open(target_save, "rb") as f:
            data = f.read()
    except Exception:
        return {
            "containers": [],
            "items": [],
            "total_containers": 0,
            "total_stored_items": 0,
            "unique_items_count": 0,
            "save_file": os.path.basename(target_save),
        }

    # Extract all JSON inventories with Version 83
    matches = [m.start() for m in re.finditer(rb'"Version"\s*:\s*83', data)]
    containers = []
    items_map = {}

    container_counter = 1
    for idx in matches:
        start = data.rfind(b'{', 0, idx)
        if start == -1:
            continue
        depth = 0
        end = -1
        for i in range(start, min(len(data), start + 32768)):
            b = data[i:i+1]
            if b == b'{':
                depth += 1
            elif b == b'}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end != -1:
            try:
                inv = json.loads(data[start:end].decode("utf-8", errors="ignore"))
                max_slots = inv.get("MaxSlotIndex", -1)
                if max_slots is not None and max_slots >= 0:
                    slots = {k: v for k, v in inv.items() if k.isdigit() and isinstance(v, dict)}
                    
                    # Prefix context analysis
                    prefix = data[max(0, start-600):start]
                    
                    owner = "World / Unowned"
                    for eos_id, pname in KNOWN_PLAYER_EOS_IDS.items():
                        if eos_id.encode() in prefix:
                            owner = pname
                            break

                    bps = re.findall(rb'BP_[A-Za-z0-9_]+', prefix)
                    actor_raw = bps[-1].decode("latin1") if bps else "BP_Storage_Container_C"

                    display_name = format_container_name(actor_raw, owner)
                    capacity = max_slots + 1
                    occupied_slots = len(slots)
                    total_items_in_container = sum(v.get("Count", 1) for v in slots.values())

                    container_id = f"cont-{container_counter:03d}"
                    container_counter += 1

                    slots_list = []
                    for slot_idx_str, slot_data in sorted(slots.items(), key=lambda x: int(x[0])):
                        item_id = slot_data.get("ItemData") or "Unknown"
                        count = slot_data.get("Count") or 1
                        durability = slot_data.get("Durability")
                        upgrades = slot_data.get("NumUpgradesApplied") or 0

                        item_info = resolve_item(item_id)

                        slot_entry = {
                            "slot": int(slot_idx_str),
                            "item_id": item_id,
                            "name": item_info.get("name") or item_id,
                            "raw_id": item_info.get("raw_id") or item_id,
                            "category": item_info.get("category") or "General",
                            "count": count,
                            "durability": durability,
                            "upgrades": upgrades,
                        }
                        slots_list.append(slot_entry)

                        # Server-wide item aggregation
                        if item_id not in items_map:
                            items_map[item_id] = {
                                "item_id": item_id,
                                "name": item_info.get("name") or item_id,
                                "raw_id": item_info.get("raw_id") or item_id,
                                "category": item_info.get("category") or "General",
                                "total_count": 0,
                                "container_count": 0,
                                "containers": [],
                            }
                        items_map[item_id]["total_count"] += count
                        items_map[item_id]["containers"].append({
                            "container_id": container_id,
                            "container_name": display_name,
                            "owner": owner,
                            "slot": int(slot_idx_str),
                            "count": count,
                            "durability": durability,
                        })

                    containers.append({
                        "id": container_id,
                        "name": display_name,
                        "actor": actor_raw,
                        "owner": owner,
                        "capacity": capacity,
                        "occupied_slots": occupied_slots,
                        "total_items": total_items_in_container,
                        "slots": slots_list,
                    })
            except Exception:
                pass

    for it in items_map.values():
        it["container_count"] = len(it["containers"])

    # Sort items by total count descending
    sorted_items = sorted(items_map.values(), key=lambda x: x["total_count"], reverse=True)
    total_stored_items = sum(c["total_items"] for c in containers)

    result = {
        "containers": containers,
        "items": sorted_items,
        "total_containers": len(containers),
        "total_stored_items": total_stored_items,
        "unique_items_count": len(sorted_items),
        "save_file": os.path.basename(target_save),
        "cache_key": cache_key,
    }

    _storage_cache = result
    _storage_cache_mtime = current_mtime
    return result


def search_stored_items(query: str = "", saves_dir: str = SAVES_DIR, save_filename: str = None) -> list:
    """Searches server-wide stored items by item name, raw id, item id, category, container name, or owner."""
    data = parse_storage_data(saves_dir=saves_dir, save_filename=save_filename)
    items = data.get("items", [])
    if not query:
        return items

    q = query.lower().strip()
    filtered = []
    for it in items:
        # Match item name, raw ID, GUID, or category
        if (q in it.get("name", "").lower() or
            q in it.get("raw_id", "").lower() or
            q in it["item_id"].lower() or
            q in it.get("category", "").lower()):
            filtered.append(it)
            continue
        # Match container name or owner
        has_match = any(
            q in c["container_name"].lower() or q in c["owner"].lower()
            for c in it["containers"]
        )
        if has_match:
            filtered.append(it)

    return filtered


def get_storage_units(saves_dir: str = SAVES_DIR, save_filename: str = None) -> list:
    """Returns all storage containers and their slot contents."""
    data = parse_storage_data(saves_dir=saves_dir, save_filename=save_filename)
    return data.get("containers", [])

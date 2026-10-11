"""
Dragonwilds Item Resolution & Canonical Name Resolver.

Resolves internal Unreal Engine item GUIDs (128-bit UUIDs serialized as 22-char base64)
and blueprint identifiers to human-readable item names and categories.
Strictly Read-Only and high-performance (sub-microsecond in-memory dictionary lookup).
"""

import os
import re
import json

_CATALOG = None
_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "data", "item_guids.json")


def _format_identifier_name(raw: str) -> tuple[str, str]:
    """Fallback heuristic to convert raw identifiers into human names and categories."""
    s = raw
    category = "General"

    if s.startswith("res_rune_"):
        rune = s.replace("res_rune_", "").title()
        return f"{rune} Rune", "Runes"
    if s.startswith("res_wood_"):
        wood = s.replace("res_wood_", "").title()
        return f"{wood} Logs", "Resources"
    if s.startswith("res_plank_"):
        wood = s.replace("res_plank_", "").title()
        return f"{wood} Plank", "Resources"
    if s.startswith("res_plank"):
        return "Regular Plank", "Resources"
    if s.startswith("res_fish_"):
        fish = s.replace("res_fish_", "").title()
        return f"Raw {fish}", "Fishing"
    if s.startswith("food_fish_"):
        fish = s.replace("food_fish_", "").replace("_burnt", "").title()
        if "_burnt" in s:
            return f"Burnt {fish}", "Food"
        return f"Cooked {fish}", "Food"
    if s.startswith("res_ore_"):
        ore = s.replace("res_ore_", "").title()
        return f"{ore} Ore", "Mining"
    if s.startswith("res_bar_"):
        bar = s.replace("res_bar_", "").title()
        return f"{bar} Bar", "Smithing"
    if s.startswith("tool_farming_seed_"):
        seed = s.replace("tool_farming_seed_", "").replace("_", " ").title()
        return f"{seed} Seed", "Farming"
    if s.startswith("farming_treeseed_"):
        tree = s.replace("farming_treeseed_", "").replace("_", " ").title()
        return f"{tree} Tree Seed", "Farming"
    if s.startswith("plan_"):
        plan_desc = s.replace("plan_decoration_general_", "").replace("plan_", "").replace("_", " ").title()
        return f"Plan: {plan_desc}", "Plans"
    if s.startswith("potion_"):
        pot = s.replace("potion_focused_", "").replace("potion_", "").replace("_", " ").title()
        return f"Potion ({pot})", "Potions"
    if s.startswith("vestige_"):
        vest = s.replace("vestige_", "").replace("_", " ").title()
        return f"Vestige: {vest}", "Equipment"
    if s.startswith("ammo_"):
        ammo_desc = s.replace("ammo_", "").replace("_", " ").title()
        return f"Ammo: {ammo_desc}", "Ammo"
    if s.startswith("recipe_"):
        rec = s.replace("recipe_", "").replace("_", " ").title()
        return f"Recipe: {rec}", "Recipes"

    if s.startswith("res_"):
        category = "Resources"
        s = s[4:]
    elif s.startswith("food_"):
        category = "Food"
        s = s[5:]
    elif s.startswith("tool_"):
        category = "Tools"
        s = s[5:]
    elif s.startswith("weapon_") or s.startswith("weap_"):
        category = "Weapons"
        s = s.split("_", 1)[1]
    elif s.startswith("armour_") or s.startswith("armor_"):
        category = "Armour"
        s = s.split("_", 1)[1]
    elif s.startswith("BP_Consumables_"):
        category = "Consumables"
        s = s.replace("BP_Consumables_", "")
    elif s.startswith("ITEM_"):
        parts = s.split("_")
        category = parts[1] if len(parts) > 1 else "Item"
        s = " ".join(parts[2:])

    words = s.replace("_", " ")
    words = re.sub(r'([a-z])([A-Z])', r'\1 \2', words)
    display = re.sub(r'\s+', ' ', words).strip().title()

    display = display.replace("Water Dirty", "Dirty Water")
    display = display.replace("Water Clean", "Clean Water")
    display = display.replace("Stone Block", "Stone Block")
    display = display.replace("Steakandeggs", "Steak & Eggs")
    display = display.replace("Spade Wood", "Wooden Spade")
    display = display.replace("Spade Bronze", "Bronze Spade")
    display = display.replace("Watering Can Wood", "Wooden Watering Can")
    display = display.replace("Watering Can Bronze", "Bronze Watering Can")
    display = display.replace("Bucket Compost", "Compost Bucket")
    display = display.replace("Fishing Rod Ash", "Ash Fishing Rod")
    display = display.replace("Fishing Rod Maple", "Maple Fishing Rod")
    display = display.replace("Fishing Net Coarse", "Coarse Fishing Net")
    display = display.replace("Pick Stone", "Stone Pickaxe")
    display = display.replace("Club Stone", "Stone Club")
    display = display.replace("Shield Wood", "Wooden Shield")
    display = display.replace("Recipe Unlocker 2", "Recipe Unlocker")
    display = display.replace("Skill Tome", "Skill Tome")
    display = display.replace("Plant Cure", "Plant Cure")
    display = display.replace("Swamp Tar", "Swamp Tar")
    display = display.replace("Skin Scraps", "Skin Scraps")
    display = display.replace("Vaultcore", "Vault Core")

    return display, category


def load_catalog(filepath: str = None) -> dict:
    """Loads the catalog into memory once."""
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG

    path = filepath or _CATALOG_PATH
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _CATALOG = json.load(f)
                return _CATALOG
        except Exception:
            pass

    _CATALOG = {}
    return _CATALOG


def resolve_item(item_id: str) -> dict:
    """Resolves any item ID (GUID or identifier) to its human-readable name, raw ID, and category."""
    if not item_id or item_id == "Unknown":
        return {
            "item_id": item_id or "Unknown",
            "name": "Unknown Item",
            "raw_id": item_id or "Unknown",
            "category": "Unknown",
        }

    catalog = load_catalog()
    if item_id in catalog:
        entry = catalog[item_id]
        return {
            "item_id": item_id,
            "name": entry.get("name") or item_id,
            "raw_id": entry.get("raw_id") or item_id,
            "category": entry.get("category") or "General",
        }

    # If it's not a GUID in the catalog, format the raw string
    # Check if it looks like a base64 hash (22 chars with base64 characters)
    if len(item_id) == 22 and re.match(r'^[A-Za-z0-9_-]{22}$', item_id):
        # Unmapped GUID fallback
        return {
            "item_id": item_id,
            "name": f"Item ({item_id[:6]}...)",
            "raw_id": item_id,
            "category": "Item",
        }

    name, cat = _format_identifier_name(item_id)
    return {
        "item_id": item_id,
        "name": name,
        "raw_id": item_id,
        "category": cat,
    }


def get_item_name(item_id: str) -> str:
    """Returns human-readable name for an item ID."""
    return resolve_item(item_id)["name"]

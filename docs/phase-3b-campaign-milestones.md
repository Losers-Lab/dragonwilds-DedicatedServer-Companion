# Phase 3B: Campaign Milestones & In-World World Markers

## Overview
Phase 3B completes the world mapping and campaign milestone tracking for the Dragonwilds Dedicated Server Companion. It introduces server save extraction for campaign progression (unlocked shrines, spells, building recipes, crafting blueprints, elite kills, quest hooks) and plots persistent player landmarks (gravestones and claimed bedrolls) on the interactive world map radar.

## Architecture & Data Extraction
- **Module**: `campaign.py`
  - Scans active Unreal `.sav` binary files for embedded JSON progression blocks.
  - Extracts campaign unlocks:
    - `ShrinesUnlocked` (Ancient shrines discovered and activated)
    - `SpellsUnlocked` (Magic spells learned and attuned)
    - `BuildingsUnlocked` (Building structures learned)
    - `RecipesUnlocked` (Crafting recipes discovered)
    - `PlayerHooksTriggered` (World quest dialogues and story triggers)
    - `KilledOnceAIs` (Elite and world boss kills verified)
  - Extracts persistent world markers:
    - `BP_PlayerGraveyard_8Slots_C_UAID_*`: Player death gravestones holding lost inventories.
    - `BP_BaseBuilding_BedRoll_C`: Claimed player bedrolls serving as active spawn points.
  - Safe caching keyed on file `mtime` prevents unnecessary disk reads.
  - Strictly read-only file access; zero mutations to save files or server directories.

## API Endpoints
- `GET /api/campaign`
  - Returns JSON object with progression counts and lists:
    ```json
    {
      "summary": {
        "shrines_unlocked": 1,
        "spells_unlocked": 14,
        "buildings_unlocked": 97,
        "recipes_unlocked": 176,
        "elites_slain": 10,
        "gravestones_found": 17,
        "camps_found": 2,
        "quest_triggers": 31,
        "active_world_save": "Hardcore Losers.sav"
      },
      "shrines": ["Shrine_Overworld_01"],
      "spells": ["Spell_Fireball"],
      "buildings": ["BP_WoodWall_C"],
      "recipes": ["Recipe_IronSword_C"],
      "elites_slain": ["AI_DireWolf_Boss_C"],
      "death_markers": [
        {"id": "BP_PlayerGraveyard_8Slots_C_UAID_...", "short_id": "UAID_...", "name": "Player Gravestone #1", "zone": "Brynmoore", "index": 1}
      ],
      "camps": [
        {"name": "Settlement Bedroll #1", "zone": "Courtyard", "index": 1}
      ]
    }
    ```

## UI & World Map Radar Integration
- **Milestones Stat Grid**:
  - Embedded in the Bosses & Encounters tab with live badge counts: Spells Mastered, Blueprints, Recipes, Shrines, Elites Slain, Gravestones, Camps.
- **Canvas Map Radar Markers**:
  - Added toggleable layers: `🪦 Gravestones` and `⛺ Player Camps`.
  - Markers rendered with distinct purple and cyan pins, clickable with detailed inspector metadata (sector, grave number, UAID, respawn status).
- **Strict UI Preservation**:
  - Existing CSS styling, palette, and sidebar navigation preserved intact without unrequested UI overhaul.

## Testing & Validation
- Unit tests in `tests/test_campaign.py` verify empty directories, corrupted JSON handling, mock save parsing, and mtime cache invalidation.
- 33 automated tests passing cleanly.

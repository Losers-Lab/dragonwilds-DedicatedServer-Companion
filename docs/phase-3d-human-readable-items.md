# Phase 3D: Human-Readable Storage & Item Resolution

## Overview
In Dragonwilds, storage containers and player inventories serialize stored items using 128-bit Unreal Engine GUIDs (`FGuid`), base64-encoded URL-safely into 22-character strings (e.g. `2rxJ495rm0GDn4h5OWKiyQ`, `qOY004ZJaEaR8DmcDqB2KA`).

Phase 3D eliminates cryptic raw GUIDs across the companion dashboard and APIs by introducing an automated, in-memory item resolver mapped directly to authentic Unreal Engine pak table definitions (`RSDragonwilds-WindowsServer.pak`).

---

## Technical Architecture

### 1. GUID Extraction & Catalog Generation
- Unreal Engine data tables in `RSDragonwilds-WindowsServer.pak` serialize items in binary blocks where the item's internal identifier (e.g. `res_wood_ash`, `res_rune_essence`) is paired directly with its canonical 22-character base64 GUID.
- 6,110 authentic item GUID definitions are extracted and indexed in [`data/item_guids.json`](file:///c:/Users/arham/programs/dragonwilds-DedicatedServer-Companion/data/item_guids.json).

### 2. Item Resolver Module (`item_resolver.py`)
- Provides `resolve_item(item_id: str) -> dict`:
  - Instantaneous in-memory dictionary lookup (< 1 microsecond).
  - Returns `item_id`, human display `name`, internal `raw_id`, and `category`.
  - Fallback heuristic for blueprint identifiers and unknown GUIDs.

### 3. Server Storage Tracker Integration (`storage.py`)
- Slot iteration resolves every item instance to its friendly name, category, and raw ID.
- Server-wide aggregation indexes items under both friendly name and raw ID.
- `search_stored_items()` supports live fuzzy querying across:
  - Human display name (e.g. `Ash Logs`, `Clean Water`, `Essence Rune`, `Cooked Shrimp`)
  - Item category (e.g. `Resources`, `Food`, `Runes`, `Mining`, `Farming`, `Tools`)
  - Raw internal identifier (e.g. `res_wood_ash`, `food_water_clean`)
  - Container name (e.g. `Base Chest Iron`, `Dungeon Cache Lunch`)
  - Owner name (e.g. `Arham`, `Mango`, `slayingmerch`)

### 4. Dashboard UI Enhancements (`app.py`)
- **Stored Items Tracker**:
  - Displays primary human-readable item name in bold.
  - Highlights item category with a subtle badge.
  - Displays secondary raw ID as a subtle monospace subtitle.
- **Inspect Container Modal**:
  - Displays formatted name, category pill, count, and durability per slot.
- **Live Search**:
  - Search bar input placeholder updated to guide players to search by item name or category.

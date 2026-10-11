# Phase 3E: Authentic World Map Coordinate Unification & Telemetry Alignment

## Overview
Phase 3E addresses coordinate discrepancies on the Interactive World Map of Ashenfall. Previously, markers for world chests, player death gravestones, camps, and boss arenas relied on legacy zone-grid approximations (`getChestWorldCoords`, `getGraveWorldCoords`, `getBossWorldCoords`, `getCampWorldCoords`) and a local Brynmoore calibration that clamped subterranean and out-of-bounds actors to the far-left map border (`X=15.0`).

This phase establishes full, objective alignment between:
1. **Unreal Engine 3D World Transforms (`FTransform` / CORA chunk)** extracted from SpudCache `.lvl` levels and savefiles.
2. **Global Continental Ashenfall Canvas Coordinates (`1000x1000`)** across all four quadrants.
3. **Subterranean Instanced Dungeons & Arenas** (Brynmoore Catacombs & Kalphite Queen hive) mapped onto their canonical surface entrances.
4. **Unified Interactive Map Telemetry** allowing users to inspect exact 3D coordinates, grid cells, and persistent UAIDs.

---

## Architectural Changes

### 1. Global & Subterranean Coordinate Calibration (`worldactors.py`)
- **Subterranean Crypt / Catacomb Dungeon Translation**:
  Chests and actors inside subterranean cells (e.g. `RSACell12800_X-13_Y7`, `RSACell12800_X-14_Y8` at `Z < -20,000 cm`, `X ≈ -170,000 cm`) are anchored beneath the Brynmoore Ancient Courtyard and Ashen Crypts (`280.0, 510.0`), distributing rooms across valid canvas space instead of flattening at `X=15.0`.
- **Subterranean Desert Hive Translation**:
  Actors in the Kalphite Queen Arena (`X ≈ -456,000 cm`, `Z ≈ -36,000 cm`) are anchored beneath the Dunes of Uzer (`650.0, 620.0`).
- **Global Overworld Calibration**:
  Maps the 896 km² Unreal Engine world bounds across the 1000x1000 canvas with safe boundary clamps (`20.0 <= x <= 980.0`, `20.0 <= y <= 980.0`). Clamped actors dropped from 341 down to 5 out-of-bounds prototype switches.

### 2. Authentic Player Gravestone Telemetry (`campaign.py`)
- Gravestones extracted from `.sav` saves are cross-referenced against `BP_PlayerGraveyard_8Slots_C` actors in SpudCache.
- All 17 active gravestones now carry authentic 3D transforms (`world_pos`), map coordinates (`map_coords`), and world grid cell names (`cell`), spanning the full continent from Brynmoore (`X=242.0`) to the eastern desert (`X=755.7`).
- Non-SpudCache gravestones receive deterministic, non-colliding sector coordinates.

### 3. Unified Chests Catalog (`respawns.py` & `app.py`)
- `/api/world/actors?category=all` provides all 43 level-extracted treasure chests and loot nodes.
- Server log respawn events (`SetRespawnTimer`) are correlated by actor UAID.
- The Interactive Map draws chests at their authentic in-engine coordinates and overlays live respawn timers when active.

### 4. Canonical Boss Arena Mapping (`bosses.py` & `app.py`)
- Attached authentic `map_coords` and canonical `region_id` to all 7 canonical boss encounters:
  - **The Dragon Arena**: Dragon's Run (`530.0, 350.0`)
  - **Kalphite Queen Arena**: Dunes of Uzer (`650.0, 620.0`)
  - **Fight Caves (TzTok-Jad)**: The Burning Spire (`570.0, 400.0`)
  - **Nightmare Crucible**: Demon Gate (`550.0, 450.0`)
  - **Titan Door Vault**: The Bastion (`620.0, 380.0`)
  - **Umbral Door Sanctum**: Al Kharid Oasis (`670.0, 440.0`)
  - **Death's Temple**: Ashen Crypts (`340.0, 650.0`)

### 5. Frontend Visualizer & Inspector Alignment (`app.py`)
- `getChestWorldCoords`, `getGraveWorldCoords`, `getCampWorldCoords`, and `getBossWorldCoords` prioritize authentic `obj.map_coords` before falling back to approximations.
- Hit testing (`findMapMarkerAt`) and canvas drawing (`renderWorldMap`) use authentic coordinates.
- Inspector sidebar displays exact 3D coordinates (`X, Y, Z cm`), World Grid Cell names, map canvas coordinates, and verification badges (`Verified SpudCache 3D Transform` or `Live Log Telemetry`).

---

## Verification & Test Results
- **Unit Test Suite**: 43/43 tests passing cleanly.
- **Docker Production Container**: Rebuilt and running healthy on port `9876`.
- **Zero Host Writes**: Strictly read-only operations preserved across all save and cache directories.

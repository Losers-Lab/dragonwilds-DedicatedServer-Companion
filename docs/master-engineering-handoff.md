# Dragonwilds Dedicated Server Companion — Master Engineering Handoff Document

> [!IMPORTANT]
> **Executive Summary for the Resuming Agent**  
> All phases up through **Phase 2C** are **fully implemented, peer-reviewed via independent PRs, merged into `main` without squash (`--no-ff`), and actively deployed in Docker** at `http://losers-dragonwilds.duckdns.org:9876` (local `http://localhost:9876`).  
> All **14/14 unit tests are passing**. The working tree on `main` is completely clean.

---

## 1. System & Environment Context

- **Repository**: `https://github.com/Losers-Lab/dragonwilds-DedicatedServer-Companion.git`
- **Current Branch**: `main` (Latest commit `47a73d8`: *Merge pull request #5 from feature/phase-2c-resource-respawn-tracker*)
- **Working Directory**: `c:\Users\arham\programs\dragonwilds-DedicatedServer-Companion`
- **Live Deployment URL**: `http://losers-dragonwilds.duckdns.org:9876` (`http://localhost:9876`)
- **Docker Container**: `dragonwilds-companion` (Running Python 3.12-slim, exposed on port 9876)
- **Host Server Path (Strictly READ-ONLY)**: `C:\DragonwildsServer\RSDragonwilds\Saved`
  - Saves: `C:\DragonwildsServer\RSDragonwilds\Saved\SaveGames` (`The Losers.sav`, `Hardcore Losers.sav`)
  - Logs: `C:\DragonwildsServer\RSDragonwilds\Saved\Logs` (`RSDragonwilds.log` + active rotation backups)
  - Config: `C:\DragonwildsServer\RSDragonwilds\Saved\Config\WindowsServer\DedicatedServer.ini`
  - Engine Paks: `C:\DragonwildsServer\RSDragonwilds\Content\Paks\RSDragonwilds-WindowsServer.pak`
- **GitHub Token**: Provided via active environment / PowerShell variable (used for GitHub REST API PR creation and merges)

---

## 2. Hard Commitments & Non-Negotiable Rules

1. **Strictly Read-Only Boundary**:
   - Under NO circumstances may any script, tool, or endpoint write or mutate files in `C:\DragonwildsServer`, `/savegames`, `/logs`, or `/serverconfig`. All mounts must be `:ro`.
2. **Autonomous Pull Request & Independent Review Pipeline**:
   - **Never commit directly to `main`**. Every mini-phase must be built on its own feature branch (`feature/<name>`).
   - Every feature branch must be pushed to GitHub and opened as a real PR on `Losers-Lab/dragonwilds-DedicatedServer-Companion`.
   - The `code-reviewer` subagent must be invoked to independently review the git diff (`git diff main..<branch>`), run the Docker test suite, and issue a verdict.
   - You must address any `VERDICT: REQUEST_CHANGES` until `VERDICT: APPROVE` is granted.
   - Merge PRs into `main` using merge commits (`--no-ff` / `merge_method: merge`). **NO SQUASHING**.
3. **Continuous Deployment**:
   - Immediately after every merge into `main`, pull `main` locally and run `docker compose up -d --build` so the live website reflects the update immediately.
4. **Data Transparency & Objective Truth (Critical User Directives)**:
   - **NO HARDCODING OR GUESSING**: Never invent or hardcode respawn timers (e.g. do not hardcode "net fishing is 3 days" or "dragons respawn in 90 minutes"). If data is not emitted by the game server logs or serialized in the save file, **do not attempt to be the source of truth yourself**. Treat data strictly as an objective data problem.
   - **Data Source Badges**: Every single metric must be transparently badged:
     - `⚡ Live Telemetry`: Real-time data from server memory/logs (`active_players`, `LogChests: SetRespawnTimer()`, server CPU/RAM).
     - `💾 Save File (as of <timestamp>)`: Data extracted from `.sav` snapshots (`world.day_count`, save size, world seed, world entity index), with tooltips displaying exact timestamps.
   - **Un-curated & Exhaustive Search**: Do not filter out "trash mobs" (rats, goblins, sticks) with hand-curated exclusions. Index all entities objectively and let users search, filter, and discover through the UI.

---

## 3. What Has Been Completed & Deployed

| Phase | PR | Commit | Description & Achievements | Status |
|---|---|---|---|---|
| **Phase 1: Environment & Server Roster** | PR #1 | `4a7e5ca` | In-world character names, live weather cards, Steam ID profile links, role badges (Owner/Admin), `.sav.backup` download portal, Docker cgroups memory monitoring. | **MERGED & LIVE** |
| **Phase 2A: Dynamic Region Lore & Weather** | PR #2 | `9aff244` | Dynamic region lore parser resolving all 31 canonical regions from `ST_UI_MapRegions` (`GET /api/world/regions`). Decoupled the engine internal `"base"` weather label. | **MERGED & LIVE** |
| **Phase 2B: Day/Night Solar Dial & Data Badges** | PR #3 & PR #4 | `b6f5cd0`, `0d60b61` | Authentic in-game solar clock SVG matching user reference: 3 distinct sectors (Night with crescent moon, grayed-out Daytime Remaining, and dynamically illuminated golden Daytime Passed swept by `clip-day-passed` leading edge up to needle). Needle starts at Dawn (210°) and rotates smoothly clockwise. | **MERGED & LIVE** |
| **Phase 2C: World Entities & Live Respawn Tracker** | PR #5 | `47a73d8` | Live chest respawn timers parsed directly from `LogChests: SetRespawnTimer()` and `PerformRespawn()`. Exhaustive save entity index covering all 770+ entity archetypes and 5,000+ instances. Thread-safe `RespawnTracker`, defensive duration parsing, and dedicated Web UI Respawns tab. | **MERGED & LIVE** |

---

## 4. Architectural Deep Dive: Current Codebase

### A. [`respawns.py`](file:///c:/Users/arham/programs/dragonwilds-DedicatedServer-Companion/respawns.py)
- **`RespawnTracker`**:
  - `scan_live_logs()`: Reads active and recent logs for `LogChests: [DedicatedServer] SetRespawnTimer() : Chest "<id>" set to respawn +<dur> from now` and `PerformRespawn()`. Parses Unreal Engine timespans (`+5.00:00:00.000`, `+1.23:16:07.741`, `+19:20:22.095`).
  - `scan_save_world_entities()`: Parses latest `.sav` file, extracts all `BP_*` entity archetypes, and groups them into objective categories (`Chests & Vaults`, `Ore & Mineral Veins`, `Mining Rocks & Crystals`, `Fishing Nodes`, `Flora & Foraging Spawners`, `NPCs & Creatures`, `Bosses, Dragons & Monsters`, etc.). Caches by save file `mtime`.
  - `get_respawns(category_filter, search_query)`: Protected by a `threading.Lock()` and cached with a 3.0s TTL.
- **`format_actor_label(actor_name)`**: Normalizes internal engine identifiers into human-readable names.
- **`parse_duration_seconds(dur_str)`**: Defensively parses timespans into total seconds, safely returning `0.0` on `None` or invalid input.

### B. [`worldreader.py`](file:///c:/Users/arham/programs/dragonwilds-DedicatedServer-Companion/worldreader.py)
- **`calculate_day_cycle(day_count, save_mtime)`**:
  - Standard day duration: **840.0s (~14 minutes)** per in-game day.
  - Cycle progression starts at Dawn (210°, approx 7 o'clock). 240° day arc sweeps through 360°/0° (Midday/Noon) to 90° (Afternoon/Sunset). 120° night arc sweeps from 90° to 210°.
  - Returns `progress_percent`, `needle_angle_deg`, `phase`, `phase_icon`, `seconds_in_day`, and `is_night`.
- **`get_world_data()`**: Extracts `day_count`, `world_name`, `weather`, and `seed`. Cached by save `mtime`.

### C. [`app.py`](file:///c:/Users/arham/programs/dragonwilds-DedicatedServer-Companion/app.py)
- **Frontend Architecture**: Single-page application serving desktop and mobile layouts.
- **Views**:
  1. `Overview`: 8 stat cards with Live/Saved transparency badges, circular solar dial with dynamic SVG arc shading, and regional weather forecast.
  2. `Respawns`: Live entity and chest tracker with category pills, instant live search, and live countdowns.
  3. `Players`: Active online players + all-time server roster with Steam community links.
  4. `Backups`: Download active `.sav` and timestamped `.sav.backup` files.
  5. `Leaderboard`: Playtime leaderboard and session metrics.
  6. `Events`: Live event log feed.
  7. `Logs`: Filterable, searchable log terminal with live streaming toggle.

---

## 5. Next Steps for Resuming Agent (Phase 2D & Beyond)

### Phase 2D: Master Item Database & Chest Inventory Search (Next Up)
- **Branch**: `feature/phase-2d-master-item-database-and-vaults`
- **Objective**:
  1. We already discovered **1,704 official game items** (`ITEM_Ammo_*`, `ITEM_Armor_*`, `ITEM_Weapon_*`, `ITEM_Resources_*`) directly inside `RSDragonwilds-WindowsServer.pak`.
  2. Create an `items.py` module embedding/loading this official item catalog.
  3. Decode `WorldItemInventory` and `LinkedInventoryComponent` across chests in `The Losers.sav` and `Hardcore Losers.sav`.
  4. Expose `GET /api/items` with search by item name, tier, and category.
  5. Add an **Items & Vaults** tab in the dashboard allowing players to search for any item in the game and find where it's stored.
  6. Run tests, open PR, independent code review, merge `--no-ff`, and deploy with `docker compose up -d --build`.

### Phase 3: Live Event Stream, Boss Checklist & 2D World Map
- Track real-time server events from logs (dragon encounters, chest looting, player connections).
- Track defeated bosses checklist (`DefeatedBossesInternalNames` in `.sav`).
- Interactive 2D World Map plotting canonical regions and player spawn locations.

### Phase 4: Modern Dashboard Visual Overhaul
- Refined dark theme styling, compact stat counters, and responsive mobile enhancements.

---

## 6. How to Run Tests & Verify Locally

```powershell
# Run the complete test suite (14/14 tests) inside Docker:
docker run --rm -v "C:/Users/arham/programs/dragonwilds-DedicatedServer-Companion:/app:ro" -w /app python:3.12-slim python -m unittest discover -s tests -v

# Verify container is running:
docker ps --filter "name=dragonwilds-companion"

# Verify API responses:
Invoke-RestMethod -Uri "http://localhost:9876/status"
Invoke-RestMethod -Uri "http://localhost:9876/api/respawns"
Invoke-RestMethod -Uri "http://localhost:9876/api/world/regions"
```

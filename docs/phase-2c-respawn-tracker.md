# Phase 2C: Resource, Dungeon Chest & Elite Respawn Tracker

## Overview
Phase 2C implements a comprehensive respawn tracking system that monitors:
1. **Dungeon and Vault Treasure Chests**: Parsed via real-time server log telemetry (`LogChests: [DedicatedServer] SetRespawnTimer()`, `PerformRespawn()`).
2. **Net Fishing Spots (3-Day Cycle)**: Tracks the canonical 3-day fishing net cycle across all regions (Brynmoor, Dowdun Reach, Fellhollow, Ghornfell, Scorned Wilderness, Umbral Sands).
3. **World Bosses & Elites**: Tracks Kalphite Queen, Red Dragon Fuzan, Dragon Imaru, Dragon Kuldra Heart, and Dragonkin Conduits.
4. **High-Tier Mining Ores**: Tracks Luminite Crystals, Runite, Adamantite, Avisk Crystals, and Pure Rune Essence nodes.

---

## Architecture & Data Flow

```
┌─────────────────────────────────┐      ┌───────────────────────────────┐
│ Server Logs (LogChests Events)  │      │ World Registry & Cycles       │
│  - SetRespawnTimer()            │      │  - 3-day Fishing Net cycles   │
│  - PerformRespawn()             │      │  - World Boss timers          │
└────────────────┬────────────────┘      └──────────────┬────────────────┘
                 │                                      │
                 ▼                                      ▼
            ┌───────────────────────────────────────────────┐
            │         respawns.py (RespawnTracker)          │
            │  - Parses Unreal Engine timespan durations    │
            │  - Filters low-level trash mobs by default    │
            │  - Computes dynamic live remaining countdowns │
            └───────────────────────┬───────────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │ GET /api/respawns     │
                        │  - ?category=<filter> │
                        │  - ?search=<query>    │
                        └───────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │ Web UI Respawns Tab   │
                        │  - Category pills     │
                        │  - Live search input  │
                        │  - Status badges      │
                        └───────────────────────┘
```

---

## API Specification: `GET /api/respawns`

### Query Parameters
- `category` (optional): Filter by category (`all`, `Dungeon Chests`, `Fishing Nets (3-Day Cycle)`, `World Bosses & Elites`, `High-Tier Mining Ores`).
- `search` (optional): Text query to filter targets by name, engine ID, or category.

### Response
```json
[
  {
    "id": "BP_Dungeon_Treasure_Chest_BM_Cook_World_Cache_C_UAID_00BE4395530E7E0C02_1510875401",
    "name": "Brinemoor Cook's Cache",
    "category": "Dungeon Chests",
    "status": "respawning",
    "remaining_seconds": 389420.5,
    "respawn_time": "2026-10-15 19:05:28",
    "duration_formatted": "5d 0h 0m",
    "remaining_formatted": "4d 12h 10m",
    "source": "live_log",
    "is_ready": false
  },
  {
    "id": "fishing_net_brynmoor",
    "name": "Brynmoor Coastal Fishing Nets",
    "category": "Fishing Nets (3-Day Cycle)",
    "status": "ready",
    "remaining_seconds": 0.0,
    "respawn_time": "Ready",
    "duration_formatted": "42m 0s",
    "remaining_formatted": "Ready to Loot / Active",
    "source": "world_registry",
    "is_ready": true
  }
]
```

---

## Verification & Testing
- Unit tests in `tests/test_respawns.py` verify timespan parser, actor name formatting, log timestamp parsing, category filtering, and search functionality.
- 14/14 tests pass across the companion test suite.

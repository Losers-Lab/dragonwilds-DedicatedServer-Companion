# REST API Reference

The Companion server exposes JSON endpoints on port `9876` (or configured `PORT`).

---

## 1. System & Status

### `GET /status`
Returns real-time server health, player counts, resource metrics, environment data, and recent activity.

**Response Example:**
```json
{
  "status": "online",
  "server": "Dragonwilds",
  "world": "Hardcore Losers",
  "version": "1.0.0.8",
  "players_online": 0,
  "max_players": 6,
  "players": [],
  "cpu": "0.1%",
  "memory": "1.0 GiB",
  "uptime": "13h 17m",
  "last_save": "12s ago",
  "day_count": 34,
  "weather": [
    {
      "icon": "☀️",
      "raw_region": "base",
      "region": "Central",
      "remaining_seconds": 2490.5,
      "remaining_text": "41m left",
      "type": "Sunny"
    }
  ],
  "roster": [
    {
      "is_admin": true,
      "is_banned": false,
      "is_owner": true,
      "name": "Replay",
      "online": false,
      "steam_id": "76561198026258675",
      "user_id": "00022ef6635e4d538914b423d8bb18c3"
    }
  ]
}
```

---

## 2. Environment & Climate

### `GET /api/weather`
Returns world day count and active regional weather forecasts.

**Response Example:**
```json
{
  "day_count": 35,
  "weather": [
    {
      "icon": "☀️",
      "raw_region": "base",
      "region": "Central Ashenfall (Overworld)",
      "remaining_seconds": 2490.5,
      "remaining_text": "41m left",
      "type": "Sunny"
    },
    {
      "icon": "⛅",
      "raw_region": "dowdun",
      "region": "Dowdun Reach",
      "remaining_seconds": 3890.1,
      "remaining_text": "1h 4m left",
      "type": "Cloudy"
    }
  ]
}
```

### `GET /api/world/regions`
Returns the 30+ canonical world map regions and biomes discovered from the game binary (`ST_UI_MapRegions`).

**Response Example:**
```json
[
  {
    "id": "MapRegionAlcarridOasis",
    "name": "Al Kharid Oasis",
    "biome": "Desert"
  },
  {
    "id": "MapRegionApproach",
    "name": "The Approach",
    "biome": "Plains"
  },
  {
    "id": "MapRegionWhisperingSwamp",
    "name": "Whispering Swamp",
    "biome": "Swamp"
  }
]
```

---

## 3. Players & Roster

### `GET /api/roster`
Returns the all-time known player directory parsed from `DedicatedServer.ini` and enriched with linked Steam 64 accounts.

**Response Example:**
```json
[
  {
    "user_id": "00022ef6635e4d538914b423d8bb18c3",
    "name": "Replay",
    "steam_id": "76561198026258675",
    "is_owner": true,
    "is_admin": true,
    "is_banned": false,
    "online": false
  }
]
```

### `GET /leaderboard`
Returns playtime ranking and session statistics from the companion database.

---

## 4. Save Game Backups

### `GET /api/save-files`
Lists all `.sav` and `.sav.backup` files in the save games directory sorted by modification time descending.

**Response Example:**
```json
[
  {
    "filename": "Hardcore Losers.sav",
    "is_backup": false,
    "size_bytes": 1160785,
    "size_str": "1.11 MB",
    "modified_iso": "2026-10-10T20:29:44.539057+00:00",
    "modified_text": "2026-10-10 20:29:44 UTC"
  }
]
```

### `GET /api/save-files/download/<filename>`
Downloads the specified save file as an attachment (`Content-Disposition: attachment`).
- Path traversal is strictly protected.
- Only `.sav` and `.sav.backup` extensions are accepted.

---

## 5. Campaign, Storage & World State

### `GET /api/campaign`
Returns overall world campaign milestones, unlock counts, and player world markers (gravestones and claimed bedrolls).

### `GET /api/storage/units`
Returns active storage units and containers with item counts and locations.

### `GET /api/storage/search?q=<query>`
Searches storage inventories for specific item names.

### `GET /api/farming`
Returns active crops and flora growth tracking by species and instance plots.

### `GET /api/bosses`
Returns canonical boss arenas, encounter statuses, and world event logs.

### `GET /api/world/actors`
Returns world persistent actors extracted directly from Unreal Engine SPUD level cache (`.lvl` files) with sub-centimeter 3D coordinates, categorized into Fishing spots, NPCs, Shrines, Agility shortcuts, and Chests. Served with zero-latency in-memory caching.
- **Query Parameters**:
  - `category` (optional): Comma-separated list of categories (`fishing`, `npcs`, `shrines`, `shortcuts`, `chests`, `geysers`, `all`).
  - `refresh` (optional): `true` to force directory rescanning.
- **Response Format**:
  ```json
  {
    "status": "ok",
    "cached": true,
    "cache_age_seconds": 0.12,
    "counts": {
      "fishing": 36,
      "npcs": 24,
      "shrines": 6,
      "shortcuts": 3,
      "chests": 43
    },
    "actors": {
      "fishing": [
        {
          "id": "UAID_DC97BA249CD4FCC402_1335208840",
          "title": "Net Fishing Spot",
          "category": "fishing",
          "cell": "RSACell12800_X0_Y13",
          "world_pos": { "x": 3406.0, "y": 178721.0, "z": -3167.7 },
          "map_coords": { "x": 206.1, "y": 485.1 },
          "hint": "Requires Small Fishing Net. Harvests trout, salmon, and river fish."
        }
      ]
    }
  }
  ```



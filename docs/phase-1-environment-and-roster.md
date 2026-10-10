# Phase 1: Environment & Server Roster Documentation

## Overview
Phase 1 enhances the Dragonwilds Dedicated Server Companion with live environment telemetry, world progression indicators, server roster mapping, and safe save file downloads.

---

## 1. Environment & World Clock
- **Day Counter**: Extracted dynamically from the active `.sav` file SPUD data (`DAY_COUNT`).
- **Regional Weather Forecast**: Live tracking across the 4 major regions:
  - Central (`base`)
  - Dowdun Reach (`dowdun`)
  - Umbral Sands (`sands`)
  - Scorned Wilderness (`Scorned Wilderness`)
- **Storm Countdown Timers**: Tracks exact remaining seconds for storms, rain, fog, and snow with automatic countdown formatting.
- **Throttled Save File Scanning**: `find_newest_save()` uses a 5-second TTL cache to prevent disk I/O thrashing during frequent HTTP polling.

---

## 2. All-Time Server Roster
- **Source**: `DedicatedServer.ini` (`KnownPlayerList` and `OwnerId`).
- **Account Linking**: Maps Epic Online Services (EOS) GUIDs to 64-bit Steam IDs via cross-save byte scanning (`RedpointEOS` and `STEAM` headers).
- **Role Hierarchy**:
  - 👑 **Server Owner** (`OwnerId` match)
  - 🛡️ **Administrator** (`PrivilegeMask > 0`)
  - 👤 **Member** (Standard player)
- **Live Online Status**: Correlated in real-time with connected player sessions from the server monitor.

---

## 3. Save File Backups & Downloads
- **Directory**: `/savegames` (mounted read-only from `C:\DragonwildsServer\RSDragonwilds\Saved\SaveGames`).
- **File Extensions**: Safely limited to `.sav` and `.sav.backup`.
- **Path Sanitization**: Cross-platform path normalization stripping both `/` and `\` separators to prevent directory traversal attacks.

---

## 4. API Endpoints
See [`docs/api.md`](./api.md) for full REST specifications.
- `GET /status` — Enriched with `day_count`, `weather`, and `roster`.
- `GET /api/weather` — Returns current world day and weather array.
- `GET /api/roster` — Returns all known players with roles and Steam IDs.
- `GET /api/save-files` — Lists available save files with sizes and modification times.
- `GET /api/save-files/download/<filename>` — Downloads raw save file as an attachment.

# Phase 2B: Day/Night Solar Dial & Data Transparency Badges

## Overview
Phase 2B implements two key user experience improvements:
1. **In-Game Day/Night Solar Dial**: An authentic recreation of the circular solar progress dial seen in-game in *Dragonwilds*, displaying current day number, phase (Dawn, Morning, Midday, Afternoon, Dusk, Night, Midnight), day progression percentage, and a smoothly rotating gold dial needle.
2. **Data Transparency Badging**: Clear visual distinction between live streaming data (`⚡ Live`) and periodic save-game snapshots (`💾 Saved (as of <time>)` with relative and absolute timestamps in tooltips).

---

## 1. Day / Night Solar Dial

### Engine Mechanics
- Dragonwilds day/night cycle runs on an internal in-game clock actor (`BP_InGameTimeActor`).
- Standard cycle length: **840.0 seconds (~14 minutes)** per full day cycle.
- The day progression is calculated via:
  $$\text{cycle\_seconds} = \text{day\_count} \times 840.0$$
  $$\text{progress\_pct} = (\text{cycle\_seconds} \pmod{840.0}) / 840.0 \times 100$$
  $$\text{needle\_rotation\_deg} = \text{progress\_pct} \times 3.6$$

### Solar Clock Visual Layout
The circular clock dial matches the in-game UI:
- **Right semicircle (0°–180°)**: Golden Sun with radiating flares ☀️ (Daytime).
- **Top-left quadrant (270°–360°)**: Periwinkle blue with crescent moon 🌙 (Night).
- **Bottom-left quadrant (180°–270°)**: Twilight slate shadow with muted dawn rays (Dawn/Dusk transition).
- **Needle**: A gold pointer (`#f59e0b`) anchored at the center pivot (50, 50) rotating smoothly in accordance with calculated progress.
- **Client-Side Live Interpolation**: The browser interpolates needle progression continuously between 5-second polling updates.

### API Response (`/status`)
```json
"world": {
  "day_count": 42.67,
  "day_cycle": {
    "day_number": 43,
    "progress_percent": 67.0,
    "needle_degrees": 241.2,
    "phase_name": "Dusk",
    "phase_icon": "🌇",
    "day_duration_seconds": 840.0,
    "seconds_into_day": 562.8
  }
}
```

---

## 2. Data Transparency Badging

To prevent confusion between live log events and periodic game saves:
- **Live Badges (`⚡ Live`)**: Displayed on real-time metrics such as Active Players, Current Weather, Uptime, Memory/CPU, and Log Events.
- **Saved Badges (`💾 Saved (as of <timestamp>)`)**: Displayed on metrics extracted from `.sav` files (World Day Count, Total Unique Players, World Seed, Save File Size).
  - Hovering displays full ISO-8601 timestamp and save filename.
  - Updates automatically whenever a new save is detected by `savewatcher.py`.

---

## Verification & Testing
- Unit tests in `tests/test_day_cycle.py` test day count calculations, phase name assignments, zero-day fallbacks, and degree boundaries (8/8 tests pass).
- Container build and integration verified.

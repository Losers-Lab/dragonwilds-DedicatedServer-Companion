# Phase 2B: Day/Night Solar Dial & Data Transparency Badges

## Overview
Phase 2B implements two key user experience improvements:
1. **In-Game Day/Night Solar Dial**: An authentic recreation of the circular solar progress dial seen in-game in *Dragonwilds*, displaying current day count, phase (*Morning*, *Midday*, *Afternoon*, *Dusk / Twilight*, *Night*), day progression percentage, and a smoothly rotating gold dial needle.
2. **Data Transparency Badging**: Clear visual distinction between live streaming process metrics (`⚡ Live` / `⚡ Process`) and periodic save-game snapshots (`💾 Saved (<time>)` / `💾 Snapshot` with relative timestamps and absolute hover tooltips).

---

## 1. Day / Night Solar Dial

### Engine Mechanics
- Dragonwilds day/night cycle runs on an internal in-game clock actor (`BP_InGameTimeActor`).
- Standard cycle length: **840.0 seconds (~14 minutes)** per full day cycle.
- The day progression calculation supports fractional day counts (e.g., `42.67` = 67% through day 42) plus wall-clock elapsed time since save creation:
  $$\text{fractional\_sec} = (\text{day\_count} \pmod{1.0}) \times 840.0$$
  $$\text{elapsed\_save} = \max(0.0, \text{now} - \text{save\_mtime})$$
  $$\text{total\_elapsed} = (\text{fractional\_sec} + \text{elapsed\_save}) \pmod{840.0}$$
  $$\text{cycle\_pos} = \frac{\text{total\_elapsed}}{840.0}$$
  $$\text{needle\_angle\_deg} = (\text{cycle\_pos} \times 360.0) \pmod{360.0}$$

### Solar Clock Visual Layout
The circular clock dial matches the in-game UI:
- **Right semicircle (0°–180°)**: Golden Sun with radiating flares ☀️ (Daytime / Morning to Afternoon).
- **Bottom-left quadrant (180°–270°)**: Twilight slate shadow with muted dawn rays (Dusk / Twilight transition).
- **Top-left quadrant (270°–360°)**: Periwinkle blue with crescent moon 🌙 (Night).
- **Needle**: A gold pointer (`#facc15` with `#78350f` border) anchored at the center pivot `(50, 50)` pointing straight up to `(50, 5)` at 12 o'clock (0°), rotating clockwise smoothly.
- **Client-Side Live Interpolation**: The browser interpolates needle progression continuously between 5-second polling updates.

### API Response (`/status`)
```json
{
  "day_cycle": {
    "day_count": 42.67,
    "progress_percent": 67.0,
    "phase": "Dusk / Twilight",
    "phase_icon": "🌇",
    "needle_angle_deg": 241.2,
    "seconds_in_day": 562.8,
    "cycle_duration_seconds": 840,
    "is_night": true
  }
}
```

---

## 2. Data Transparency Badging

To prevent confusion between live server process/log events and periodic game saves:
- **Live Badges (`⚡ Live` / `⚡ Process`)**: Displayed on real-time metrics such as Active Players, Connected Steam Accounts, Server Uptime, Memory/CPU, and Log Events.
- **Saved Badges (`💾 Saved (<time>)` / `💾 Snapshot`)**: Displayed on metrics extracted from `.sav` files (World Day Count, Total Unique Players, Regional Weather, World Seed, Save File Size).
  - Hovering displays full ISO-8601 timestamp and save filename.
  - Updates automatically whenever a new save is detected by `savewatcher.py`.

---

## Verification & Testing
- Unit tests in `tests/test_day_cycle.py` test day count calculations, phase name assignments, zero/negative/invalid day fallbacks, fractional day counts, and cycle wraparound (10/10 tests pass across test suite).
- Container build and integration verified.

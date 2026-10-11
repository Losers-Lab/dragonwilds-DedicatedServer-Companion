# Phase 3A: Interactive World Map Radar, Crop Accordion & Timezone Synchronization

## 1. Executive Summary
Phase 3A addresses core player UX friction in territorial resource tracking and data comprehension without altering the established dashboard styling or navigation layout:
1. **Interactive 2D World Map & Territorial Radar**: Replaces ambiguous raw engine lists with an intuitive geographical canvas radar plotting all 31 canonical game regions, live chest respawn pins (green = ready to loot, amber = respawning countdown), boss encounter sanctums, and regional weather.
2. **Agriculture Plot Accordion**: Provides interactive collapse/expand visibility into distinct in-world plot instances (UAIDs, plot numbers, sectors, growth status) for all crop species (e.g. Flax, Bittercap, Redberry, Dwellberry, Thorny Roots, and Saplings).
3. **UTC $\to$ Local Timezone Auto-Synchronization**: Converts server engine timestamps (emitted in UTC by Unreal Engine) into the player's local timezone (Eastern Time / ET) across the Event Feed, Server Telemetry, Live World Events, and Respawn countdowns.

---

## 2. Technical Architecture

### 2.1 2D World Map Radar Canvas Engine
- **HTML5 Canvas Visualizer**: Built with high-DPI scaling, smooth pan/zoom transformation matrix, coordinate projection (`screenToWorld`, `worldToScreen`), and zero-idle CPU footprint.
- **Canonical Territorial Grid**: Projects 31 canonical map regions with biome-themed aesthetic palettes (`Desert`, `Forest`, `Highlands`, `Ruins`, `Sanctuary`, `Volcanic`, `Swamp`, `Lake`, `Arcane`).
- **Concentric Radar & Compass**: Subtle radar rings and cardinal direction indicators (`N`, `S`, `E`, `W`) anchor spatial orientation.
- **Travel Roads & Leyline Network**: Connects neighboring territories with dashed pathways representing canonical travel routes across Dragonwilds.
- **Live Entity Pins**:
  - **Loot Chests**: Placed within respective territorial sectors using orbital distribution algorithms. Pins reflect real-time loot status (`🟢 Ready to Loot` vs `⏳ Respawning` with pulsing radar waves).
  - **Boss Arenas**: Highlighted with crimson diamond markers and encounter classifications (Velgar, Kalphite Queen, Titan Gate, Fight Caves, etc.).
  - **Regional Weather**: Displays active weather icons directly above region hubs.
- **Inspector Panel**: Clicking any region or marker updates the detail panel with territory lore, coordinates, biome info, and localized chest countdowns.

### 2.2 Agriculture Plot Breakdown
- Extracted directly from `.sav` binary saves without heuristics.
- Unrolls unique in-world UAID instances per species (e.g., 30 Flax plots, 31 Bittercap plots, 4 Redberry plots).
- Interactive chevron toggle reveals individual plot cards showing plot index, short instance ID, world zone, and active status.

### 2.3 Timezone Normalization
- Server-side log timestamps parsed using explicit `timezone.utc` to prevent naive local datetime drift.
- Client-side helpers (`formatLocalDateTime`, `formatLocalDate`, `parseToLocalDate`) automatically adjust times to the user's browser timezone (EDT/UTC-4).
- Respawns display remaining duration alongside exact local ready time (e.g., *"Ready at 9:45 PM EDT"*).

---

## 3. Host Safety & Universal Save Compatibility
- **Read-Only Guarantee**: Zero file writes or modifications to server files, saves, logs, or configs.
- **Safe Fallbacks**: Handles missing saves, empty logs, and novel custom regions gracefully without runtime exceptions.
- **UI Consistency**: Fully preserves the dark dashboard architecture, CSS structure, and sidebar styling.

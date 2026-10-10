# Phase 2A: Dynamic Region Resolution & Weather Geography

## Overview
Phase 2A refines the world geography and weather representation within the Companion dashboard:
1. **Decoupled Overworld Climate from Player Bases**:
   - The game's internal weather engine uses `"base"` to designate the default global climate profile (Central Ashenfall), while providing regional overrides for biomes such as `"dowdun"` (Dowdun Reach), `"sands"` (Umbral Sands), and `"Scorned Wilderness"`.
   - The label `"base"` is now mapped to `"Central Ashenfall (Overworld)"` to avoid confusion with player-built home bases.
2. **Dynamic Fallback Formatting**:
   - Save files from other servers or custom community configurations may introduce new or custom region names. The system no longer assumes any single hardcoded layout.
   - Any unmapped region identifier is automatically transformed from CamelCase or snake_case into clean, title-cased labels (e.g. `MapRegionWhisperingSwamp` -> `Whispering Swamp`).
3. **Canonical Game Map Region Directory**:
   - 30+ native game regions extracted from `ST_UI_MapRegions` in the server package are now exposed via `GET /api/world/regions`.

## Endpoints Added / Modified
- `GET /api/weather`: Returns day count and weather cards with updated region labels.
- `GET /api/world/regions`: Returns canonical map regions with their respective biomes.
- `GET /status`: Enriched with updated region labels in the `weather` array.

## Verification
- Verified dynamically across both `Hardcore Losers.sav` and `The Losers.sav`.
- Unit tests verify `format_region_name()` against standard keys, `MapRegion*` strings, and arbitrary PascalCase identifiers.

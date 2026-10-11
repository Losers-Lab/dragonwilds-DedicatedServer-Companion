# Phase 4: Dragonwilds Theme & Mobile-First Redesign

## 1. Overview & Objectives
Phase 4 executes a complete aesthetic and architectural overhaul of the **Dragonwilds Dedicated Server Companion** user interface:
1. **Authentic Dragonwilds Aesthetic**: Migrated away from generic dark gaming / neon cyan HUD styling to authentic *RuneScape: Dragonwilds* visual tokens (warm deep charcoal stone, parchment typography, ember gold accents, and RuneScape skill/combat highlights).
2. **Mobile-First Responsiveness**: Replaced the cramped desktop horizontal navbar on mobile with a sticky topbar and a slide-over drawer (`☰` menu) with backdrop blur, $2\times 2$ touch-friendly stat grids, touch gestures for the Ashenfall canvas map, and scrollable responsive tables.
3. **Clean Zero-Abstraction Architecture**: Extracted the monolithic 3,600+ line inline HTML/JS string in `app.py` into standard modular Flask files (`templates/index.html`, `static/style.css`, `static/app.js`). This shrank `app.py` from 3,942 lines to 295 lines without introducing any npm, webpack, or complex framework dependencies.

---

## 2. Dragonwilds Design System & Color Tokens

All design tokens are defined via CSS variables in [`static/style.css`](file:///c:/Users/arham/programs/dragonwilds-DedicatedServer-Companion/static/style.css):

| Token Name | Hex Code | UI Role |
| :--- | :--- | :--- |
| `--bg-deep` | `#221d1a` | Darkest background, modals, code blocks |
| `--bg-root` | `#312a26` | Page body background (deep stone) |
| `--bg-card` | `#3a322d` | Container cards, panels, table headers |
| `--bg-elevated` | `#4a4039` | Hover states, pill badges, inputs, borders |
| `--text-pure` | `#fbf9f2` | Primary headings, active item names |
| `--text-primary` | `#f1ede4` | Main content text |
| `--text-body` | `#e0dbd1` | Table cells, labels, regular text |
| `--text-muted` | `#a29a8d` | Secondary subtitles, timestamps, tags |
| `--gold-core` | `#ebd15f` | Dragonwilds signature ember gold (brand, highlights) |
| `--gold-light` | `#fbe4b0` | Light gold accent for tags and active badges |
| `--gold-deep` | `#dbbd0d` | Deep gold buttons, active borders |
| `--rune-green` | `#84be5b` | Nature, ready loot status, online players |
| `--blood-red` | `#c43a2e` | Combat, danger, boss gates, offline status |
| `--magic-blue` | `#8cc7ef` | Telemetry, coordinates, interactive links |
| `--arcane-purple` | `#dba6cf` | Hardcore player gravestones, sacred relics |

---

## 3. Mobile Navigation & Touch-Ready UX

### 3.1 Sticky Mobile Topbar & Slide-Over Drawer
- On viewports $\le 860\text{px}$, the desktop sidebar is hidden.
- A fixed `mobile-topbar` displays the Dragonwilds emblem, live online player counter, and a `☰` button.
- Clicking `☰` slides open a full-height `mobile-drawer` with backdrop blur, categorized links for all 11 views, and live badge counters (`Respawns`, `Items`, `Bosses`, `Players`).
- Tapping anywhere outside the drawer or selecting any view automatically closes the drawer.

### 3.2 Responsive Layout Adaptations
- **Stat Grids**: Automatically scale from 4 columns on desktop down to a $2\times 2$ grid on mobile for high legibility.
- **Day / Night Solar Dial**: The animated SVG astronomical clock and dynamic daytime shading arc scale down to fit compact mobile viewports without clipping.
- **Ashenfall Radar Map**: Canvas map supports both single-touch dragging and dual-touch pinch-to-zoom on mobile devices.
- **Data Tables**: Encapsulated in horizontal scroll containers with touch-friendly padding and truncation safety.

---

## 4. Modular Flask File Structure

```
dragonwilds-DedicatedServer-Companion/
├── app.py                # 295 lines (Flask routes, API endpoints)
├── templates/
│   └── index.html        # Clean semantic HTML5 layout & view containers
├── static/
│   ├── style.css         # Dragonwilds responsive design system
│   ├── app.js            # Vanilla JS (map canvas, solar dial, live polling)
│   └── ashenfall_world_map_1000.jpg
└── tests/
    └── test_ui.py        # Automated test verification for templates & assets
```

---

## 5. Verification & Automated Test Results
All 48 unit tests pass cleanly:
```bash
docker exec dragonwilds-companion python -m unittest discover -s tests -v
# Ran 48 tests in 0.231s (OK)
```
Live server verification:
- `GET /` -> `200 OK` (Serves `templates/index.html`)
- `GET /static/style.css` -> `200 OK`
- `GET /static/app.js` -> `200 OK`
- `GET /status` -> `200 OK`
- `GET /api/world/regions` -> `200 OK`
- `GET /api/respawns` -> `200 OK`
- `GET /api/farming` -> `200 OK`
- `GET /api/storage/items` -> `200 OK`
- `GET /api/bosses` -> `200 OK`

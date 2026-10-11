// Dragonwilds Dedicated Server Companion - Client Application Logic

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function parseToLocalDate(val) {
  if (!val) return null;
  if (typeof val === 'number') {
    return new Date(val * 1000);
  }
  if (typeof val === 'string') {
    let s = val.trim();
    if (s.endsWith(' UTC')) {
      s = s.replace(' UTC', 'Z').replace(' ', 'T');
      return new Date(s);
    }
    if (s.includes('T') || s.endsWith('Z')) {
      return new Date(s);
    }
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(s)) {
      return new Date(s.replace(' ', 'T') + 'Z');
    }
    return new Date(s);
  }
  return new Date(val);
}

function formatLocalDateTime(val) {
  const d = parseToLocalDate(val);
  if (!d || isNaN(d.getTime())) return String(val || '—');
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' });
}

function formatLocalDate(val) {
  const d = parseToLocalDate(val);
  if (!d || isNaN(d.getTime())) return String(val || '—');
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) + ' ' +
         d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

// ----------------- MOBILE DRAWER NAVIGATION -----------------
function toggleDrawer() {
  const drawer = document.getElementById('mobile-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  if (!drawer || !backdrop) return;
  const isOpen = drawer.classList.contains('open');
  if (isOpen) {
    closeDrawer();
  } else {
    drawer.classList.add('open');
    backdrop.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

function closeDrawer() {
  const drawer = document.getElementById('mobile-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';
}

// Helper to update badge counts on both desktop sidebar and mobile drawer
function updateNavBadge(name, count) {
  const navEl = document.getElementById('nav-' + name + '-count');
  const drawerEl = document.getElementById('drawer-' + name + '-count');
  if (navEl) {
    navEl.innerText = count;
    navEl.style.display = count !== undefined && count !== null ? 'inline' : 'none';
  }
  if (drawerEl) {
    drawerEl.innerText = count;
    drawerEl.style.display = count !== undefined && count !== null ? 'inline' : 'none';
  }
}

// ----------------- TAB SWITCHER -----------------
let currentTab = 'overview';

// State caches
let allEvents = [];
let eventFilter = 'all';
let eventsPerPage = 10;
let eventsPage = 1;

// Log Viewer State
let currentLogFile = 'RSDragonwilds.log';
let currentLogLevel = 'all';
let isLive = true;
let logOffset = 0;
let rawLogLines = [];

function setTab(tab) {
  currentTab = tab;
  try { history.replaceState(null, null, '#' + tab); } catch(e){}

  closeDrawer();

  document.querySelectorAll('.nav-link').forEach(el => {
    if (el.dataset.tab === tab) el.classList.add('active');
    else el.classList.remove('active');
  });

  const title = document.getElementById('page-title');
  const subtitle = document.getElementById('page-subtitle');
  const vOverview = document.getElementById('view-overview');
  const vMap = document.getElementById('view-map');
  const vLogs = document.getElementById('view-logs');
  const vPlayers = document.getElementById('view-players');
  const vBackups = document.getElementById('view-backups');
  const vLeaderboard = document.getElementById('view-leaderboard');
  const vEvents = document.getElementById('view-events');
  const vRespawns = document.getElementById('view-respawns');
  const vFarming = document.getElementById('view-farming');
  const vItems = document.getElementById('view-items');
  const vBosses = document.getElementById('view-bosses');

  if (vOverview) vOverview.style.display = 'none';
  if (vMap) vMap.style.display = 'none';
  if (vLogs) vLogs.style.display = 'none';
  if (vPlayers) vPlayers.style.display = 'none';
  if (vBackups) vBackups.style.display = 'none';
  if (vLeaderboard) vLeaderboard.style.display = 'none';
  if (vEvents) vEvents.style.display = 'none';
  if (vRespawns) vRespawns.style.display = 'none';
  if (vFarming) vFarming.style.display = 'none';
  if (vItems) vItems.style.display = 'none';
  if (vBosses) vBosses.style.display = 'none';

  if (tab === 'overview') {
    if (title) title.innerText = 'Overview';
    if (subtitle) subtitle.innerText = 'Real-time overview of your Dragonwilds server';
    if (vOverview) vOverview.style.display = 'block';
  } else if (tab === 'map') {
    if (title) title.innerText = 'Interactive World Map';
    if (subtitle) subtitle.innerText = 'Territorial radar plotting canonical regions, chest respawn timers & boss gates';
    if (vMap) vMap.style.display = 'block';
    initWorldMap();
  } else if (tab === 'respawns') {
    if (title) title.innerText = 'Respawn Tracker';
    if (subtitle) subtitle.innerText = 'Active timers for dungeon chests, fishing nets, world bosses & high-tier ores';
    if (vRespawns) vRespawns.style.display = 'block';
    loadRespawns();
  } else if (tab === 'farming') {
    if (title) title.innerText = 'Farming & Agriculture';
    if (subtitle) subtitle.innerText = 'Tracking placed hydration, composters, and growing agriculture plots';
    if (vFarming) vFarming.style.display = 'block';
    loadFarming();
  } else if (tab === 'items') {
    if (title) title.innerText = 'Storage & Item Tracker';
    if (subtitle) subtitle.innerText = 'Search items across storage containers, inspect server totals & track unit locations';
    if (vItems) vItems.style.display = 'block';
    loadStorageTracker();
  } else if (tab === 'bosses') {
    if (title) title.innerText = 'Boss Arenas & Events';
    if (subtitle) subtitle.innerText = 'Objective encounter gates, boss arenas & live world raid telemetry';
    if (vBosses) vBosses.style.display = 'block';
    loadBosses();
    loadLiveWorldEvents();
  } else if (tab === 'logs') {
    if (title) title.innerText = 'Server Logs';
    if (subtitle) subtitle.innerText = 'Stream, filter and search RSDragonwilds server logs';
    if (vLogs) vLogs.style.display = 'block';
    fetchLogFiles();
    fetchLogs();
  } else if (tab === 'players') {
    if (title) title.innerText = 'Players';
    if (subtitle) subtitle.innerText = 'Active players & all-time registered server roster';
    if (vPlayers) vPlayers.style.display = 'block';
    loadRoster();
  } else if (tab === 'backups') {
    if (title) title.innerText = 'Save Backups';
    if (subtitle) subtitle.innerText = 'Download server save files for local backups or editing';
    if (vBackups) vBackups.style.display = 'block';
    loadSaveFiles();
  } else if (tab === 'leaderboard') {
    if (title) title.innerText = 'Leaderboard';
    if (subtitle) subtitle.innerText = 'Player playtime rankings & sessions';
    if (vLeaderboard) vLeaderboard.style.display = 'block';
  } else if (tab === 'events') {
    if (title) title.innerText = 'Events';
    if (subtitle) subtitle.innerText = 'Server activity & event timeline';
    if (vEvents) vEvents.style.display = 'block';
  }
}

// ----------------- OVERVIEW STATUS, WEATHER & EVENTS -----------------
async function loadStatus() {
  try {
    const res = await fetch('/status');
    const s = await res.json();

    const statPlayers = document.getElementById('stat-players');
    if (statPlayers) statPlayers.innerText = `${s.players_online} / ${s.max_players}`;
    
    updateNavBadge('players', s.players_online);

    const mobileDot = document.getElementById('mobile-server-dot');
    const mobilePlayers = document.getElementById('mobile-server-players');
    if (mobileDot) {
      mobileDot.className = s.status === 'online' ? 'status-dot' : 'status-dot offline';
    }
    if (mobilePlayers) {
      mobilePlayers.innerText = `${s.players_online}/${s.max_players}`;
    }
    
    const dayEl = document.getElementById('stat-day');
    if (dayEl) dayEl.innerText = s.day_count ? `Day ${s.day_count}` : 'Day --';
    const weatherDayEl = document.getElementById('weather-day-badge');
    if (weatherDayEl) weatherDayEl.innerText = s.day_count ? `Day ${s.day_count}` : 'Day --';

    const worldEl = document.getElementById('world');
    if (worldEl) worldEl.innerText = s.world || 'Unknown';
    const uptimeEl = document.getElementById('uptime');
    if (uptimeEl) uptimeEl.innerText = s.uptime || 'Unknown';
    const saveEl = document.getElementById('save');
    if (saveEl) saveEl.innerText = s.last_save || 'Unknown';
    const cpuEl = document.getElementById('cpu');
    if (cpuEl) cpuEl.innerText = s.cpu || 'N/A';
    const ramEl = document.getElementById('ram');
    if (ramEl) ramEl.innerText = s.memory || 'N/A';
    const verEl = document.getElementById('version');
    if (verEl) verEl.innerText = s.version || 'Unknown';
    const updEl = document.getElementById('updated-time');
    if (updEl) updEl.innerText = new Date().toLocaleTimeString();

    const dot = document.getElementById('server-dot');
    const label = document.getElementById('server-status-label');
    const ind = document.getElementById('server-indicator');

    if (dot && label && ind) {
      if (s.status === 'online') {
        dot.className = 'status-dot';
        ind.className = 'status-indicator';
        label.innerText = 'Server Online';
      } else {
        dot.className = 'status-dot offline';
        ind.className = 'status-indicator offline';
        label.innerText = 'Server Offline';
      }
    }

    // Update transparency data source badges with last save timestamp
    const saveTimeText = s.last_save || 'recently';
    const badgeStatDay = document.getElementById('badge-stat-day');
    if (badgeStatDay) {
      badgeStatDay.innerText = `💾 Saved (${saveTimeText})`;
      badgeStatDay.title = `Extracted from world save snapshot (${saveTimeText})`;
    }
    const badgeWorld = document.getElementById('badge-world');
    if (badgeWorld) {
      badgeWorld.innerText = `💾 Saved (${saveTimeText})`;
      badgeWorld.title = `Active save slot from disk snapshot (${saveTimeText})`;
    }
    const badgeDialSource = document.getElementById('badge-dial-source');
    if (badgeDialSource) {
      badgeDialSource.innerText = `💾 Saved (${saveTimeText})`;
      badgeDialSource.title = `Time progression synchronized from save snapshot (${saveTimeText})`;
    }
    const badgeWeatherSource = document.getElementById('badge-weather-source');
    if (badgeWeatherSource) {
      badgeWeatherSource.innerText = `💾 Saved (${saveTimeText})`;
      badgeWeatherSource.title = `Climate forecast extracted from world save (${saveTimeText})`;
    }

    // Render In-Game Day/Night Solar Dial
    renderDayNightDial(s.day_cycle, s.day_count, s.last_save);

    // Weather forecast
    renderWeather(s.weather);

    // Events caching
    allEvents = s.events || [];
    renderEvents();

    // Players list view
    const pContainer = document.getElementById('current-players-list');
    if (pContainer) {
      pContainer.innerHTML = '';
      const details = s.players_detail || (s.players || []).map(p => ({ name: p, character_name: null }));
      if (!details || details.length === 0) {
        pContainer.innerHTML = '<div style="color:var(--text-muted); padding:16px 0;">No players currently connected.</div>';
      } else {
        details.forEach(p => {
          const charTitle = p.character_name 
            ? `<span style="color:var(--gold-core); font-weight:bold;">${escapeHtml(p.character_name)}</span> <span style="font-weight:normal; color:var(--text-muted); font-size:13px;">(${escapeHtml(p.name)})</span>` 
            : `<span style="font-weight:bold; color:var(--text-pure);">${escapeHtml(p.name)}</span>`;
          const initial = (p.character_name || p.name || '?')[0].toUpperCase();
          const div = document.createElement('div');
          div.className = 'player-row';
          div.innerHTML = `
            <div class="player-left">
              <div class="avatar">${escapeHtml(initial)}</div>
              <div>
                <div>${charTitle}</div>
                <div style="font-size:12px; color:var(--text-muted);">Connected to ${escapeHtml(s.world||'World')}</div>
              </div>
            </div>
            <div class="badge-online">Online</div>
          `;
          pContainer.appendChild(div);
        });
      }
    }

  } catch (err) {
    console.error('Status fetch error:', err);
  }
}

function renderDayNightDial(cycle, dayCount, lastSave) {
  if (!cycle) return;
  const needleGroup = document.getElementById('dial-needle-group');
  const phaseIcon = document.getElementById('dial-phase-icon');
  const phaseLabel = document.getElementById('dial-phase-label');
  const progressBar = document.getElementById('dial-progress-bar');
  const progressText = document.getElementById('dial-progress-text');
  const timeCountdown = document.getElementById('dial-time-countdown');

  // Needle angle rotation (0 to 360 deg)
  const angle = typeof cycle.needle_angle_deg === 'number' ? cycle.needle_angle_deg : 180;
  if (needleGroup) {
    needleGroup.style.transform = `rotate(${angle}deg)`;
  }

  // Dynamic Day-Passed SVG Clipping Arc
  // Day starts at top (0° / 12 o'clock) and sweeps clockwise through 90° (3 o'clock) to 240° (8 o'clock)
  const clipPathEl = document.getElementById('path-day-passed');
  if (clipPathEl) {
    const cx = 50, cy = 50, r = 46;
    const startDeg = 0.0;
    const startRad = (startDeg - 90) * Math.PI / 180;
    const x0 = cx + r * Math.cos(startRad);
    const y0 = cy + r * Math.sin(startRad);

    // Current needle clamped to day arc (0° to 240°)
    let delta = angle;
    if (delta > 240) {
      // It's night time: the entire daytime portion has passed!
      delta = 240;
    }

    if (delta <= 0.5) {
      clipPathEl.setAttribute('d', 'M 50,50 Z');
    } else {
      const endDeg = (startDeg + delta) % 360;
      const endRad = (endDeg - 90) * Math.PI / 180;
      const x1 = cx + r * Math.cos(endRad);
      const y1 = cy + r * Math.sin(endRad);
      const largeArc = delta > 180 ? 1 : 0;
      clipPathEl.setAttribute('d', `M ${cx},${cy} L ${x0.toFixed(2)},${y0.toFixed(2)} A ${r},${r} 0 ${largeArc},1 ${x1.toFixed(2)},${y1.toFixed(2)} Z`);
    }
  }

  // Phase Title & Icon
  const dayStr = dayCount ? `Day ${dayCount}` : (cycle.day_count ? `Day ${cycle.day_count}` : 'Day --');
  if (phaseIcon) phaseIcon.innerText = cycle.phase_icon || '☀️';
  if (phaseLabel) phaseLabel.innerText = `${cycle.phase || 'Daytime'} (${dayStr})`;

  // Progress Bar & Percentage
  const pct = Math.min(100, Math.max(0, cycle.progress_percent || 0));
  if (progressBar) progressBar.style.width = `${pct}%`;
  if (progressText) progressText.innerText = `${pct}%`;

  // Elapsed Seconds in Day
  if (timeCountdown) {
    const elapsedSec = Math.floor(cycle.seconds_in_day || 0);
    const totalSec = cycle.cycle_duration_seconds || 840;
    const m = Math.floor(elapsedSec / 60);
    const s = elapsedSec % 60;
    const totM = Math.floor(totalSec / 60);
    const totS = totalSec % 60;
    const pad = (n) => n < 10 ? '0' + n : n;
    timeCountdown.innerText = `${m}m ${pad(s)}s / ${totM}m ${pad(totS)}s in day cycle`;
  }
}

function renderWeather(list) {
  const grid = document.getElementById('weather-grid');
  if (!grid) return;
  if (!list || list.length === 0) {
    grid.innerHTML = '<div style="color:var(--text-muted); grid-column:1/-1; padding:12px 0;">No weather forecast available in save file.</div>';
    return;
  }
  grid.innerHTML = list.map(w => `
    <div class="weather-biome-card">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
        <span style="font-size:26px;">${w.icon || '🌤️'}</span>
        <span style="font-size:11px; font-weight:600; padding:2px 8px; border-radius:12px; background:var(--bg-elevated); color:${w.remaining_seconds > 0 ? 'var(--magic-blue)' : 'var(--text-muted)'};">
          ${escapeHtml(w.remaining_text || 'Active')}
        </span>
      </div>
      <div style="font-size:12.5px; font-weight:500; color:var(--text-muted); margin-bottom:2px;">${escapeHtml(w.region || w.raw_region)}</div>
      <div style="font-size:15px; font-weight:bold; color:var(--text-pure);">${escapeHtml(w.type)}</div>
    </div>
  `).join('');
}

// ----------------- ALL-TIME ROSTER -----------------
let allRoster = [];
let rosterFilter = 'all';

async function loadRoster() {
  try {
    const res = await fetch('/api/roster');
    allRoster = await res.json();
    renderRoster();
  } catch(e) {}
}

function setRosterFilter(filter, btn) {
  rosterFilter = filter;
  btn.parentElement.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderRoster();
}

function renderRoster() {
  const body = document.getElementById('roster-table-body');
  if (!body) return;
  const q = (document.getElementById('roster-search-input')?.value || '').toLowerCase().trim();

  let filtered = allRoster.filter(p => {
    if (rosterFilter === 'admins' && !p.is_admin) return false;
    if (rosterFilter === 'online' && !p.online) return false;
    if (q) {
      const matchName = (p.name || '').toLowerCase().includes(q);
      const matchChar = (p.character_name || '').toLowerCase().includes(q);
      const matchSteam = (p.steam_id || '').includes(q);
      const matchEos = (p.user_id || '').toLowerCase().includes(q);
      return matchName || matchChar || matchSteam || matchEos;
    }
    return true;
  });

  if (filtered.length === 0) {
    body.innerHTML = '<tr><td colspan="7" style="color:var(--text-muted); text-align:center; padding:18px;">No matching players found in server roster.</td></tr>';
    return;
  }

  body.innerHTML = filtered.map(p => {
    let roleBadge = '<span style="background:var(--bg-elevated); color:var(--text-muted); padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">Member</span>';
    if (p.is_owner) {
      roleBadge = '<span style="background:#5c4314; color:var(--gold-light); padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">👑 Owner</span>';
    } else if (p.is_admin) {
      roleBadge = '<span style="background:#4a243c; color:var(--arcane-purple); padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">🛡️ Admin</span>';
    }

    const charCell = p.character_name
      ? `<strong style="color:var(--gold-core);">${escapeHtml(p.character_name)}</strong>`
      : '<span style="color:var(--text-muted);">—</span>';

    const statusBadge = p.online 
      ? '<span style="background:#22401f; color:var(--rune-green); padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">🟢 Online</span>'
      : '<span style="background:var(--bg-elevated); color:var(--text-muted); padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">Offline</span>';

    const steamCell = p.steam_id
      ? `<a href="https://steamcommunity.com/profiles/${encodeURIComponent(p.steam_id)}" target="_blank" style="color:var(--magic-blue); text-decoration:none; font-family:monospace; font-size:12px;">${escapeHtml(p.steam_id)} ↗</a>`
      : '<span style="color:var(--text-muted); font-size:12px;">Unlinked</span>';

    const bannedBadge = p.is_banned
      ? '<span style="background:#521c17; color:#fca5a5; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">Banned</span>'
      : '<span style="color:var(--rune-green); font-size:12px;">Active</span>';

    const shortEos = p.user_id ? `${p.user_id.slice(0, 8)}...${p.user_id.slice(-6)}` : 'N/A';

    return `
      <tr>
        <td><strong>${escapeHtml(p.name)}</strong></td>
        <td>${charCell}</td>
        <td>${roleBadge}</td>
        <td>${statusBadge}</td>
        <td>${steamCell}</td>
        <td><code style="color:var(--text-muted); font-size:12px;" title="${escapeHtml(p.user_id)}">${escapeHtml(shortEos)}</code></td>
        <td>${bannedBadge}</td>
      </tr>
    `;
  }).join('');
}

// ----------------- SAVE FILE BACKUPS -----------------
let allSaveFiles = [];

async function loadSaveFiles() {
  try {
    const res = await fetch('/api/save-files');
    allSaveFiles = await res.json();
    const body = document.getElementById('save-files-table-body');
    updateNavBadge('backups', allSaveFiles.length);

    if (!body) return;

    if (!allSaveFiles || allSaveFiles.length === 0) {
      body.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted); text-align:center; padding:18px;">No save files found in server save directory.</td></tr>';
      return;
    }

    body.innerHTML = allSaveFiles.map(f => {
      const typeBadge = f.is_backup
        ? '<span style="background:var(--bg-elevated); color:var(--text-muted); padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">Backup (.sav.backup)</span>'
        : '<span style="background:#22401f; color:var(--rune-green); padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">Active World (.sav)</span>';

      return `
        <tr>
          <td><strong style="font-family:monospace; color:var(--text-pure);">${escapeHtml(f.filename)}</strong></td>
          <td>${typeBadge}</td>
          <td>${escapeHtml(f.size_str)}</td>
          <td style="color:var(--text-muted); font-size:13px;">${escapeHtml(f.modified_text)}</td>
          <td style="text-align:right;">
            <a href="/api/save-files/download/${encodeURIComponent(f.filename)}" class="pg-btn" style="text-decoration:none; display:inline-block; padding:4px 12px; background:var(--gold-deep); color:#1c1714; border-color:var(--gold-core); font-weight:bold;">
              📥 Download
            </a>
          </td>
        </tr>
      `;
    }).join('');
  } catch(e) {}
}

function setEventFilter(cat, btn) {
  eventFilter = cat;
  eventsPage = 1;
  btn.parentElement.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderEvents();
}

function changeEventsPerPage(val) {
  eventsPerPage = parseInt(val);
  eventsPage = 1;
  renderEvents();
}

function renderEvents() {
  const container = document.getElementById('events-list-container');
  const fullContainer = document.getElementById('full-events-list');

  let filtered = allEvents;
  if (eventFilter !== 'all') {
    filtered = allEvents.filter(e => e.category === eventFilter);
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / eventsPerPage));
  eventsPage = Math.min(eventsPage, totalPages);

  const start = (eventsPage - 1) * eventsPerPage;
  const pageItems = filtered.slice(start, start + eventsPerPage);

  const renderHtml = (items) => {
    if (items.length === 0) {
      return '<div style="color:var(--text-muted); padding:18px 0;">No events match filter.</div>';
    }
    return items.map(e => `
      <div class="event-item">
        <span class="event-time" title="${escapeHtml(formatLocalDate(e.epoch || e.iso || e.full_time || e.timestamp))}">[${escapeHtml(formatLocalDateTime(e.epoch || e.iso || e.timestamp))}]</span>
        <span class="event-tag ${e.category}">[${e.category}]</span>
        <span class="event-msg">${escapeHtml(e.message)}</span>
      </div>
    `).join('');
  };

  if (container) container.innerHTML = renderHtml(pageItems);
  if (fullContainer) fullContainer.innerHTML = renderHtml(filtered);

  // Update pagination controls
  const pgInfo = document.getElementById('pg-info');
  const pgPrev = document.getElementById('pg-prev');
  const pgNext = document.getElementById('pg-next');
  if (pgInfo) pgInfo.innerText = `Page ${eventsPage} of ${totalPages}`;
  if (pgPrev) pgPrev.disabled = (eventsPage <= 1);
  if (pgNext) pgNext.disabled = (eventsPage >= totalPages);
}

function prevEventsPage() {
  if (eventsPage > 1) {
    eventsPage--;
    renderEvents();
  }
}

function nextEventsPage() {
  eventsPage++;
  renderEvents();
}

// ----------------- LEADERBOARD -----------------
async function loadLeaderboard() {
  try {
    const res = await fetch('/leaderboard');
    const rows = await res.json();
    const body = document.getElementById('leaderboard-body');
    const fullBody = document.getElementById('full-leaderboard-body');

    const renderRows = (r) => {
      if (!r || r.length === 0) {
        return '<tr><td colspan="5" style="color:var(--text-muted); text-align:center; padding:18px;">No completed sessions yet</td></tr>';
      }
      return r.map((row, idx) => `
        <tr>
          <td>${idx + 1}</td>
          <td><strong>${escapeHtml(row.player)}</strong></td>
          <td>${escapeHtml(row.playtime)}</td>
          <td>${row.sessions}</td>
          <td>${escapeHtml(row.longest_session)}</td>
        </tr>
      `).join('');
    };

    if (body) body.innerHTML = renderRows(rows);
    if (fullBody) fullBody.innerHTML = renderRows(rows);
  } catch(e) {}
}

// ----------------- SERVER LOGS -----------------
async function fetchLogFiles() {
  try {
    const res = await fetch('/api/log-files');
    const files = await res.json();
    const sel = document.getElementById('log-file-select');
    if (!sel) return;
    sel.innerHTML = '';
    files.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.name;
      opt.innerText = `${f.name} (${f.size})${f.live ? ' - live' : ''}`;
      if (f.name === currentLogFile) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch(e) {}
}

function switchLogFile(filename) {
  currentLogFile = filename;
  logOffset = 0;
  fetchLogs();
}

function setLogLevel(lvl, btn) {
  currentLogLevel = lvl;
  btn.parentElement.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  fetchLogs();
}

function handleLogSearch() {
  fetchLogs();
}

function clearDateFilter() {
  const fromEl = document.getElementById('log-from-date');
  const toEl = document.getElementById('log-to-date');
  if (fromEl) fromEl.value = '';
  if (toEl) toEl.value = '';
  fetchLogs();
}

function toggleLive() {
  isLive = !isLive;
  const btn = document.getElementById('btn-live-toggle');
  const label = document.getElementById('live-label');
  if (isLive) {
    if (btn) btn.className = 'btn-live';
    if (label) label.innerText = 'Live: on';
  } else {
    if (btn) btn.className = 'btn-live off';
    if (label) label.innerText = 'Live: off';
  }
}

function loadOlderLogs() {
  logOffset += 200;
  fetchLogs(true);
}

async function fetchLogs(isOlderAppend = false) {
  try {
    const q = (document.getElementById('log-search-input')?.value || '').trim();
    const fromD = document.getElementById('log-from-date')?.value || '';
    const toD = document.getElementById('log-to-date')?.value || '';

    const url = `/api/logs?file=${encodeURIComponent(currentLogFile)}&lines=250&offset=${logOffset}&level=${currentLogLevel}&search=${encodeURIComponent(q)}&from_date=${fromD}&to_date=${toD}`;
    const res = await fetch(url);
    const data = await res.json();

    if (data.lines) {
      rawLogLines = data.lines;
      renderLogTerminal(!isOlderAppend);
    }
  } catch(e) {}
}

function renderLogTerminal(autoScrollToEnd = true) {
  const term = document.getElementById('log-terminal');
  if (!term) return;
  if (rawLogLines.length === 0) {
    term.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">No matching log entries found.</div>';
    return;
  }

  const html = rawLogLines.map(line => {
    let ts = '';
    let rest = line;

    const tsMatch = line.match(/^(\[\d{4}[\.\-]\d{2}[\.\-]\d{2}[^\]]+\](?:\[\s*\d+\])?)\s*(.*)$/);
    if (tsMatch) {
      ts = tsMatch[1];
      rest = tsMatch[2];
    }

    let channel = '';
    let levelClass = '';
    let body = rest;

    const chMatch = rest.match(/^([A-Za-z0-9_]+:)\s*(.*)$/);
    if (chMatch) {
      channel = chMatch[1];
      body = chMatch[2];
    }

    if (/error:/i.test(body) || /fatal:/i.test(body) || /exception:/i.test(body)) {
      levelClass = 'log-level-error';
    } else if (/warning:/i.test(body)) {
      levelClass = 'log-level-warn';
    } else if (/verbose:/i.test(body)) {
      levelClass = 'log-level-verb';
    } else if (/display:/i.test(body)) {
      levelClass = 'log-level-disp';
    }

    const escTs = ts.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const escCh = channel.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const escBody = body.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

    return `<div class="log-line"><span class="log-ts">${escTs}</span> <span class="log-channel">${escCh}</span> <span class="${levelClass}">${escBody}</span></div>`;
  }).join('');

  term.innerHTML = html;

  if (autoScrollToEnd && isLive) {
    term.scrollTop = term.scrollHeight;
  }
}

// ----------------- RESPAWNS TRACKER -----------------
let allRespawns = [];
let respawnCategory = 'all';

async function loadRespawns() {
  try {
    const q = (document.getElementById('respawn-search-input') ? document.getElementById('respawn-search-input').value.trim() : '');
    const url = `/api/respawns?category=${encodeURIComponent(respawnCategory)}&search=${encodeURIComponent(q)}`;
    const res = await fetch(url);
    allRespawns = await res.json();
    renderRespawns();

    const respawningCount = allRespawns.filter(r => !r.is_ready).length;
    const countDisplay = respawningCount > 0 ? respawningCount : allRespawns.length;
    updateNavBadge('respawns', countDisplay);
  } catch(e) {}
}

function setRespawnCategory(cat, btn) {
  respawnCategory = cat;
  if (btn) {
    document.querySelectorAll('#respawn-pills .pill-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  loadRespawns();
}

function filterRespawnsLive() {
  renderRespawns();
}

function renderRespawns() {
  const body = document.getElementById('respawns-table-body');
  if (!body) return;

  const q = (document.getElementById('respawn-search-input') ? document.getElementById('respawn-search-input').value.toLowerCase().trim() : '');
  const filtered = allRespawns.filter(r => {
    if (respawnCategory !== 'all' && r.category !== respawnCategory) return false;
    if (q) {
      const matchName = (r.name || '').toLowerCase().includes(q);
      const matchId = (r.id || '').toLowerCase().includes(q);
      const matchCat = (r.category || '').toLowerCase().includes(q);
      return matchName || matchId || matchCat;
    }
    return true;
  });

  if (filtered.length === 0) {
    body.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted); text-align:center; padding:24px;">No matching respawns found.</td></tr>';
    return;
  }

  body.innerHTML = filtered.map(r => {
    const statusBadge = r.is_ready
      ? '<span style="background:#22401f; color:var(--rune-green); padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">🟢 Ready to Loot</span>'
      : '<span style="background:#5c4314; color:var(--gold-light); padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">⏳ Respawning</span>';

    const sourceBadge = r.source === 'live_log'
      ? '<span class="data-source-badge live" title="Direct telemetry from server logs">⚡ Live Telemetry</span>'
      : '<span class="data-source-badge saved" title="Extracted from server save game file">💾 Save File</span>';

    const remainingColor = r.is_ready ? 'var(--rune-green)' : 'var(--gold-core)';

    return `
      <tr>
        <td style="padding:12px 14px;">${statusBadge}</td>
        <td style="padding:12px 14px;">
          <div style="font-weight:600; color:var(--text-pure); font-size:14px; display:flex; align-items:center; gap:8px;">
            <span>${escapeHtml(r.name)}</span>
            ${r.zone ? `<span style="font-size:10.5px; background:var(--bg-elevated); color:var(--magic-blue); padding:1px 6px; border-radius:4px; font-weight:normal;">${escapeHtml(r.zone)}</span>` : ''}
            <button onclick="switchTabToMapMarker('${escapeHtml(r.id)}')" style="background:transparent; border:1px solid var(--magic-blue); color:var(--magic-blue); font-size:10px; padding:1px 6px; border-radius:4px; cursor:pointer;" title="View location on World Map">📍 Map</button>
          </div>
          <div style="font-family:monospace; font-size:11.5px; color:var(--text-muted); margin-top:2px;">${escapeHtml(r.id)}</div>
        </td>
        <td style="padding:12px 14px; color:var(--text-body); font-size:13px;">${escapeHtml(r.category)}</td>
        <td style="padding:12px 14px; color:var(--text-muted); font-size:13px;">${escapeHtml(r.duration_formatted || '—')}</td>
        <td style="padding:12px 14px;">
          <strong style="color:${remainingColor}; font-size:13.5px;">${escapeHtml(r.remaining_formatted)}</strong>
          ${!r.is_ready && (r.respawn_epoch || r.respawn_time) ? `<div style="color:var(--text-muted); font-size:11px;" title="${escapeHtml(formatLocalDate(r.respawn_epoch || r.respawn_time))}">Ready at ${escapeHtml(formatLocalDateTime(r.respawn_epoch || r.respawn_time))}</div>` : ''}
        </td>
        <td style="padding:12px 14px;">${sourceBadge}</td>
      </tr>
    `;
  }).join('');
}

// ----------------- AGRICULTURE & FARMING -----------------
let farmingData = null;

async function loadFarming() {
  try {
    const res = await fetch('/api/farming');
    farmingData = await res.json();
    renderFarming();
  } catch(e) {}
}

function renderFarming() {
  if (!farmingData) return;
  const s = farmingData.summary || {};
  const elBarrels = document.getElementById('farm-stat-barrels');
  const elRain = document.getElementById('farm-stat-rain');
  const elCompost = document.getElementById('farm-stat-composters');
  const elTrees = document.getElementById('farm-stat-trees');
  const elCrops = document.getElementById('farm-stat-crops');

  if (elBarrels) elBarrels.innerText = s.total_water_barrels || 0;
  if (elRain) elRain.innerText = s.total_rain_catchers || 0;
  if (elCompost) elCompost.innerText = s.total_composters || 0;
  if (elTrees) elTrees.innerText = (s.total_growing_trees || 0) + (s.total_saplings || 0);
  if (elCrops) elCrops.innerText = s.total_crops || 0;

  // 1. Render Active In-World Crops & Herbs with Collapsible Plot Accordion
  const cropsBody = document.getElementById('crops-table-body');
  if (cropsBody) {
    const crops = farmingData.crops || [];
    if (crops.length === 0) {
      cropsBody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted); text-align:center; padding:20px;">No wild or planted crop instances found in active save file.</td></tr>';
    } else {
      cropsBody.innerHTML = crops.map((c, cIdx) => {
        const plots = c.plots || [];
        const hasPlots = plots.length > 0;
        const accordionId = `crop-plots-${cIdx}`;

        const plotsHtml = hasPlots ? `
          <tr id="${accordionId}" style="display:none; background:var(--bg-deep); border-bottom:1px solid var(--bg-card);">
            <td colspan="4" style="padding:14px 18px;">
              <div style="font-size:12px; font-weight:600; color:var(--magic-blue); margin-bottom:8px; text-transform:uppercase; letter-spacing:0.5px;">
                Distinct In-World Plot Instances (${plots.length} unique locations in save)
              </div>
              <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:8px;">
                ${plots.map(p => `
                  <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:8px 10px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <div style="font-weight:600; color:var(--text-pure); font-size:12px;">Plot #${p.plot_number} (${escapeHtml(p.zone)})</div>
                      <div style="font-family:monospace; font-size:10.5px; color:var(--text-muted);" title="${escapeHtml(p.instance_id)}">...${escapeHtml(p.short_id.slice(-14))}</div>
                    </div>
                    <span style="background:#22401f; color:var(--rune-green); padding:2px 6px; border-radius:4px; font-size:10px; font-weight:600;">
                      ${escapeHtml(p.status)}
                    </span>
                  </div>
                `).join('')}
              </div>
            </td>
          </tr>
        ` : '';

        return `
          <tr style="cursor:pointer;" onclick="toggleCropAccordion('${accordionId}', this)">
            <td style="padding:12px 14px; font-weight:600; color:var(--text-pure); display:flex; align-items:center; gap:8px;">
              <span id="chevron-${accordionId}" style="color:var(--gold-core); font-size:12px; transition:transform 0.2s;">▶</span>
              <span>${escapeHtml(c.name)}</span>
            </td>
            <td style="padding:12px 14px; color:var(--text-muted); font-size:13px;">${escapeHtml(c.category)}</td>
            <td style="padding:12px 14px; font-weight:bold; color:var(--rune-green);">
              ${c.count || 0}
              ${hasPlots ? `<span style="font-size:11px; font-weight:normal; color:var(--text-muted); margin-left:4px;">(${plots.length} plots)</span>` : ''}
            </td>
            <td style="padding:12px 14px;">
              <span style="background:#22401f; color:var(--rune-green); padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">
                ${escapeHtml(c.status || 'Active')}
              </span>
            </td>
          </tr>
          ${plotsHtml}
        `;
      }).join('');
    }
  }

  // 2. Render Placed Farming Infrastructure & Arboriculture
  const tbody = document.getElementById('farming-table-body');
  if (!tbody) return;

  const structures = farmingData.structures || [];
  const growing = farmingData.growing_trees || [];
  const allEntries = [...structures, ...growing];

  if (allEntries.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted); text-align:center; padding:20px;">No placed agriculture structures or planted saplings detected in current save file.</td></tr>';
    return;
  }

  tbody.innerHTML = allEntries.map(item => `
    <tr>
      <td style="padding:12px 14px; font-weight:600; color:var(--text-pure);">${escapeHtml(item.name)}</td>
      <td style="padding:12px 14px; color:var(--text-muted); font-size:13px;">${escapeHtml(item.type || item.stage_tracking || item.category || 'Agriculture')}</td>
      <td style="padding:12px 14px; font-weight:bold; color:var(--magic-blue);">${item.count || 0}</td>
      <td style="padding:12px 14px;">
        <span style="background:#22401f; color:var(--rune-green); padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">
          ${escapeHtml(item.status || 'Active')}
        </span>
      </td>
    </tr>
  `).join('');
}

function toggleCropAccordion(accordionId, trEl) {
  const targetTr = document.getElementById(accordionId);
  const chevron = document.getElementById(`chevron-${accordionId}`);
  if (!targetTr) return;

  if (targetTr.style.display === 'none' || !targetTr.style.display) {
    targetTr.style.display = 'table-row';
    if (chevron) chevron.style.transform = 'rotate(90deg)';
  } else {
    targetTr.style.display = 'none';
    if (chevron) chevron.style.transform = 'rotate(0deg)';
  }
}

// ----------------- STORAGE & STORED ITEM TRACKER -----------------
let storageData = null;
let storageUnitsData = [];
let storageSearchTimeout = null;
let currentStorageTab = 'items';

function switchStorageTab(tab) {
  currentStorageTab = tab;
  const btnItems = document.getElementById('btn-tab-stored-items');
  const btnConts = document.getElementById('btn-tab-containers');
  const panelItems = document.getElementById('storage-panel-items');
  const panelConts = document.getElementById('storage-panel-containers');

  if (tab === 'items') {
    if (btnItems) btnItems.classList.add('active');
    if (btnConts) btnConts.classList.remove('active');
    if (panelItems) panelItems.style.display = 'block';
    if (panelConts) panelConts.style.display = 'none';
  } else {
    if (btnConts) btnConts.classList.add('active');
    if (btnItems) btnItems.classList.remove('active');
    if (panelConts) panelConts.style.display = 'block';
    if (panelItems) panelItems.style.display = 'none';
  }
}

async function loadStorageTracker() {
  await searchStorageLive();
  await loadStorageUnits();
}

function searchStorageLive() {
  clearTimeout(storageSearchTimeout);
  storageSearchTimeout = setTimeout(async () => {
    try {
      const q = (document.getElementById('items-search-input')?.value || '').trim();
      const saveFile = document.getElementById('storage-save-select')?.value || '';
      const params = new URLSearchParams();
      if (q) params.set('search', q);
      if (saveFile) params.set('save', saveFile);

      const res = await fetch(`/api/storage/items?${params.toString()}`);
      storageData = await res.json();
      renderStoredItems();

      if (storageData.summary) {
        const total = storageData.summary.total_stored_items || 0;
        const totalFormatted = total > 1000 ? `${(total/1000).toFixed(1)}k` : total;
        updateNavBadge('items', totalFormatted);
      }
    } catch(e) {}
  }, 200);
}

async function loadStorageUnits() {
  try {
    const saveFile = document.getElementById('storage-save-select')?.value || '';
    const url = saveFile ? `/api/storage/units?save=${encodeURIComponent(saveFile)}` : '/api/storage/units';
    const res = await fetch(url);
    storageUnitsData = await res.json();
    renderStorageUnits();
  } catch(e) {}
}

function renderStoredItems() {
  const tbody = document.getElementById('items-table-body');
  if (!tbody || !storageData) return;

  const summary = storageData.summary || {};
  const unitsEl = document.getElementById('storage-stat-units');
  const itemsEl = document.getElementById('storage-stat-items');
  const typesEl = document.getElementById('storage-stat-types');
  if (unitsEl) unitsEl.innerText = summary.total_containers?.toLocaleString() || '0';
  if (itemsEl) itemsEl.innerText = summary.total_stored_items?.toLocaleString() || '0';
  if (typesEl) typesEl.innerText = summary.unique_items_count?.toLocaleString() || '0';

  const items = storageData.items || [];
  if (items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted); text-align:center; padding:24px;">No stored items match your query.</td></tr>';
    return;
  }

  const itemsToShow = items.slice(0, 150);
  tbody.innerHTML = itemsToShow.map(it => {
    const conts = it.containers || [];
    const shownConts = conts.slice(0, 4);
    const badgesHtml = shownConts.map(c => {
      const ownerPrefix = c.owner && c.owner !== 'World / Unowned' ? `<strong>${escapeHtml(c.owner)}:</strong> ` : '';
      return `<span style="display:inline-block; margin:2px 4px 2px 0; background:var(--bg-elevated); border:1px solid rgba(235,209,95,0.15); color:var(--text-body); padding:3px 8px; border-radius:6px; font-size:11.5px;">
        ${ownerPrefix}${escapeHtml(c.container_name)} <span style="color:var(--magic-blue); font-weight:bold;">(x${c.count})</span>
      </span>`;
    }).join('');

    const moreHtml = conts.length > 4 
      ? `<span style="font-size:11px; color:var(--text-muted); margin-left:4px;">+${conts.length - 4} more units</span>` 
      : '';

    const itemName = it.name || it.item_id;
    const itemSub = (it.raw_id && it.raw_id !== it.name) ? it.raw_id : it.item_id;
    const catBadge = it.category && it.category !== 'General' 
      ? `<span style="background:var(--bg-elevated); color:var(--gold-core); border:1px solid rgba(235,209,95,0.2); font-size:10px; padding:1px 6px; border-radius:4px; font-weight:normal; letter-spacing:0.3px;">${escapeHtml(it.category)}</span>` 
      : '';

    return `
      <tr>
        <td style="padding:10px 14px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <strong style="color:var(--text-pure); font-size:13.5px;">${escapeHtml(itemName)}</strong>
            ${catBadge}
          </div>
          <div style="font-family:monospace; color:var(--text-muted); font-size:11px; margin-top:2px;">
            ${escapeHtml(itemSub)}
          </div>
        </td>
        <td style="padding:10px 14px; font-weight:bold; color:var(--rune-green); font-size:14px;">
          ${(it.total_count || 0).toLocaleString()}
        </td>
        <td style="padding:10px 14px;">
          <span style="background:var(--bg-card); color:var(--text-muted); border:1px solid var(--bg-elevated); padding:2px 8px; border-radius:999px; font-size:11.5px; font-weight:600;">
            ${(it.container_count || conts.length)} containers
          </span>
        </td>
        <td style="padding:10px 14px;">
          ${badgesHtml} ${moreHtml}
        </td>
      </tr>
    `;
  }).join('');

  if (items.length > 150) {
    tbody.innerHTML += `<tr><td colspan="4" style="color:var(--text-muted); text-align:center; padding:12px; font-size:12px;">Showing first 150 of ${items.length} stored item types. Use the search bar above to filter.</td></tr>`;
  }
}

function renderStorageUnits() {
  const tbody = document.getElementById('containers-table-body');
  if (!tbody) return;

  if (!storageUnitsData || storageUnitsData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted); text-align:center; padding:24px;">No storage units detected in current save snapshot.</td></tr>';
    return;
  }

  const unitsToShow = storageUnitsData.slice(0, 150);
  tbody.innerHTML = unitsToShow.map(c => {
    const ownerBadge = c.owner && c.owner !== 'World / Unowned'
      ? `<span style="background:#22401f; color:var(--rune-green); padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">${escapeHtml(c.owner)}</span>`
      : `<span style="background:var(--bg-elevated); color:var(--text-muted); padding:2px 8px; border-radius:6px; font-size:11px;">World / Unowned</span>`;

    return `
      <tr>
        <td style="padding:10px 14px; font-weight:600; color:var(--text-pure);">
          ${escapeHtml(c.name)}
        </td>
        <td style="padding:10px 14px;">
          ${ownerBadge}
        </td>
        <td style="padding:10px 14px; color:var(--text-body); font-size:13px;">
          ${c.capacity} slots
        </td>
        <td style="padding:10px 14px; font-weight:600; color:var(--magic-blue); font-size:13px;">
          ${c.occupied_slots} used
        </td>
        <td style="padding:10px 14px; font-weight:bold; color:var(--rune-green); font-size:13px;">
          ${(c.total_items || 0).toLocaleString()} items
        </td>
        <td style="padding:10px 14px;">
          <button class="pill-btn" style="font-size:11px; padding:3px 8px;" onclick="inspectContainer('${c.id}')">Inspect Slots</button>
        </td>
      </tr>
    `;
  }).join('');

  if (storageUnitsData.length > 150) {
    tbody.innerHTML += `<tr><td colspan="6" style="color:var(--text-muted); text-align:center; padding:12px; font-size:12px;">Showing first 150 of ${storageUnitsData.length} storage containers.</td></tr>`;
  }
}

function inspectContainer(containerId) {
  const container = storageUnitsData.find(c => c.id === containerId);
  if (!container) return;

  const slots = container.slots || [];
  let modalHtml = `
    <div id="container-modal" style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; z-index:9999; backdrop-filter:blur(4px);">
      <div style="background:var(--bg-card); border:1px solid var(--gold-core); border-radius:12px; max-width:650px; width:90%; max-height:80vh; display:flex; flex-direction:column; padding:20px; box-shadow:0 12px 32px rgba(0,0,0,0.6);">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--bg-elevated); padding-bottom:12px; margin-bottom:14px;">
          <div>
            <h3 style="margin:0; color:var(--text-pure); font-size:18px;">${escapeHtml(container.name)}</h3>
            <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Owner: ${escapeHtml(container.owner)} | Capacity: ${container.capacity} slots (${container.occupied_slots} occupied)</div>
          </div>
          <button onclick="document.getElementById('container-modal').remove()" style="background:var(--bg-elevated); border:none; color:var(--text-pure); padding:6px 10px; border-radius:6px; cursor:pointer;">✕</button>
        </div>
        <div style="overflow-y:auto; flex:1;">
          <table style="width:100%; text-align:left; border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:1px solid var(--bg-elevated); color:var(--text-muted); font-size:11px; text-transform:uppercase;">
                <th style="padding:8px;">Slot</th>
                <th style="padding:8px;">Item Name / Identifier</th>
                <th style="padding:8px;">Count</th>
                <th style="padding:8px;">Durability</th>
              </tr>
            </thead>
            <tbody>
              ${slots.length === 0 ? '<tr><td colspan="4" style="text-align:center; padding:18px; color:var(--text-muted);">Container is empty</td></tr>' : slots.map(s => `
                <tr style="border-bottom:1px solid var(--bg-deep);">
                  <td style="padding:8px; color:var(--text-muted); font-family:monospace;">#${s.slot}</td>
                  <td style="padding:8px;">
                    <div style="font-weight:600; color:var(--gold-core); font-size:13px; display:flex; align-items:center; gap:6px;">
                      <span>${escapeHtml(s.name || s.item_id)}</span>
                      ${s.category && s.category !== 'General' ? `<span style="background:var(--bg-elevated); color:var(--text-muted); border:1px solid rgba(235,209,95,0.15); font-size:9.5px; padding:0 5px; border-radius:3px;">${escapeHtml(s.category)}</span>` : ''}
                    </div>
                    <div style="font-size:10.5px; color:var(--text-muted); font-family:monospace; margin-top:2px;">
                      ${escapeHtml(s.raw_id && s.raw_id !== s.name ? s.raw_id : s.item_id)}
                    </div>
                  </td>
                  <td style="padding:8px; font-weight:bold; color:var(--rune-green);">x${s.count || 1}</td>
                  <td style="padding:8px; color:var(--text-body); font-size:12px;">${s.durability !== undefined && s.durability !== null ? s.durability : '—'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// ----------------- BOSS ENCOUNTERS, CAMPAIGN & ARENAS -----------------
let bossesData = null;
let campaignData = null;
let worldEventsData = [];

async function loadCampaign() {
  try {
    const res = await fetch('/api/campaign');
    campaignData = await res.json();
    renderCampaign();
  } catch(e) {}
}

function renderCampaign() {
  if (!campaignData) return;
  const s = campaignData.summary || {};
  const elSpells = document.getElementById('camp-stat-spells');
  const elBuild = document.getElementById('camp-stat-buildings');
  const elRec = document.getElementById('camp-stat-recipes');
  const elShrine = document.getElementById('camp-stat-shrines');
  const elElites = document.getElementById('camp-stat-elites');
  const elGraves = document.getElementById('camp-stat-graves');
  const elCamps = document.getElementById('camp-stat-camps');

  if (elSpells) elSpells.innerText = s.spells_unlocked || 0;
  if (elBuild) elBuild.innerText = s.buildings_unlocked || 0;
  if (elRec) elRec.innerText = s.recipes_unlocked || 0;
  if (elShrine) elShrine.innerText = s.shrines_unlocked || 0;
  if (elElites) elElites.innerText = s.bosses_and_elites || 0;
  if (elGraves) elGraves.innerText = s.player_gravestones || 0;
  if (elCamps) elCamps.innerText = s.player_bedrolls || 0;
}

async function loadBosses() {
  try {
    const res = await fetch('/api/bosses');
    bossesData = await res.json();
    renderBosses();
    await loadCampaign();
  } catch(e) {}
}

function renderBosses() {
  if (!bossesData) return;
  const s = bossesData.summary || {};
  const elTotal = document.getElementById('boss-stat-total');
  const elDisc = document.getElementById('boss-stat-discovered');
  const elSave = document.getElementById('boss-stat-save');

  if (elTotal) elTotal.innerText = s.total_boss_arenas || 7;
  if (elDisc) elDisc.innerText = s.discovered_arenas || 0;
  if (elSave) elSave.innerText = s.active_world_save || 'None';
  updateNavBadge('bosses', `${s.discovered_arenas || 0}/${s.total_boss_arenas || 7}`);

  const tbody = document.getElementById('bosses-table-body');
  if (!tbody) return;

  const encounters = bossesData.encounters || [];
  if (encounters.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted); text-align:center; padding:24px;">No boss encounters discovered in active world.</td></tr>';
    return;
  }

  tbody.innerHTML = encounters.map(b => {
    const statusBadge = b.world_discovered
      ? '<span style="background:#22401f; color:var(--rune-green); padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">🟢 Discovered & Active</span>'
      : '<span style="background:var(--bg-elevated); color:var(--text-muted); padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">🔒 Undiscovered</span>';

    return `
      <tr>
        <td style="padding:12px 14px;">
          <div style="font-weight:600; color:var(--text-pure); font-size:14px;">${escapeHtml(b.name)}</div>
          <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">${escapeHtml(b.description)}</div>
        </td>
        <td style="padding:12px 14px; color:var(--text-body); font-size:13px;">${escapeHtml(b.lore_region)}</td>
        <td style="padding:12px 14px;">
          <span style="background:var(--bg-elevated); color:var(--gold-core); padding:2px 8px; border-radius:6px; font-size:11.5px; font-weight:500;">
            ${escapeHtml(b.category)}
          </span>
        </td>
        <td style="padding:12px 14px;">${statusBadge}</td>
      </tr>
    `;
  }).join('');
}

async function loadLiveWorldEvents() {
  try {
    const res = await fetch('/api/world-events');
    worldEventsData = await res.json();
    renderLiveWorldEvents();
  } catch(e) {}
}

function renderLiveWorldEvents() {
  const tbody = document.getElementById('world-events-table-body');
  if (!tbody) return;

  if (!worldEventsData || worldEventsData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted); text-align:center; padding:20px;">No recent world events or raids logged.</td></tr>';
    return;
  }

  tbody.innerHTML = worldEventsData.map(ev => {
    let typeStyle = 'background:var(--bg-elevated); color:var(--text-body);';
    if (ev.badge === 'raid') typeStyle = 'background:#521c17; color:#fca5a5;';
    else if (ev.badge === 'combat') typeStyle = 'background:#5c4314; color:var(--gold-light);';
    else if (ev.badge === 'chest') typeStyle = 'background:#22401f; color:var(--rune-green);';
    else if (ev.badge === 'player') typeStyle = 'background:#1a324a; color:var(--magic-blue);';

    return `
      <tr>
        <td style="padding:10px 14px; font-family:monospace; color:var(--text-muted); font-size:12px; white-space:nowrap;" title="${escapeHtml(formatLocalDate(ev.epoch || ev.iso || ev.timestamp))}">${escapeHtml(formatLocalDateTime(ev.epoch || ev.iso || ev.timestamp))}</td>
        <td style="padding:10px 14px;">
          <span style="${typeStyle} padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">
            ${escapeHtml(ev.type)}
          </span>
        </td>
        <td style="padding:10px 14px; color:var(--text-pure); font-size:13px;">${escapeHtml(ev.message)}</td>
        <td style="padding:10px 14px;">
          <span class="data-source-badge live" style="font-size:10px; padding:2px 6px;">${escapeHtml(ev.source)}</span>
        </td>
      </tr>
    `;
  }).join('');
}

// ----------------- INTERACTIVE WORLD MAP (ASHENFALL) -----------------
let mapRegions = [];
let mapRespawns = [];
let mapChests = [];
let mapActorsChests = [];
let mapBosses = [];
let mapWeather = [];
let mapGraves = [];
let mapCamps = [];
let mapFishing = [];
let mapNPCs = [];
let mapShrines = [];
let mapShortcuts = [];
let mapInitialized = false;
let mapSelectedTarget = null;
let mapHoveredTarget = null;
let mapMousePos = { x: 0, y: 0 };
let mapFilterLayer = 'all';
let mapSearchQuery = '';
let mapTransform = { x: 0, y: 0, scale: 0.85 };
let mapIsDragging = false;
let mapDragStart = { x: 0, y: 0 };
let mapHasDragged = false;
let mapCanvas = null;
let mapCtx = null;

// Preload Ashenfall Topographical Map Image
const worldMapImg = new Image();
let worldMapImgLoaded = false;
worldMapImg.onload = () => {
  worldMapImgLoaded = true;
  renderWorldMap();
};
worldMapImg.src = '/static/ashenfall_world_map_1000.jpg';

const MAP_ROADS = [
  ['MapRegionApproach', 'MapRegionPastures'],
  ['MapRegionPastures', 'MapRegionCourtyard'],
  ['MapRegionCourtyard', 'MapRegionGrandHall'],
  ['MapRegionCourtyard', 'MapRegionCathedral'],
  ['MapRegionCathedral', 'MapRegionLibrary'],
  ['MapRegionCourtyard', 'MapRegionGarrison'],
  ['MapRegionGarrison', 'MapRegionHighlands'],
  ['MapRegionHighlands', 'MapRegionHopesFall'],
  ['MapRegionHighlands', 'MapRegionCoalridge'],
  ['MapRegionGarrison', 'MapRegionBastion'],
  ['MapRegionBastion', 'MapRegionDragonsRun'],
  ['MapRegionDragonsRun', 'MapRegionTheBurningSpire'],
  ['MapRegionTheBurningSpire', 'MapRegionDemonGate'],
  ['MapRegionPastures', 'MapRegionBramblemead'],
  ['MapRegionBramblemead', 'MapRegionTempleWoods'],
  ['MapRegionTempleWoods', 'MapRegionSilverthorn'],
  ['MapRegionSilverthorn', 'MapRegionEmberwood'],
  ['MapRegionEmberwood', 'MapRegionLake'],
  ['MapRegionLake', 'MapRegionLakeOfLostSouls'],
  ['MapRegionLakeOfLostSouls', 'MapRegionBleakfields'],
  ['MapRegionSilverthorn', 'MapRegionNexus'],
  ['MapRegionPastures', 'MapRegionFracturedPlains'],
  ['MapRegionFracturedPlains', 'MapRegionCrypt'],
  ['MapRegionCrypt', 'MapRegionBloodblight'],
  ['MapRegionBloodblight', 'MapRegionWhisperingSwamp'],
  ['MapRegionWhisperingSwamp', 'MapRegionWItchWillow'],
  ['MapRegionFracturedPlains', 'MapRegionManafemPlains'],
  ['MapRegionManafemPlains', 'MapRegionAlcarridOasis'],
  ['MapRegionAlcarridOasis', 'MapRegionDunesOfUzzer']
];

const BIOME_COLORS = {
  'Desert': { fill: 'rgba(217, 119, 6, 0.22)', stroke: '#ebd15f', text: '#ebd15f' },
  'Plains': { fill: 'rgba(132, 190, 91, 0.18)', stroke: '#84be5b', text: '#84be5b' },
  'Meadow': { fill: 'rgba(132, 190, 91, 0.18)', stroke: '#84be5b', text: '#84be5b' },
  'Forest': { fill: 'rgba(74, 138, 52, 0.22)', stroke: '#84be5b', text: '#a7f3d0' },
  'Highlands': { fill: 'rgba(140, 199, 239, 0.22)', stroke: '#8cc7ef', text: '#8cc7ef' },
  'Mountains': { fill: 'rgba(140, 199, 239, 0.22)', stroke: '#8cc7ef', text: '#bae6fd' },
  'Wasteland': { fill: 'rgba(162, 154, 141, 0.22)', stroke: '#a29a8d', text: '#e0dbd1' },
  'Volcanic': { fill: 'rgba(196, 58, 46, 0.22)', stroke: '#c43a2e', text: '#fca5a5' },
  'Fortress': { fill: 'rgba(219, 166, 207, 0.22)', stroke: '#dba6cf', text: '#dba6cf' },
  'Ruins': { fill: 'rgba(219, 166, 207, 0.22)', stroke: '#dba6cf', text: '#dba6cf' },
  'Sanctuary': { fill: 'rgba(219, 166, 207, 0.22)', stroke: '#dba6cf', text: '#dba6cf' },
  'Subterranean': { fill: 'rgba(74, 64, 57, 0.30)', stroke: '#a29a8d', text: '#e0dbd1' },
  'Swamp': { fill: 'rgba(13, 148, 136, 0.22)', stroke: '#0d9488', text: '#5eead4' },
  'Lake': { fill: 'rgba(140, 199, 239, 0.22)', stroke: '#8cc7ef', text: '#8cc7ef' },
  'Mystic': { fill: 'rgba(219, 166, 207, 0.22)', stroke: '#dba6cf', text: '#dba6cf' },
  'Arcane': { fill: 'rgba(219, 166, 207, 0.22)', stroke: '#dba6cf', text: '#dba6cf' }
};

async function initWorldMap() {
  mapCanvas = document.getElementById('world-map-canvas');
  if (!mapCanvas) return;
  mapCtx = mapCanvas.getContext('2d');

  if (!mapInitialized) {
    setupMapEventListeners();
    mapInitialized = true;
  }

  await refreshMapData();
  renderWorldMap();
}

async function refreshMapData() {
  try {
    const [resReg, resResp, resBoss, resWeath, resCamp, resActors] = await Promise.all([
      fetch('/api/world/regions').then(r => r.json()).catch(() => []),
      fetch('/api/respawns').then(r => r.json()).catch(() => []),
      fetch('/api/bosses').then(r => r.json()).catch(() => ({ encounters: [] })),
      fetch('/api/weather').then(r => r.json()).catch(() => []),
      fetch('/api/campaign').then(r => r.json()).catch(() => ({})),
      fetch('/api/world/actors?category=all').then(r => r.json()).catch(() => ({}))
    ]);

    mapRegions = Array.isArray(resReg) ? resReg : [];
    mapRespawns = Array.isArray(resResp) ? resResp : [];
    mapBosses = (resBoss && resBoss.encounters) ? resBoss.encounters : [];
    mapWeather = Array.isArray(resWeath) ? resWeath : [];
    mapGraves = (resCamp && resCamp.death_markers) ? resCamp.death_markers : [];
    mapCamps = (resCamp && resCamp.camps) ? resCamp.camps : [];
    const actData = (resActors && resActors.actors) || {};
    mapFishing = actData.fishing || [];
    mapNPCs = actData.npcs || [];
    mapShrines = actData.shrines || [];
    mapShortcuts = actData.shortcuts || [];
    mapActorsChests = actData.chests || [];

    // Build unified chests catalog: SpudCache 3D chests + live log respawns
    const liveMap = new Map();
    for (const r of mapRespawns) {
      if (r && r.id) {
        liveMap.set(r.id, r);
        const short = r.id.includes('_UAID_') ? 'UAID_' + r.id.split('_UAID_')[1] : r.id;
        liveMap.set(short, r);
      }
    }

    const unifiedChests = [];
    const seenChests = new Set();

    for (const sc of mapActorsChests) {
      const live = liveMap.get(sc.id);
      seenChests.add(sc.id);
      if (sc.full_name) seenChests.add(sc.full_name);
      unifiedChests.push({
        ...sc,
        name: sc.title || sc.name,
        status: live ? live.status : 'ready',
        is_ready: live ? live.status === 'ready' : true,
        remaining_seconds: live ? (live.remaining_seconds || 0) : 0,
        remaining_formatted: live ? (live.remaining_formatted || 'Ready') : 'Ready',
        duration_formatted: live ? live.duration_formatted : 'Standard',
        respawn_epoch: live ? (live.respawn_epoch || 0) : 0,
        source: live ? 'live_log' : 'spud_cache_3d'
      });
    }

    for (const lr of mapRespawns) {
      const short = (lr.id && lr.id.includes('_UAID_')) ? 'UAID_' + lr.id.split('_UAID_')[1] : lr.id;
      if (lr.id && !seenChests.has(lr.id) && !seenChests.has(short)) {
        seenChests.add(lr.id);
        unifiedChests.push({
          ...lr,
          title: lr.name,
          is_ready: lr.status === 'ready'
        });
      }
    }

    mapChests = unifiedChests;

    if (!mapSelectedTarget && mapRegions.length > 0) {
      const central = mapRegions.find(r => r.id === 'MapRegionCourtyard') || mapRegions[0];
      selectMapMarker({ type: 'region', data: central }, false);
    }
  } catch(e) {}
}

function setupMapEventListeners() {
  if (!mapCanvas) return;

  mapCanvas.addEventListener('mousedown', (e) => {
    mapIsDragging = true;
    mapHasDragged = false;
    mapDragStart = { x: e.clientX - mapTransform.x, y: e.clientY - mapTransform.y };
    mapCanvas.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (e) => {
    if (!mapCanvas) return;
    const rect = mapCanvas.getBoundingClientRect();
    mapMousePos.x = e.clientX - rect.left;
    mapMousePos.y = e.clientY - rect.top;

    if (mapIsDragging) {
      mapHasDragged = true;
      mapTransform.x = e.clientX - mapDragStart.x;
      mapTransform.y = e.clientY - mapDragStart.y;
      renderWorldMap();
      return;
    }

    if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
      const canvasX = (e.clientX - rect.left) * (mapCanvas.width / rect.width);
      const canvasY = (e.clientY - rect.top) * (mapCanvas.height / rect.height);
      const wx = (canvasX - mapCanvas.width / 2 - mapTransform.x) / mapTransform.scale + 500;
      const wy = (canvasY - mapCanvas.height / 2 - mapTransform.y) / mapTransform.scale + 500;

      const hit = findMapMarkerAt(wx, wy);
      const prevHitId = mapHoveredTarget ? (mapHoveredTarget.data.id || mapHoveredTarget.data.name || mapHoveredTarget.data.index) : null;
      const newHitId = hit ? (hit.data.id || hit.data.name || hit.data.index) : null;
      if (prevHitId !== newHitId) {
        mapHoveredTarget = hit;
        mapCanvas.style.cursor = hit ? 'pointer' : 'grab';
        renderWorldMap();
      }
    } else if (mapHoveredTarget) {
      mapHoveredTarget = null;
      renderWorldMap();
    }
  });

  window.addEventListener('mouseup', () => {
    if (mapIsDragging) {
      mapIsDragging = false;
      if (mapCanvas) mapCanvas.style.cursor = mapHoveredTarget ? 'pointer' : 'grab';
    }
  });

  mapCanvas.addEventListener('mouseleave', () => {
    if (mapHoveredTarget) {
      mapHoveredTarget = null;
      renderWorldMap();
    }
  });

  mapCanvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    mapTransform.scale = Math.max(0.4, Math.min(3.5, mapTransform.scale * zoomFactor));
    renderWorldMap();
  }, { passive: false });

  mapCanvas.addEventListener('click', (e) => {
    if (mapHasDragged) return;
    handleMapClick(e);
  });

  let lastTouchDist = 0;
  mapCanvas.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      mapIsDragging = true;
      mapHasDragged = false;
      mapDragStart = { x: e.touches[0].clientX - mapTransform.x, y: e.touches[0].clientY - mapTransform.y };
    } else if (e.touches.length === 2) {
      lastTouchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }
  }, { passive: true });

  mapCanvas.addEventListener('touchmove', (e) => {
    if (e.touches.length === 1 && mapIsDragging) {
      mapHasDragged = true;
      mapTransform.x = e.touches[0].clientX - mapDragStart.x;
      mapTransform.y = e.touches[0].clientY - mapDragStart.y;
      renderWorldMap();
    } else if (e.touches.length === 2) {
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      if (lastTouchDist > 0) {
        const factor = dist / lastTouchDist;
        mapTransform.scale = Math.max(0.4, Math.min(3.5, mapTransform.scale * factor));
        renderWorldMap();
      }
      lastTouchDist = dist;
    }
  }, { passive: true });

  mapCanvas.addEventListener('touchend', (e) => {
    if (e.touches.length === 0) {
      mapIsDragging = false;
      lastTouchDist = 0;
    }
  });
}

function getGraveWorldCoords(grave, index) {
  if (grave && grave.map_coords && typeof grave.map_coords.x === 'number') {
    return { wx: grave.map_coords.x, wy: grave.map_coords.y };
  }
  const zone = (grave && grave.zone) || 'Overworld';
  let base = { x: 290, y: 520 };
  if (zone === 'Brynmoore') base = { x: 280, y: 480 };
  else if (zone === 'Ghornefell') base = { x: 560, y: 400 };
  else if (zone === 'Dowdun Reach') base = { x: 420, y: 220 };
  else if (zone === 'Fellhollow') base = { x: 240, y: 660 };
  else if (zone === 'Umbral Sands') base = { x: 680, y: 580 };

  const col = index % 4;
  const row = Math.floor(index / 4);
  return {
    wx: base.x - 36 + (col * 24),
    wy: base.y + 18 + (row * 20)
  };
}

function getCampWorldCoords(camp, index) {
  if (camp && camp.map_coords && typeof camp.map_coords.x === 'number') {
    return { wx: camp.map_coords.x, wy: camp.map_coords.y };
  }
  if (index === 0) return { wx: 345, wy: 535 };
  if (index === 1) return { wx: 360, wy: 550 };
  return { wx: 330 + (index * 20), wy: 520 };
}

function getChestWorldCoords(chest, index) {
  if (chest && chest.map_coords && typeof chest.map_coords.x === 'number') {
    return { wx: chest.map_coords.x, wy: chest.map_coords.y };
  }
  const zone = (chest && chest.zone) || 'Overworld';
  let base = { x: 280, y: 480 };
  if (zone === 'Brynmoore') base = { x: 280, y: 480 };
  else if (zone === 'Ghornefell') base = { x: 560, y: 400 };
  else if (zone === 'Dowdun Reach') base = { x: 420, y: 220 };
  else if (zone === 'Fellhollow') base = { x: 240, y: 660 };
  else if (zone === 'Umbral Sands') base = { x: 680, y: 580 };

  const col = index % 3;
  const row = Math.floor(index / 3);
  return {
    wx: base.x - 28 + (col * 28),
    wy: base.y - 42 - (row * 22)
  };
}

function getBossWorldCoords(boss) {
  if (boss && boss.map_coords && typeof boss.map_coords.x === 'number') {
    return { wx: boss.map_coords.x, wy: boss.map_coords.y };
  }
  const n = (((boss && boss.name) || '') + ' ' + ((boss && boss.id) || '')).toLowerCase();
  if (n.includes('dragon') || n.includes('velgar')) return { wx: 530, wy: 350 };
  if (n.includes('kalphite')) return { wx: 650, wy: 620 };
  if (n.includes('fight cave') || n.includes('fuzan') || n.includes('tztok') || n.includes('fight caves')) return { wx: 570, wy: 400 };
  if (n.includes('demon') || n.includes('hellfire') || n.includes('gate')) return { wx: 550, wy: 450 };
  if (n.includes('titan') || n.includes('bastion')) return { wx: 620, wy: 380 };
  if (n.includes('burning spire') || n.includes('crucible')) return { wx: 570, wy: 400 };
  if (n.includes('sands') || n.includes('oasis')) return { wx: 670, wy: 440 };
  if (n.includes('death') || n.includes('imaru') || n.includes('crypt')) return { wx: 340, wy: 650 };
  return { wx: 280, wy: 500 };
}

function findMapMarkerAt(wx, wy) {
  const hitTol = Math.max(12, 18 / mapTransform.scale);

  // 1. Fishing Nodes
  if (mapFilterLayer === 'all' || mapFilterLayer === 'fishing') {
    for (const f of mapFishing) {
      if (Math.hypot(wx - f.map_coords.x, wy - f.map_coords.y) <= hitTol) {
        return { type: 'fishing', data: f, wx: f.map_coords.x, wy: f.map_coords.y };
      }
    }
  }

  // 2. NPCs & Quest Givers
  if (mapFilterLayer === 'all' || mapFilterLayer === 'npcs') {
    for (const n of mapNPCs) {
      if (Math.hypot(wx - n.map_coords.x, wy - n.map_coords.y) <= hitTol) {
        return { type: 'npc', data: n, wx: n.map_coords.x, wy: n.map_coords.y };
      }
    }
  }

  // 3. Sacred Shrines
  if (mapFilterLayer === 'all' || mapFilterLayer === 'shrines') {
    for (const s of mapShrines) {
      if (Math.hypot(wx - s.map_coords.x, wy - s.map_coords.y) <= hitTol) {
        return { type: 'shrine', data: s, wx: s.map_coords.x, wy: s.map_coords.y };
      }
    }
  }

  // 4. Bosses
  if (mapFilterLayer === 'all' || mapFilterLayer === 'bosses') {
    for (const b of mapBosses) {
      const bw = getBossWorldCoords(b);
      if (Math.hypot(wx - bw.wx, wy - bw.wy) <= hitTol) {
        return { type: 'boss', data: b, wx: bw.wx, wy: bw.wy };
      }
    }
  }

  // 5. Chests
  if (mapFilterLayer === 'all' || mapFilterLayer === 'chests') {
    for (let i = 0; i < mapChests.length; i++) {
      const c = mapChests[i];
      const cw = getChestWorldCoords(c, i);
      if (Math.hypot(wx - cw.wx, wy - cw.wy) <= hitTol) {
        return { type: 'chest', data: c, wx: cw.wx, wy: cw.wy };
      }
    }
  }

  // 6. Graves
  if (mapFilterLayer === 'all' || mapFilterLayer === 'graves') {
    for (let i = 0; i < mapGraves.length; i++) {
      const g = mapGraves[i];
      const gw = getGraveWorldCoords(g, i);
      if (Math.hypot(wx - gw.wx, wy - gw.wy) <= hitTol) {
        return { type: 'grave', data: g, wx: gw.wx, wy: gw.wy };
      }
    }
  }

  // 7. Camps
  if (mapFilterLayer === 'all' || mapFilterLayer === 'camps') {
    for (let i = 0; i < mapCamps.length; i++) {
      const camp = mapCamps[i];
      const cw = getCampWorldCoords(camp, i);
      if (Math.hypot(wx - cw.wx, wy - cw.wy) <= hitTol) {
        return { type: 'camp', data: camp, wx: cw.wx, wy: cw.wy };
      }
    }
  }

  // 8. Canonical Regions
  for (const r of mapRegions) {
    const rx = r.x || 500;
    const ry = r.y || 500;
    if (Math.hypot(wx - rx, wy - ry) <= 22) {
      return { type: 'region', data: r, wx: rx, wy: ry };
    }
  }

  return null;
}

function handleMapClick(e) {
  if (!mapCanvas) return;
  const rect = mapCanvas.getBoundingClientRect();
  const canvasX = (e.clientX - rect.left) * (mapCanvas.width / rect.width);
  const canvasY = (e.clientY - rect.top) * (mapCanvas.height / rect.height);
  const wx = (canvasX - mapCanvas.width / 2 - mapTransform.x) / mapTransform.scale + 500;
  const wy = (canvasY - mapCanvas.height / 2 - mapTransform.y) / mapTransform.scale + 500;

  const hit = findMapMarkerAt(wx, wy);
  if (hit) {
    selectMapMarker(hit);
  }
}

function selectMapMarker(target, doRender = true) {
  mapSelectedTarget = target;
  const titleEl = document.getElementById('map-inspector-title');
  const subEl = document.getElementById('map-inspector-sub');
  const chestsEl = document.getElementById('map-inspector-chests');
  const loreEl = document.getElementById('map-inspector-lore');

  if (!titleEl || !subEl || !chestsEl || !loreEl) return;

  if (target.type === 'region') {
    const r = target.data;
    titleEl.innerText = r.name;
    subEl.innerText = `Biome: ${r.biome || 'Plains'} | Sector: [${r.x}, ${r.y}]`;
    loreEl.innerText = r.lore || 'Canonical world region across the realm of Dragonwilds.';

    const regChests = mapRespawns.filter(c => {
      const z = (c.zone || '').toLowerCase();
      const n = (r.name || '').toLowerCase();
      if (z && n.includes(z)) return true;
      if (n.includes('courtyard') && z.includes('brynmoore')) return true;
      if (n.includes('garrison') && z.includes('ghornefell')) return true;
      if (n.includes('highlands') && z.includes('dowdun')) return true;
      if (n.includes('crypt') && z.includes('fellhollow')) return true;
      return false;
    });

    if (regChests.length === 0) {
      chestsEl.innerHTML = '<span style="color:var(--text-muted); font-size:12px;">No active dungeon chests currently assigned to this sector.</span>';
    } else {
      chestsEl.innerHTML = `
        <div style="font-size:12px; color:var(--magic-blue); font-weight:600; margin-bottom:6px;">
          ${regChests.length} Localized Dungeon Caches & Loot Nodes:
        </div>
        <div style="display:flex; flex-direction:column; gap:6px;">
          ${regChests.map(c => `
            <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:6px 10px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
              <div>
                <div style="font-weight:600; color:var(--text-pure); font-size:12px;">${escapeHtml(c.name)}</div>
                <div style="font-size:10.5px; color:var(--text-muted);">${escapeHtml(c.duration_formatted ? 'Cycle: ' + c.duration_formatted : '')}</div>
              </div>
              <div>
                ${c.is_ready
                  ? '<span style="background:#22401f; color:var(--rune-green); padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">🟢 Ready to Loot</span>'
                  : `<span style="background:#5c4314; color:var(--gold-light); padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">⏳ ${escapeHtml(c.remaining_formatted)}</span>`
                }
              </div>
            </div>
          `).join('')}
        </div>
      `;
    }
  } else if (target.type === 'chest') {
    const c = target.data;
    const displayName = c.title || c.name || 'Treasure Chest';
    titleEl.innerText = displayName;
    const cellInfo = c.cell ? ` • Grid Cell: ${c.cell}` : '';
    const posInfo = c.world_pos ? ` • Elevation: ${c.world_pos.z} cm` : '';
    subEl.innerText = `Loot Cache • Territory: ${c.zone || 'Overworld'}${cellInfo}${posInfo}`;
    const readyTimeStr = c.respawn_epoch || c.respawn_time ? formatLocalDateTime(c.respawn_epoch || c.respawn_time) : 'Now';

    chestsEl.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:var(--text-pure);">Loot Status</span>
          ${c.is_ready
            ? '<span style="background:#22401f; color:var(--rune-green); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟢 Ready to Loot</span>'
            : '<span style="background:#5c4314; color:var(--gold-light); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">⏳ Respawning</span>'
          }
        </div>
        <div style="font-size:12px; color:var(--text-body); line-height:1.6;">
          ${!c.is_ready ? `<div><strong>Remaining Time:</strong> <span style="color:var(--gold-core);">${escapeHtml(c.remaining_formatted || 'In Progress')}</span></div>` : ''}
          ${!c.is_ready && c.respawn_epoch ? `<div><strong>Ready At:</strong> <span style="color:var(--magic-blue);">${escapeHtml(readyTimeStr)}</span></div>` : ''}
          ${c.cell ? `<div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:var(--text-body);">${escapeHtml(c.cell)}</span></div>` : ''}
          ${c.world_pos ? `<div><strong>Exact 3D Coordinates:</strong> <span style="color:var(--magic-blue);">X=${c.world_pos.x}, Y=${c.world_pos.y}, Z=${c.world_pos.z}</span></div>` : ''}
          ${c.map_coords ? `<div><strong>Map Canvas Coords:</strong> <span style="color:var(--text-body);">X=${c.map_coords.x}, Y=${c.map_coords.y}</span></div>` : ''}
          <div><strong>Persistence ID:</strong> <span style="font-family:monospace; font-size:11px; color:var(--text-muted);">${escapeHtml(c.id)}</span></div>
          <div><strong>Source Verification:</strong> <span style="color:${c.source === 'live_log' ? 'var(--rune-green)' : 'var(--magic-blue)'}; font-weight:600;">${c.source === 'live_log' ? '⚡ Live Server Log Tick' : '💾 Extracted SpudCache 3D Transform'}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = c.hint || `Objective treasure container tracked with authentic in-engine coordinates.`;
  } else if (target.type === 'boss') {
    const b = target.data;
    titleEl.innerText = b.name;
    subEl.innerText = `Boss Arena | Lore Region: ${b.lore_region} | Category: ${b.category}`;
    chestsEl.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:var(--text-pure);">Encounter Gate</span>
          ${b.world_discovered
            ? '<span style="background:#22401f; color:var(--rune-green); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟢 Discovered & Active</span>'
            : '<span style="background:var(--bg-elevated); color:var(--text-muted); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔒 Undiscovered</span>'
          }
        </div>
        <div style="font-size:12px; color:var(--text-body); line-height:1.5; margin-bottom:8px;">${escapeHtml(b.description || 'Major world encounter.')}</div>
        <div style="font-size:12px; color:var(--text-muted); line-height:1.6;">
          <div><strong>Encounter Lore Region:</strong> <span style="color:var(--text-pure);">${escapeHtml(b.lore_region)}</span></div>
          ${b.map_coords ? `<div><strong>Canvas Arena Coords:</strong> <span style="color:var(--magic-blue);">X=${b.map_coords.x}, Y=${b.map_coords.y}</span></div>` : ''}
          <div><strong>Status:</strong> <span style="color:${b.world_discovered ? 'var(--rune-green)' : 'var(--text-muted)'};">${escapeHtml(b.status || 'Undiscovered')}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Canonical sanctum or portal arena for high-tier combat trials. Verified through in-world teleporter blueprints in active server saves.`;
  } else if (target.type === 'grave') {
    const g = target.data;
    titleEl.innerText = g.name || `Player Gravestone #${g.index}`;
    const cellInfo = g.cell ? ` • Grid Cell: ${g.cell}` : '';
    const posInfo = g.world_pos ? ` • Elevation: ${g.world_pos.z} cm` : '';
    subEl.innerText = `Death Marker • Sector: ${g.zone || 'Overworld'}${cellInfo}${posInfo}`;
    chestsEl.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:var(--text-pure);">Death Marker Status</span>
          <span style="background:#4a243c; color:var(--arcane-purple); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🪦 Persistent Grave</span>
        </div>
        <div style="font-size:12px; color:var(--text-body); line-height:1.6;">
          <div><strong>Grave Number:</strong> <span style="color:var(--text-pure);">#${g.index}</span></div>
          <div><strong>Territory Sector:</strong> <span style="color:var(--magic-blue);">${escapeHtml(g.zone)}</span></div>
          ${g.cell ? `<div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:var(--text-body);">${escapeHtml(g.cell)}</span></div>` : ''}
          ${g.world_pos ? `<div><strong>Exact 3D Coordinates:</strong> <span style="color:var(--magic-blue);">X=${g.world_pos.x}, Y=${g.world_pos.y}, Z=${g.world_pos.z}</span></div>` : ''}
          ${g.map_coords ? `<div><strong>Map Canvas Coords:</strong> <span style="color:var(--text-body);">X=${g.map_coords.x}, Y=${g.map_coords.y}</span></div>` : ''}
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:var(--text-muted);">${escapeHtml(g.short_id || g.id)}</span></div>
          <div><strong>Source Verification:</strong> <span style="color:var(--arcane-purple); font-weight:600;">${g.source === 'spud_cache_3d' ? '💾 Verified SpudCache 3D Transform' : '📁 Savefile Player Registry'}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Permanent player death gravestone in Hardcore mode. Holds the fallen adventurer's belongings and inventory at exact coordinates of demise.`;
  } else if (target.type === 'camp') {
    const camp = target.data;
    titleEl.innerText = camp.name || `Settlement Bedroll #${camp.index}`;
    subEl.innerText = `Settlement Landmark | Sector: ${camp.zone} | Type: Claimed Bedroll`;
    chestsEl.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:var(--text-pure);">Camp Status</span>
          <span style="background:#1a324a; color:var(--magic-blue); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">⛺ Active Spawn Point</span>
        </div>
        <div style="font-size:12px; color:var(--text-body); line-height:1.6;">
          <div><strong>Bedroll Index:</strong> <span style="color:var(--text-pure);">#${camp.index}</span></div>
          <div><strong>Territory Sector:</strong> <span style="color:var(--magic-blue);">${escapeHtml(camp.zone)}</span></div>
          ${camp.map_coords ? `<div><strong>Camp Coordinates:</strong> <span style="color:var(--magic-blue);">X=${camp.map_coords.x}, Y=${camp.map_coords.y}</span></div>` : ''}
          <div><strong>Spawn Point Type:</strong> <span style="color:var(--text-pure);">Territorial Bedroll Camp</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Active player bedroll anchor registered in active server save. Functions as territorial respawn point.`;
  } else if (target.type === 'fishing') {
    const f = target.data;
    titleEl.innerText = f.title;
    subEl.innerText = `Fishing Resource • Grid Cell: ${f.cell} • Water Elevation: ${f.world_pos.z} cm`;
    chestsEl.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:var(--text-pure);">Fishing Node Details</span>
          <span style="background:#1a324a; color:var(--magic-blue); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🎣 Active Spot</span>
        </div>
        <div style="font-size:12px; color:var(--text-body); line-height:1.6;">
          <div><strong>Fishing Method:</strong> <span style="color:var(--text-pure);">${escapeHtml(f.title)}</span></div>
          <div><strong>Requirement:</strong> <span style="color:var(--magic-blue);">${escapeHtml(f.hint)}</span></div>
          <div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:var(--text-body);">${escapeHtml(f.cell)}</span></div>
          <div><strong>Exact 3D Coordinates:</strong> <span style="color:var(--magic-blue);">X=${f.world_pos.x}, Y=${f.world_pos.y}, Z=${f.world_pos.z}</span></div>
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:var(--text-muted);">${escapeHtml(f.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Permanent world fishing spawner stream-loaded from Unreal Engine level geometry. Harvestable by players with appropriate tackle.`;
  } else if (target.type === 'npc') {
    const n = target.data;
    titleEl.innerText = n.title;
    subEl.innerText = `Interactive NPC • Grid Cell: ${n.cell} • Elevation: ${n.world_pos.z} cm`;
    chestsEl.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:var(--text-pure);">Character Status</span>
          <span style="background:#5c4314; color:var(--gold-light); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">👤 Persistent Character</span>
        </div>
        <div style="font-size:12px; color:var(--text-body); line-height:1.6;">
          <div><strong>Role & Interaction:</strong> <span style="color:var(--text-pure);">${escapeHtml(n.hint)}</span></div>
          <div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:var(--text-body);">${escapeHtml(n.cell)}</span></div>
          <div><strong>Blueprint Class:</strong> <span style="font-family:monospace; font-size:11px; color:var(--text-muted);">${escapeHtml(n.class_name)}</span></div>
          <div><strong>Exact 3D Coordinates:</strong> <span style="color:var(--magic-blue);">X=${n.world_pos.x}, Y=${n.world_pos.y}, Z=${n.world_pos.z}</span></div>
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:var(--text-muted);">${escapeHtml(n.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = n.hint || `World character registered in active level persistence cache.`;
  } else if (target.type === 'shrine') {
    const s = target.data;
    titleEl.innerText = s.title;
    subEl.innerText = `Sacred Monument • Grid Cell: ${s.cell} • Elevation: ${s.world_pos.z} cm`;
    chestsEl.innerHTML = `
      <div style="background:var(--bg-card); border:1px solid var(--bg-elevated); padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:var(--text-pure);">Monument Blessing</span>
          <span style="background:#4a243c; color:var(--arcane-purple); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">✨ Active Shrine</span>
        </div>
        <div style="font-size:12px; color:var(--text-body); line-height:1.6;">
          <div><strong>Sanctuary Effect:</strong> <span style="color:var(--text-pure);">${escapeHtml(s.hint)}</span></div>
          <div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:var(--text-body);">${escapeHtml(s.cell)}</span></div>
          <div><strong>Exact 3D Coordinates:</strong> <span style="color:var(--magic-blue);">X=${s.world_pos.x}, Y=${s.world_pos.y}, Z=${s.world_pos.z}</span></div>
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:var(--text-muted);">${escapeHtml(s.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = s.hint || `Sacred landmark in Ashenfall.`;
  }

  if (doRender) renderWorldMap();
}

function switchTabToMapMarker(markerId) {
  setTab('map');
  const findChest = mapChests.find(r => r.id === markerId || r.title === markerId || r.name === markerId) || mapRespawns.find(r => r.id === markerId);
  if (findChest) {
    const idx = mapChests.indexOf(findChest);
    const coords = getChestWorldCoords(findChest, idx >= 0 ? idx : 0);
    mapTransform.x = -(coords.wx - 500) * mapTransform.scale;
    mapTransform.y = -(coords.wy - 500) * mapTransform.scale;
    selectMapMarker({ type: 'chest', data: findChest, wx: coords.wx, wy: coords.wy });
    return;
  }
  const findBoss = mapBosses.find(b => b.name === markerId || b.id === markerId);
  if (findBoss) {
    const coords = getBossWorldCoords(findBoss);
    mapTransform.x = -(coords.wx - 500) * mapTransform.scale;
    mapTransform.y = -(coords.wy - 500) * mapTransform.scale;
    selectMapMarker({ type: 'boss', data: findBoss, wx: coords.wx, wy: coords.wy });
  }
}

function zoomMap(factor) {
  mapTransform.scale = Math.max(0.35, Math.min(3.5, mapTransform.scale * factor));
  renderWorldMap();
}

function resetMap() {
  mapTransform = { x: 0, y: 0, scale: 0.85 };
  if (mapRegions.length > 0) {
    const central = mapRegions.find(r => r.id === 'MapRegionCourtyard') || mapRegions[0];
    selectMapMarker({ type: 'region', data: central });
  } else {
    renderWorldMap();
  }
}

function toggleMapLayer(layer, btn) {
  mapFilterLayer = layer;
  document.querySelectorAll('#map-layer-pills .pill-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderWorldMap();
}

function filterMapMarkersLive() {
  const input = document.getElementById('map-search-input');
  mapSearchQuery = input ? input.value.trim().toLowerCase() : '';
  renderWorldMap();
}

function drawMapLabel(ctx, text, x, y, textColor = 'var(--text-pure)', bgColor = 'rgba(34, 29, 26, 0.92)') {
  ctx.save();
  ctx.font = 'bold 10px system-ui, sans-serif';
  const textWidth = ctx.measureText(text).width;
  const padX = 6;
  const h = 16;
  ctx.fillStyle = bgColor;
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(x - textWidth / 2 - padX, y - h / 2, textWidth + padX * 2, h, 4);
  } else {
    ctx.rect(x - textWidth / 2 - padX, y - h / 2, textWidth + padX * 2, h);
  }
  ctx.fill();
  ctx.strokeStyle = 'rgba(235, 209, 95, 0.35)';
  ctx.lineWidth = 1;
  ctx.stroke();

  ctx.fillStyle = textColor;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x, y);
  ctx.restore();
}

function drawCompassRose(ctx, cx, cy) {
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, 22, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(34, 29, 26, 0.9)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(235, 209, 95, 0.7)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // North needle
  ctx.fillStyle = '#c43a2e';
  ctx.beginPath();
  ctx.moveTo(cx, cy - 16);
  ctx.lineTo(cx - 5, cy);
  ctx.lineTo(cx, cy - 2);
  ctx.fill();

  // South needle
  ctx.fillStyle = '#a29a8d';
  ctx.beginPath();
  ctx.moveTo(cx, cy + 16);
  ctx.lineTo(cx + 5, cy);
  ctx.lineTo(cx, cy + 2);
  ctx.fill();

  ctx.fillStyle = '#ebd15f';
  ctx.font = 'bold 9px system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('N', cx, cy - 7);
  ctx.restore();
}

function drawHoverTooltip(ctx, target, mx, my) {
  ctx.save();
  let title = '';
  let badge = '';
  let badgeColor = '#8cc7ef';

  if (target.type === 'region') {
    title = target.data.name;
    badge = `Territory • ${target.data.biome || 'Plains'}`;
  } else if (target.type === 'boss') {
    title = target.data.name;
    badge = '⚔️ Boss Arena Gate';
    badgeColor = '#c43a2e';
  } else if (target.type === 'chest') {
    title = target.data.name;
    badge = target.data.is_ready ? '🟢 Ready to Loot' : `⏳ ${target.data.remaining_formatted}`;
    badgeColor = target.data.is_ready ? '#84be5b' : '#ebd15f';
  } else if (target.type === 'grave') {
    title = target.data.name;
    badge = `🪦 Grave (${target.data.zone || 'Overworld'})`;
    badgeColor = '#dba6cf';
  } else if (target.type === 'camp') {
    title = target.data.name;
    badge = '⛺ Claimed Bedroll Camp';
    badgeColor = '#8cc7ef';
  } else if (target.type === 'fishing') {
    title = target.data.title;
    badge = `🎣 Fishing Spot (${target.data.cell})`;
    badgeColor = '#8cc7ef';
  } else if (target.type === 'npc') {
    title = target.data.title;
    badge = `👤 NPC / Quest (${target.data.cell})`;
    badgeColor = '#ebd15f';
  } else if (target.type === 'shrine') {
    title = target.data.title;
    badge = `✨ Shrine (${target.data.cell})`;
    badgeColor = '#dba6cf';
  }

  ctx.font = 'bold 12px system-ui, sans-serif';
  const titleWidth = ctx.measureText(title).width;
  ctx.font = '11px system-ui, sans-serif';
  const badgeWidth = ctx.measureText(badge).width;
  const boxWidth = Math.max(titleWidth, badgeWidth) + 24;
  const boxHeight = 44;

  let bx = mx + 14;
  let by = my - boxHeight - 8;
  if (bx + boxWidth > ctx.canvas.width - 10) bx = mx - boxWidth - 14;
  if (by < 10) by = my + 14;

  ctx.fillStyle = 'rgba(34, 29, 26, 0.95)';
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(bx, by, boxWidth, boxHeight, 6);
  } else {
    ctx.rect(bx, by, boxWidth, boxHeight);
  }
  ctx.fill();
  ctx.strokeStyle = 'rgba(235, 209, 95, 0.6)';
  ctx.lineWidth = 1.2;
  ctx.stroke();

  ctx.fillStyle = '#fbf9f2';
  ctx.font = 'bold 12px system-ui, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.fillText(title, bx + 12, by + 8);

  ctx.fillStyle = badgeColor;
  ctx.font = '11px system-ui, sans-serif';
  ctx.fillText(badge, bx + 12, by + 24);

  ctx.restore();
}

function renderWorldMap() {
  if (!mapCanvas || !mapCtx) return;
  const ctx = mapCtx;
  const width = mapCanvas.width;
  const height = mapCanvas.height;

  // Clear canvas
  ctx.fillStyle = '#1c1714';
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.translate(width / 2 + mapTransform.x, height / 2 + mapTransform.y);
  ctx.scale(mapTransform.scale, mapTransform.scale);
  ctx.translate(-500, -500);

  // 1. Draw Ashenfall Topographical Continent Map
  if (worldMapImgLoaded && worldMapImg.complete && worldMapImg.naturalWidth > 0) {
    ctx.drawImage(worldMapImg, 0, 0, 1000, 1000);
    ctx.strokeStyle = 'rgba(235, 209, 95, 0.4)';
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, 1000, 1000);
  } else {
    ctx.fillStyle = '#221d1a';
    ctx.fillRect(0, 0, 1000, 1000);
    ctx.fillStyle = '#a29a8d';
    ctx.font = '14px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Loading Ashenfall Topographical Map...', 500, 500);
  }

  // 2. Travel Roads / Leyline Pathways (amber trails)
  const regionMap = {};
  for (const reg of mapRegions) {
    regionMap[reg.id] = reg;
  }

  ctx.strokeStyle = 'rgba(235, 209, 95, 0.4)';
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 5]);
  for (const [r1Id, r2Id] of MAP_ROADS) {
    const r1 = regionMap[r1Id];
    const r2 = regionMap[r2Id];
    if (r1 && r2 && r1.x && r1.y && r2.x && r2.y) {
      ctx.beginPath();
      ctx.moveTo(r1.x, r1.y);
      ctx.lineTo(r2.x, r2.y);
      ctx.stroke();
    }
  }
  ctx.setLineDash([]);

  // 3. Canonical Regions
  for (const reg of mapRegions) {
    const rx = reg.x || 500;
    const ry = reg.y || 500;
    const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'region' && mapSelectedTarget.data.id === reg.id;
    const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'region' && mapHoveredTarget.data.id === reg.id;
    const isMatch = !mapSearchQuery || reg.name.toLowerCase().includes(mapSearchQuery) || (reg.biome || '').toLowerCase().includes(mapSearchQuery);

    const theme = BIOME_COLORS[reg.biome] || BIOME_COLORS['Plains'];

    if (isSelected || isHovered) {
      ctx.beginPath();
      ctx.arc(rx, ry, isSelected ? 22 : 18, 0, Math.PI * 2);
      ctx.strokeStyle = isSelected ? '#ebd15f' : '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(rx, ry, 7, 0, Math.PI * 2);
    ctx.fillStyle = isMatch ? theme.stroke : '#4a4039';
    ctx.fill();
    ctx.strokeStyle = '#221d1a';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    if (mapFilterLayer === 'all' || mapFilterLayer === 'weather') {
      const matchWeather = mapWeather.find(w => (w.region || '').toLowerCase().includes(reg.name.toLowerCase()));
      if (matchWeather) {
        ctx.font = '14px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(matchWeather.icon || '☀️', rx, ry - 16);
      }
    }

    if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
      drawMapLabel(ctx, reg.name, rx, ry + 16, '#fbf9f2', 'rgba(34, 29, 26, 0.92)');
    }
  }

  // 4. Boss Arenas & Gateways
  if (mapFilterLayer === 'all' || mapFilterLayer === 'bosses') {
    for (const b of mapBosses) {
      const bw = getBossWorldCoords(b);
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'boss' && mapSelectedTarget.data.name === b.name;
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'boss' && mapHoveredTarget.data.name === b.name;
      const isMatch = !mapSearchQuery || b.name.toLowerCase().includes(mapSearchQuery);

      ctx.save();
      ctx.translate(bw.wx, bw.wy);
      ctx.rotate(Math.PI / 4);

      ctx.beginPath();
      ctx.rect(-8, -8, 16, 16);
      ctx.fillStyle = isMatch ? 'rgba(196, 58, 46, 0.9)' : 'rgba(74, 64, 57, 0.5)';
      ctx.fill();
      ctx.strokeStyle = isSelected ? '#ebd15f' : (isHovered ? '#ffffff' : '#fbe4b0');
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.stroke();
      ctx.restore();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(bw.wx, bw.wy, 18, 0, Math.PI * 2);
        ctx.strokeStyle = '#ebd15f';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, '⚔️ ' + b.name, bw.wx, bw.wy - 18, '#fca5a5', 'rgba(52, 28, 23, 0.92)');
      }
    }
  }

  // 5. Live Loot Chests & Dungeon Caches
  if (mapFilterLayer === 'all' || mapFilterLayer === 'chests') {
    for (let i = 0; i < mapChests.length; i++) {
      const c = mapChests[i];
      const cw = getChestWorldCoords(c, i);
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'chest' && (mapSelectedTarget.data.id === c.id || mapSelectedTarget.data.title === c.title);
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'chest' && (mapHoveredTarget.data.id === c.id || mapHoveredTarget.data.title === c.title);
      const isMatch = !mapSearchQuery || (c.title || c.name || '').toLowerCase().includes(mapSearchQuery);

      const pinColor = c.is_ready ? '#84be5b' : '#ebd15f';

      ctx.beginPath();
      ctx.arc(cw.wx, cw.wy, 6, 0, Math.PI * 2);
      ctx.fillStyle = isMatch ? pinColor : '#4a4039';
      ctx.fill();
      ctx.strokeStyle = '#221d1a';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (!c.is_ready && isMatch) {
        ctx.beginPath();
        ctx.arc(cw.wx, cw.wy, 11, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(235, 209, 95, 0.6)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(cw.wx, cw.wy, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#ebd15f' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        const titleStr = c.title || c.name || 'Chest';
        const labelText = c.is_ready ? `${titleStr} (Ready)` : `${titleStr} (${c.remaining_formatted})`;
        drawMapLabel(ctx, labelText, cw.wx, cw.wy + 15, c.is_ready ? '#84be5b' : '#fbe4b0');
      }
    }
  }

  // 6. Player Death Gravestones
  if (mapFilterLayer === 'all' || mapFilterLayer === 'graves') {
    for (let i = 0; i < mapGraves.length; i++) {
      const g = mapGraves[i];
      const gw = getGraveWorldCoords(g, i);
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'grave' && mapSelectedTarget.data.id === g.id;
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'grave' && mapHoveredTarget.data.id === g.id;
      const isMatch = !mapSearchQuery || g.name.toLowerCase().includes(mapSearchQuery) || (g.zone || '').toLowerCase().includes(mapSearchQuery);

      ctx.beginPath();
      ctx.arc(gw.wx, gw.wy, 6, 0, Math.PI * 2);
      ctx.fillStyle = isMatch ? 'rgba(219, 166, 207, 0.95)' : '#4a4039';
      ctx.fill();
      ctx.strokeStyle = '#221d1a';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(gw.wx, gw.wy, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#ebd15f' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, `🪦 #${g.index} Grave`, gw.wx, gw.wy + 15, '#dba6cf', 'rgba(46, 24, 40, 0.92)');
      }
    }
  }

  // 7. Claimed Player Camps / Bedrolls
  if (mapFilterLayer === 'all' || mapFilterLayer === 'camps') {
    for (let i = 0; i < mapCamps.length; i++) {
      const camp = mapCamps[i];
      const cw = getCampWorldCoords(camp, i);
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'camp' && mapSelectedTarget.data.index === camp.index;
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'camp' && mapHoveredTarget.data.index === camp.index;
      const isMatch = !mapSearchQuery || camp.name.toLowerCase().includes(mapSearchQuery);

      ctx.beginPath();
      ctx.arc(cw.wx, cw.wy, 6, 0, Math.PI * 2);
      ctx.fillStyle = isMatch ? 'rgba(140, 199, 239, 0.95)' : '#4a4039';
      ctx.fill();
      ctx.strokeStyle = '#221d1a';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(cw.wx, cw.wy, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#ebd15f' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, `⛺ #${camp.index} Camp`, cw.wx, cw.wy + 15, '#8cc7ef', 'rgba(26, 42, 58, 0.92)');
      }
    }
  }

  // 8. Fishing Spots (Net & Rod)
  if (mapFilterLayer === 'all' || mapFilterLayer === 'fishing') {
    for (const f of mapFishing) {
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'fishing' && mapSelectedTarget.data.id === f.id;
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'fishing' && mapHoveredTarget.data.id === f.id;
      const isMatch = !mapSearchQuery || f.title.toLowerCase().includes(mapSearchQuery) || f.cell.toLowerCase().includes(mapSearchQuery);

      ctx.beginPath();
      ctx.arc(f.map_coords.x, f.map_coords.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = isMatch ? '#8cc7ef' : '#4a4039';
      ctx.fill();
      ctx.strokeStyle = '#221d1a';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(f.map_coords.x, f.map_coords.y, 10, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(140, 199, 239, 0.45)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(f.map_coords.x, f.map_coords.y, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#ebd15f' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, '🎣 ' + f.title, f.map_coords.x, f.map_coords.y + 15, '#8cc7ef', 'rgba(26, 42, 58, 0.92)');
      }
    }
  }

  // 9. Interactive NPCs & Quest Givers
  if (mapFilterLayer === 'all' || mapFilterLayer === 'npcs') {
    for (const n of mapNPCs) {
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'npc' && mapSelectedTarget.data.id === n.id;
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'npc' && mapHoveredTarget.data.id === n.id;
      const isMatch = !mapSearchQuery || n.title.toLowerCase().includes(mapSearchQuery) || n.cell.toLowerCase().includes(mapSearchQuery);

      ctx.beginPath();
      ctx.arc(n.map_coords.x, n.map_coords.y, 7, 0, Math.PI * 2);
      ctx.fillStyle = isMatch ? '#ebd15f' : '#4a4039';
      ctx.fill();
      ctx.strokeStyle = '#221d1a';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(n.map_coords.x, n.map_coords.y, 11, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(235, 209, 95, 0.55)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(n.map_coords.x, n.map_coords.y, 16, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#ebd15f' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.25) && isMatch) {
        drawMapLabel(ctx, '👤 ' + n.title, n.map_coords.x, n.map_coords.y + 16, '#fbe4b0', 'rgba(58, 42, 20, 0.92)');
      }
    }
  }

  // 10. Shrines & Sacred Relics
  if (mapFilterLayer === 'all' || mapFilterLayer === 'shrines') {
    for (const s of mapShrines) {
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'shrine' && mapSelectedTarget.data.id === s.id;
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'shrine' && mapHoveredTarget.data.id === s.id;
      const isMatch = !mapSearchQuery || s.title.toLowerCase().includes(mapSearchQuery);

      ctx.beginPath();
      ctx.arc(s.map_coords.x, s.map_coords.y, 7, 0, Math.PI * 2);
      ctx.fillStyle = isMatch ? '#dba6cf' : '#4a4039';
      ctx.fill();
      ctx.strokeStyle = '#221d1a';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(s.map_coords.x, s.map_coords.y, 16, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#ebd15f' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.25) && isMatch) {
        drawMapLabel(ctx, '✨ ' + s.title, s.map_coords.x, s.map_coords.y + 16, '#dba6cf', 'rgba(46, 24, 40, 0.92)');
      }
    }
  }

  ctx.restore();

  // 8. Compass Rose Indicator in Top-Right
  drawCompassRose(ctx, width - 42, 42);

  // 9. Floating Hover Tooltip
  if (mapHoveredTarget && !mapIsDragging) {
    drawHoverTooltip(ctx, mapHoveredTarget, mapMousePos.x, mapMousePos.y);
  }
}

// ----------------- REFRESH LOOPS -----------------
async function refreshAll() {
  await loadStatus();
  await loadLeaderboard();
  await loadSaveFiles();
  await loadRespawns();
  if (currentTab === 'map') await refreshMapData();
  if (currentTab === 'farming') await loadFarming();
  if (currentTab === 'bosses') {
    await loadBosses();
    await loadLiveWorldEvents();
  }
  if (currentTab === 'players') await loadRoster();
  if (currentTab === 'logs' && isLive) {
    await fetchLogs();
  }
}

// Initial hash support
const hash = (window.location.hash || '').replace('#', '');
if (['overview', 'map', 'respawns', 'farming', 'items', 'bosses', 'players', 'backups', 'leaderboard', 'events', 'logs'].includes(hash)) {
  setTab(hash);
} else {
  setTab('overview');
}

refreshAll();
setInterval(loadStatus, 1000);
setInterval(() => {
  if (currentTab === 'map') {
    refreshMapData().then(() => renderWorldMap());
  }
  if (currentTab === 'respawns') {
    loadRespawns();
  }
  if (currentTab === 'farming') {
    loadFarming();
  }
  if (currentTab === 'bosses') {
    loadBosses();
    loadLiveWorldEvents();
  }
  if (currentTab === 'logs' && isLive) {
    fetchLogs();
  }
}, 2000);

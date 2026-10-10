from flask import Flask, jsonify, request
import os
import re
from datetime import datetime
from collections import deque
import config
from database import init_db
from state import get_state
from monitor import start_monitor
from dockerstats import start_dockerstats
from savewatcher import start_savewatcher
from database import get_leaderboard


app = Flask(__name__)


def get_logs_dir():
    if config.LOG_PATH and os.path.exists(config.LOG_PATH):
        return os.path.dirname(config.LOG_PATH)
    if os.path.exists("/logs"):
        return "/logs"
    if os.path.exists(r"C:\DragonwildsServer\RSDragonwilds\Saved\Logs"):
        return r"C:\DragonwildsServer\RSDragonwilds\Saved\Logs"
    return "."


def format_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


@app.route("/status")
def status():
    return jsonify(get_state())


@app.route("/leaderboard")
def leaderboard():
    return jsonify(get_leaderboard())


@app.route("/api/log-files")
def api_log_files():
    logs_dir = get_logs_dir()
    files = []
    if os.path.exists(logs_dir):
        for f in os.listdir(logs_dir):
            if f.endswith(".log"):
                path = os.path.join(logs_dir, f)
                try:
                    stat = os.stat(path)
                    is_live = (f == "RSDragonwilds.log")
                    files.append({
                        "name": f,
                        "size": format_size(stat.st_size),
                        "mtime": stat.st_mtime,
                        "live": is_live
                    })
                except Exception:
                    pass
    files.sort(key=lambda x: (not x["live"], -x["mtime"]))
    return jsonify(files)


@app.route("/api/logs")
def api_logs():
    filename = request.args.get("file", "RSDragonwilds.log")
    lines_count = int(request.args.get("lines", 300))
    offset = int(request.args.get("offset", 0))
    level_filter = request.args.get("level", "all").lower()
    search_query = request.args.get("search", "").lower()
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()

    safe_name = os.path.basename(filename)
    logs_dir = get_logs_dir()
    file_path = os.path.join(logs_dir, safe_name)

    if not os.path.exists(file_path):
        return jsonify({"lines": [], "error": f"File {safe_name} not found"}), 404

    try:
        stat = os.stat(file_path)
        total_fetch = lines_count + offset

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            if offset > 0:
                raw_chunk = list(deque(f, maxlen=total_fetch))
                raw_lines = raw_chunk[:len(raw_chunk) - offset]
                raw_lines = raw_lines[-lines_count:]
            else:
                raw_lines = list(deque(f, maxlen=lines_count))

        filtered = []
        for line in raw_lines:
            line_str = line.rstrip("\r\n")
            if not line_str:
                continue

            # Level filter (All, Error, Warning, Display, Log, Verbose)
            if level_filter == "error":
                if not re.search(r"\b(error|fatal|exception)\b", line_str, re.IGNORECASE):
                    continue
            elif level_filter == "warning":
                if not re.search(r"\bwarning\b", line_str, re.IGNORECASE):
                    continue
            elif level_filter == "display":
                if not re.search(r"\bdisplay:\b", line_str, re.IGNORECASE):
                    continue
            elif level_filter == "log":
                if not re.search(r"\b(log|info):\b", line_str, re.IGNORECASE):
                    continue
            elif level_filter == "verbose":
                if not re.search(r"\bverbose:\b", line_str, re.IGNORECASE):
                    continue

            # Search text filter
            if search_query and search_query not in line_str.lower():
                continue

            # Optional date filter: parses [YYYY.MM.DD or [YYYY-MM-DD
            if from_date or to_date:
                ts_m = re.search(r"\[(\d{4})[\.\-](\d{2})[\.\-](\d{2})", line_str)
                if ts_m:
                    line_date = f"{ts_m.group(1)}-{ts_m.group(2)}-{ts_m.group(3)}"
                    if from_date and line_date < from_date:
                        continue
                    if to_date and line_date > to_date:
                        continue

            filtered.append(line_str)

        return jsonify({
            "file": safe_name,
            "size": format_size(stat.st_size),
            "lines": filtered,
            "count": len(filtered)
        })

    except Exception as e:
        return jsonify({"lines": [], "error": str(e)}), 500


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Dragonwilds Companion</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * { box-sizing: border-box; }
    body { margin:0; background:#070b14; color:#e5e7eb; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
    .layout { display:flex; min-height:100vh; }
    
    /* Sidebar */
    .sidebar { width:225px; background:#0c1322; padding:24px 16px; border-right:1px solid #1a2538; flex-shrink:0; }
    .brand { color:#f59e0b; font-size:20px; font-weight:bold; margin-bottom:28px; line-height:1.2; display:flex; align-items:center; }
    .brand .logo { width:36px; height:36px; background:#f59e0b; color:#0f172a; border-radius:10px; display:inline-flex; align-items:center; justify-content:center; font-weight:bold; margin-right:10px; flex-shrink:0; font-size:16px; }
    
    .nav { display:flex; flex-direction:column; gap:6px; }
    .nav a { display:flex; align-items:center; justify-content:space-between; color:#94a3b8; text-decoration:none; padding:11px 16px; border-radius:10px; cursor:pointer; font-weight:500; font-size:14px; transition:all 0.15s ease; }
    .nav a:hover { background:#172236; color:#ffffff; }
    .nav a.active { background:#e65100; color:#ffffff; font-weight:600; box-shadow:0 4px 14px rgba(230,81,0,0.3); }
    .nav a .badge { background:#1e293b; color:#f59e0b; font-size:11px; padding:2px 7px; border-radius:10px; font-weight:bold; }
    .nav a.active .badge { background:rgba(0,0,0,0.25); color:#fff; }
    
    .sidebar hr { border:0; border-top:1px solid #1a2538; margin:14px 0; }
    
    /* Content Area */
    .content { flex:1; padding:26px 32px; max-width:1440px; }
    .topbar { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:24px; flex-wrap:wrap; gap:16px; }
    h1 { margin:0; color:#ffffff; font-size:26px; font-weight:bold; }
    .subtitle { color:#94a3b8; font-size:14px; margin-top:4px; }
    .topbar-right { display:flex; flex-direction:column; align-items:flex-end; gap:4px; }
    .status-indicator { display:flex; align-items:center; color:#22c55e; font-weight:bold; font-size:14px; }
    .status-dot { width:8px; height:8px; border-radius:50%; background:#22c55e; margin-right:8px; display:inline-block; }
    .status-dot.offline { background:#ef4444; }
    .status-indicator.offline { color:#ef4444; }
    .updated-text { color:#94a3b8; font-size:13px; }

    /* Mobile Nav */
    .mobile-nav { display:none; overflow-x:auto; gap:8px; margin-bottom:18px; padding-bottom:4px; }
    .mobile-nav a { padding:8px 14px; background:#131c2e; border:1px solid #1e2c45; color:#cbd5e1; border-radius:8px; font-size:13px; text-decoration:none; white-space:nowrap; cursor:pointer; }
    .mobile-nav a.active { background:#e65100; color:#white; border-color:#e65100; font-weight:bold; }

    /* 8 Stat Cards Grid */
    .grid { display:grid; grid-template-columns:repeat(4,minmax(180px,1fr)); gap:16px; margin-bottom:22px; }
    .card { background:#111a2d; border:1px solid #1c283f; border-radius:14px; padding:18px 20px; box-shadow:0 8px 24px rgba(0,0,0,0.3); }
    .card .icon { width:36px; height:36px; border-radius:10px; background:#19253d; display:flex; align-items:center; justify-content:center; color:#f59e0b; font-weight:bold; font-size:13px; margin-bottom:12px; }
    .card .label { color:#94a3b8; font-size:13px; margin-bottom:6px; font-weight:500; }
    .card .value { font-size:22px; font-weight:bold; color:#f8fafc; word-break:break-word; }
    
    /* 2 Columns Grid for Overview Bottom */
    .overview-split { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:22px; }
    .overview-split h2 { margin:0; font-size:18px; font-weight:bold; color:#fff; }
    
    /* Recent Events Controls */
    .events-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; flex-wrap:wrap; gap:8px; }
    .pill-group { display:inline-flex; background:#0c1322; border:1px solid #1c283f; border-radius:8px; padding:3px; gap:4px; }
    .pill-btn { background:transparent; border:none; color:#94a3b8; padding:5px 12px; border-radius:6px; font-size:12px; font-weight:500; cursor:pointer; transition:all 0.15s; }
    .pill-btn:hover { color:#fff; }
    .pill-btn.active { background:#e65100; color:#fff; font-weight:600; }
    
    .select-sm { background:#0c1322; border:1px solid #1c283f; color:#94a3b8; padding:5px 10px; border-radius:6px; font-size:12px; cursor:pointer; }
    
    .event-item { padding:10px 0; border-bottom:1px solid #1a2538; font-size:14px; display:flex; align-items:center; }
    .event-item:last-child { border-bottom:none; }
    .event-time { color:#94a3b8; margin-right:8px; font-family:monospace; font-size:13px; }
    .event-tag { color:#94a3b8; margin-right:8px; font-size:13px; font-weight:500; }
    .event-tag.user { color:#38bdf8; }
    .event-tag.server { color:#94a3b8; }
    .event-tag.dragon { color:#f59e0b; }
    .event-msg { color:#e2e8f0; }

    /* Pagination */
    .pagination { display:flex; align-items:center; justify-content:center; gap:14px; margin-top:16px; padding-top:12px; border-top:1px solid #1a2538; font-size:13px; color:#94a3b8; }
    .pg-btn { background:#162238; border:1px solid #22324e; color:#cbd5e1; padding:4px 12px; border-radius:6px; cursor:pointer; font-size:12px; }
    .pg-btn:disabled { opacity:0.4; cursor:not-allowed; }
    .pg-btn:hover:not(:disabled) { background:#22324e; color:#fff; }

    /* Leaderboard Table */
    table { width:100%; border-collapse:collapse; margin-top:8px; }
    th, td { padding:12px 8px; border-bottom:1px solid #1a2538; text-align:left; font-size:14px; }
    th { color:#94a3b8; font-weight:normal; font-size:13px; }
    
    /* Server Logs View Styling */
    .logs-toolbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; flex-wrap:wrap; gap:12px; }
    .logs-toolbar-left { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
    .logs-toolbar-right { display:flex; align-items:center; gap:10px; }
    
    .select-log-file { background:#0c1322; border:1px solid #1e2c45; color:#f8fafc; padding:8px 12px; border-radius:8px; font-size:13px; font-weight:500; cursor:pointer; min-width:260px; }
    
    .search-input { background:#0c1322; border:1px solid #1e2c45; color:#f8fafc; padding:7px 12px; border-radius:8px; font-size:13px; width:180px; }
    .search-input:focus { outline:none; border-color:#e65100; }
    
    .date-input { background:#0c1322; border:1px solid #1e2c45; color:#94a3b8; padding:6px 10px; border-radius:8px; font-size:12px; width:125px; }
    .date-input:focus { outline:none; border-color:#e65100; }
    
    .btn-live { display:inline-flex; align-items:center; gap:6px; background:#059669; color:#fff; border:none; padding:7px 14px; border-radius:8px; font-size:13px; font-weight:bold; cursor:pointer; }
    .btn-live.off { background:#374151; color:#9ca3af; }
    .btn-live .dot { width:8px; height:8px; border-radius:50%; background:#fff; display:inline-block; }
    
    .btn-load-older { display:block; margin:0 auto 12px auto; background:#162238; border:1px solid #22324e; color:#cbd5e1; padding:6px 18px; border-radius:8px; font-size:12px; cursor:pointer; }
    .btn-load-older:hover { background:#22324e; color:#fff; }
    
    .terminal-container { background:#060b16; border:1px solid #18243a; border-radius:12px; padding:16px; font-family:Consolas, "Cascadia Code", Menlo, monospace; font-size:12.5px; line-height:1.6; height:600px; overflow-y:auto; white-space:pre-wrap; word-break:break-all; }
    
    /* Terminal Log Formatting */
    .log-line { padding:1px 0; }
    .log-ts { color:#64748b; margin-right:6px; }
    .log-channel { color:#38bdf8; font-weight:500; margin-right:6px; }
    .log-level-error { color:#ef4444; font-weight:bold; }
    .log-level-warn { color:#fbbf24; font-weight:bold; }
    .log-level-disp { color:#e2e8f0; }
    .log-level-verb { color:#94a3b8; }
    .log-body { color:#cbd5e1; }
    
    /* Players Section */
    .player-row { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border:1px solid #1c283f; border-radius:12px; margin-bottom:10px; background:#0c1322; }
    .player-left { display:flex; align-items:center; }
    .avatar { width:38px; height:38px; border-radius:50%; background:#19253d; color:#22c55e; display:flex; align-items:center; justify-content:center; font-weight:bold; margin-right:12px; font-size:15px; }
    .badge-online { background:#064e3b; color:#34d399; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:bold; }
    
    @media(max-width:1100px){
      .grid { grid-template-columns:repeat(2,1fr); }
      .overview-split { grid-template-columns:1fr; }
      .sidebar { display:none; }
      .mobile-nav { display:flex; }
      .content { padding:20px 16px; }
    }
    @media(max-width:640px){
      .grid { grid-template-columns:1fr; }
      .logs-toolbar { flex-direction:column; align-items:stretch; }
    }
  </style>
</head>
<body>
<div class="layout">
  <!-- Left Sidebar -->
  <aside class="sidebar">
    <div class="brand">
      <span class="logo">DW</span>
      <span>Dragonwilds<br>Companion</span>
    </div>
    <div class="nav">
      <a class="nav-link active" data-tab="overview" onclick="setTab('overview')">Overview</a>
      <a class="nav-link" data-tab="players" onclick="setTab('players')">
        <span>Players</span>
        <span class="badge" id="nav-players-count">0</span>
      </a>
      <a class="nav-link" data-tab="leaderboard" onclick="setTab('leaderboard')">Leaderboard</a>
      <a class="nav-link" data-tab="events" onclick="setTab('events')">Events</a>
      <a class="nav-link" data-tab="logs" onclick="setTab('logs')">Logs</a>
      <hr>
      <a href="/status" target="_blank">
        <span>API Status</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/leaderboard" target="_blank">
        <span>API Leaderboard</span>
        <span style="font-size:11px;">↗</span>
      </a>
    </div>
  </aside>

  <!-- Main Content -->
  <main class="content">
    <!-- Topbar -->
    <div class="topbar">
      <div>
        <h1 id="page-title">Overview</h1>
        <div class="subtitle" id="page-subtitle">Real-time overview of your Dragonwilds server</div>
      </div>
      <div class="topbar-right">
        <div id="server-indicator" class="status-indicator">
          <span class="status-dot" id="server-dot"></span>
          <span id="server-status-label">Server Online</span>
        </div>
        <div class="updated-text">Updated: <span id="updated-time">--:--:--</span></div>
      </div>
    </div>

    <!-- Mobile Navigation -->
    <div class="mobile-nav">
      <a class="mobile-link active" data-tab="overview" onclick="setTab('overview')">Overview</a>
      <a class="mobile-link" data-tab="players" onclick="setTab('players')">Players</a>
      <a class="mobile-link" data-tab="leaderboard" onclick="setTab('leaderboard')">Leaderboard</a>
      <a class="mobile-link" data-tab="events" onclick="setTab('events')">Events</a>
      <a class="mobile-link" data-tab="logs" onclick="setTab('logs')">Logs</a>
    </div>

    <!-- VIEW 1: OVERVIEW -->
    <div id="view-overview">
      <!-- 8 Stat Cards -->
      <div class="grid">
        <div class="card"><div class="icon">PL</div><div class="label">Players</div><div class="value" id="stat-players">0 / 6</div></div>
        <div class="card"><div class="icon">NM</div><div class="label">Names</div><div class="value" id="names" style="font-size:18px;">None</div></div>
        <div class="card"><div class="icon">WD</div><div class="label">World</div><div class="value" id="world" style="font-size:18px;">...</div></div>
        <div class="card"><div class="icon">UP</div><div class="label">Uptime</div><div class="value" id="uptime">...</div></div>
        <div class="card"><div class="icon">SV</div><div class="label">Last Save</div><div class="value" id="save">...</div></div>
        <div class="card"><div class="icon">CPU</div><div class="label">CPU</div><div class="value" id="cpu">N/A</div></div>
        <div class="card"><div class="icon">RAM</div><div class="label">RAM</div><div class="value" id="ram">N/A</div></div>
        <div class="card"><div class="icon">VER</div><div class="label">Version</div><div class="value" id="version" style="font-size:18px;">...</div></div>
      </div>

      <!-- Split Bottom Row: Recent Events & Leaderboard -->
      <div class="overview-split">
        <!-- Recent Events Card -->
        <div class="card">
          <div class="events-header">
            <h2>Recent Events</h2>
            <div style="display:flex; align-items:center; gap:8px;">
              <div class="pill-group">
                <button class="pill-btn active" onclick="setEventFilter('all', this)">All</button>
                <button class="pill-btn" onclick="setEventFilter('user', this)">User</button>
                <button class="pill-btn" onclick="setEventFilter('server', this)">Server</button>
                <button class="pill-btn" onclick="setEventFilter('dragon', this)">Dragon</button>
              </div>
              <select class="select-sm" id="events-per-page" onchange="changeEventsPerPage(this.value)">
                <option value="10" selected>10 / page</option>
                <option value="20">20 / page</option>
                <option value="50">50 / page</option>
              </select>
            </div>
          </div>
          <div id="events-list-container">Loading events...</div>
          <div class="pagination" id="events-pagination">
            <button class="pg-btn" id="pg-prev" onclick="prevEventsPage()">« Prev</button>
            <span id="pg-info">Page 1 of 1</span>
            <button class="pg-btn" id="pg-next" onclick="nextEventsPage()">Next »</button>
          </div>
        </div>

        <!-- Leaderboard Card -->
        <div class="card">
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;">
            <h2>Leaderboard <span style="font-size:12px; background:#1e293b; color:#f59e0b; padding:3px 8px; border-radius:999px; margin-left:6px;">Top 10</span></h2>
          </div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Player</th>
                <th>Playtime</th>
                <th>Sessions</th>
                <th>Longest</th>
              </tr>
            </thead>
            <tbody id="leaderboard-body">
              <tr><td colspan="5" style="color:#94a3b8; text-align:center; padding:18px;">No completed sessions yet</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- VIEW 2: SERVER LOGS (Screenshot 2) -->
    <div id="view-logs" style="display:none;">
      <div class="card">
        <!-- Logs Toolbar -->
        <div class="logs-toolbar">
          <div class="logs-toolbar-left">
            <select class="select-log-file" id="log-file-select" onchange="switchLogFile(this.value)">
              <option value="RSDragonwilds.log">RSDragonwilds.log - live</option>
            </select>

            <div class="pill-group">
              <button class="pill-btn active" onclick="setLogLevel('all', this)">All</button>
              <button class="pill-btn" onclick="setLogLevel('error', this)">Error</button>
              <button class="pill-btn" onclick="setLogLevel('warning', this)">Warning</button>
              <button class="pill-btn" onclick="setLogLevel('display', this)">Display</button>
              <button class="pill-btn" onclick="setLogLevel('log', this)">Log</button>
              <button class="pill-btn" onclick="setLogLevel('verbose', this)">Verbose</button>
            </div>

            <input type="text" class="search-input" id="log-search-input" placeholder="Search logs..." oninput="handleLogSearch()">
            
            <input type="date" class="date-input" id="log-from-date" onchange="fetchLogs()">
            <input type="date" class="date-input" id="log-to-date" onchange="fetchLogs()">
            <button class="pg-btn" style="padding:5px 8px;" onclick="clearDateFilter()" title="Clear dates">✕</button>
          </div>

          <div class="logs-toolbar-right">
            <button class="btn-live" id="btn-live-toggle" onclick="toggleLive()">
              <span class="dot"></span>
              <span id="live-label">Live: on</span>
            </button>
          </div>
        </div>

        <button class="btn-load-older" onclick="loadOlderLogs()">Load older</button>

        <!-- Terminal Window -->
        <div class="terminal-container" id="log-terminal">
          <div style="color:#64748b;">Connecting to live server log stream...</div>
        </div>
      </div>
    </div>

    <!-- VIEW 3: PLAYERS -->
    <div id="view-players" style="display:none;">
      <div class="card">
        <h2 style="margin-bottom:18px;">Current Connected Players</h2>
        <div id="current-players-list">Loading players...</div>
      </div>
    </div>

    <!-- VIEW 4: LEADERBOARD FULL -->
    <div id="view-leaderboard" style="display:none;">
      <div class="card">
        <h2 style="margin-bottom:18px;">Leaderboard - Top Player Playtimes</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Player</th>
              <th>Playtime</th>
              <th>Sessions</th>
              <th>Longest Session</th>
            </tr>
          </thead>
          <tbody id="full-leaderboard-body">
            <tr><td colspan="5" style="color:#94a3b8; text-align:center; padding:24px;">No session history yet</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- VIEW 5: EVENTS FULL -->
    <div id="view-events" style="display:none;">
      <div class="card">
        <div class="events-header">
          <h2>Server & Player Events</h2>
          <div class="pill-group">
            <button class="pill-btn active" onclick="setEventFilter('all', this)">All</button>
            <button class="pill-btn" onclick="setEventFilter('user', this)">User</button>
            <button class="pill-btn" onclick="setEventFilter('server', this)">Server</button>
            <button class="pill-btn" onclick="setEventFilter('dragon', this)">Dragon</button>
          </div>
        </div>
        <div id="full-events-list">Loading events...</div>
      </div>
    </div>
  </main>
</div>

<script>
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
let liveTimer = null;

// Tab Switcher
function setTab(tab) {
  currentTab = tab;
  try { history.replaceState(null, null, '#' + tab); } catch(e){}

  document.querySelectorAll('.nav-link, .mobile-link').forEach(el => {
    if (el.dataset.tab === tab) el.classList.add('active');
    else el.classList.remove('active');
  });

  const title = document.getElementById('page-title');
  const subtitle = document.getElementById('page-subtitle');
  const vOverview = document.getElementById('view-overview');
  const vLogs = document.getElementById('view-logs');
  const vPlayers = document.getElementById('view-players');
  const vLeaderboard = document.getElementById('view-leaderboard');
  const vEvents = document.getElementById('view-events');

  vOverview.style.display = 'none';
  vLogs.style.display = 'none';
  vPlayers.style.display = 'none';
  vLeaderboard.style.display = 'none';
  vEvents.style.display = 'none';

  if (tab === 'overview') {
    title.innerText = 'Overview';
    subtitle.innerText = 'Real-time overview of your Dragonwilds server';
    vOverview.style.display = 'block';
  } else if (tab === 'logs') {
    title.innerText = 'Server Logs';
    subtitle.innerText = 'Stream, filter and search RSDragonwilds server logs';
    vLogs.style.display = 'block';
    fetchLogFiles();
    fetchLogs();
  } else if (tab === 'players') {
    title.innerText = 'Players';
    subtitle.innerText = 'Active players currently in-game';
    vPlayers.style.display = 'block';
  } else if (tab === 'leaderboard') {
    title.innerText = 'Leaderboard';
    subtitle.innerText = 'Player playtime rankings & sessions';
    vLeaderboard.style.display = 'block';
  } else if (tab === 'events') {
    title.innerText = 'Events';
    subtitle.innerText = 'Server activity & event timeline';
    vEvents.style.display = 'block';
  }
}

// ----------------- OVERVIEW STATUS & EVENTS -----------------
async function loadStatus() {
  try {
    const res = await fetch('/status');
    const s = await res.json();

    document.getElementById('stat-players').innerText = `${s.players_online} / ${s.max_players}`;
    document.getElementById('nav-players-count').innerText = s.players_online;
    document.getElementById('names').innerText = s.players_text || 'None';
    document.getElementById('world').innerText = s.world || 'Unknown';
    document.getElementById('uptime').innerText = s.uptime || 'Unknown';
    document.getElementById('save').innerText = s.last_save || 'Unknown';
    document.getElementById('cpu').innerText = s.cpu || 'N/A';
    document.getElementById('ram').innerText = s.memory || 'N/A';
    document.getElementById('version').innerText = s.version || 'Unknown';
    document.getElementById('updated-time').innerText = new Date().toLocaleTimeString();

    const dot = document.getElementById('server-dot');
    const label = document.getElementById('server-status-label');
    const ind = document.getElementById('server-indicator');

    if (s.status === 'online') {
      dot.className = 'status-dot';
      ind.className = 'status-indicator';
      label.innerText = 'Server Online';
    } else {
      dot.className = 'status-dot offline';
      ind.className = 'status-indicator offline';
      label.innerText = 'Server Offline';
    }

    // Events caching
    allEvents = s.events || [];
    renderEvents();

    // Players list view
    const pContainer = document.getElementById('current-players-list');
    pContainer.innerHTML = '';
    if (!s.players || s.players.length === 0) {
      pContainer.innerHTML = '<div style="color:#94a3b8; padding:16px 0;">No players currently connected.</div>';
    } else {
      s.players.forEach(p => {
        const div = document.createElement('div');
        div.className = 'player-row';
        div.innerHTML = `
          <div class="player-left">
            <div class="avatar">${(p||'?')[0].toUpperCase()}</div>
            <div>
              <div style="font-weight:bold; color:#fff;">${p}</div>
              <div style="font-size:12px; color:#94a3b8;">Connected to ${s.world||'World'}</div>
            </div>
          </div>
          <div class="badge-online">Online</div>
        `;
        pContainer.appendChild(div);
      });
    }

  } catch (err) {
    console.error('Status fetch error:', err);
  }
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
      return '<div style="color:#64748b; padding:18px 0;">No events match filter.</div>';
    }
    return items.map(e => `
      <div class="event-item">
        <span class="event-time">[${e.timestamp}]</span>
        <span class="event-tag ${e.category}">[${e.category}]</span>
        <span class="event-msg">${e.message}</span>
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
        return '<tr><td colspan="5" style="color:#94a3b8; text-align:center; padding:18px;">No completed sessions yet</td></tr>';
      }
      return r.map((row, idx) => `
        <tr>
          <td>${idx + 1}</td>
          <td><strong>${row.player}</strong></td>
          <td>${row.playtime}</td>
          <td>${row.sessions}</td>
          <td>${row.longest_session}</td>
        </tr>
      `).join('');
    };

    if (body) body.innerHTML = renderRows(rows);
    if (fullBody) fullBody.innerHTML = renderRows(rows);
  } catch(e) {}
}

// ----------------- SERVER LOGS (SCREENSHOT 2) -----------------
async function fetchLogFiles() {
  try {
    const res = await fetch('/api/log-files');
    const files = await res.json();
    const sel = document.getElementById('log-file-select');
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
  document.getElementById('log-from-date').value = '';
  document.getElementById('log-to-date').value = '';
  fetchLogs();
}

function toggleLive() {
  isLive = !isLive;
  const btn = document.getElementById('btn-live-toggle');
  const label = document.getElementById('live-label');
  if (isLive) {
    btn.className = 'btn-live';
    label.innerText = 'Live: on';
  } else {
    btn.className = 'btn-live off';
    label.innerText = 'Live: off';
  }
}

function loadOlderLogs() {
  logOffset += 200;
  fetchLogs(true);
}

async function fetchLogs(isOlderAppend = false) {
  try {
    const q = document.getElementById('log-search-input').value.trim();
    const fromD = document.getElementById('log-from-date').value;
    const toD = document.getElementById('log-to-date').value;

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
  if (rawLogLines.length === 0) {
    term.innerHTML = '<div style="color:#64748b; padding:20px; text-align:center;">No matching log entries found.</div>';
    return;
  }

  const html = rawLogLines.map(line => {
    // Parse: [Timestamp][Index]Channel: Level: Message
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

    // Detect channel (e.g. LogPersistence:, LogSpudData:, DominionCombatMode:)
    const chMatch = rest.match(/^([A-Za-z0-9_]+:)\s*(.*)$/);
    if (chMatch) {
      channel = chMatch[1];
      body = chMatch[2];
    }

    // Detect error / warning / verbose / display
    if (/error:/i.test(body) || /fatal:/i.test(body) || /exception:/i.test(body)) {
      levelClass = 'log-level-error';
    } else if (/warning:/i.test(body)) {
      levelClass = 'log-level-warn';
    } else if (/verbose:/i.test(body)) {
      levelClass = 'log-level-verb';
    } else if (/display:/i.test(body)) {
      levelClass = 'log-level-disp';
    }

    // Escape HTML
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

// ----------------- REFRESH LOOPS -----------------
async function refreshAll() {
  await loadStatus();
  await loadLeaderboard();
  if (currentTab === 'logs' && isLive) {
    await fetchLogs();
  }
}

// Initial hash support
const hash = (window.location.hash || '').replace('#', '');
if (['overview', 'players', 'leaderboard', 'events', 'logs'].includes(hash)) {
  setTab(hash);
} else {
  setTab('overview');
}

refreshAll();
setInterval(loadStatus, 4000);
setInterval(() => {
  if (currentTab === 'logs' && isLive) {
    fetchLogs();
  }
}, 2000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    init_db()
    start_monitor()
    start_dockerstats()
    start_savewatcher()

    app.run(
        host="0.0.0.0",
        port=config.PORT
    )
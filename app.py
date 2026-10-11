from flask import Flask, jsonify, request, send_from_directory, abort
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


@app.route("/api/weather")
def api_weather():
    from worldreader import get_world_data
    wdata = get_world_data()
    return jsonify({
        "day_count": wdata.get("day_count", 0),
        "weather": wdata.get("weather", [])
    })


@app.route("/api/world/regions")
def api_world_regions():
    from worldreader import get_canonical_regions
    return jsonify(get_canonical_regions())


@app.route("/api/respawns")
def api_respawns():
    from respawns import get_respawn_tracker
    category = request.args.get("category", "all")
    search = request.args.get("search", "").strip()
    tracker = get_respawn_tracker()
    return jsonify(tracker.get_respawns(category_filter=category, search_query=search))


@app.route("/api/farming")
def api_farming():
    from farming import get_farming_status
    return jsonify(get_farming_status())


@app.route("/api/items")
def api_items():
    from items import get_master_items
    category = request.args.get("category", "all")
    search = request.args.get("search", "").strip()
    return jsonify(get_master_items(category=category, search_query=search))


@app.route("/api/roster")
def api_roster():
    st = get_state()
    return jsonify(st.get("roster", []))


@app.route("/api/save-files")
def api_save_files():
    from worldreader import get_save_files_list
    return jsonify(get_save_files_list())


@app.route("/api/save-files/download/<path:filename>")
def api_download_save(filename):
    safe_name = os.path.basename(filename.replace("\\", "/"))
    if not (safe_name.endswith(".sav") or safe_name.endswith(".sav.backup")):
        abort(400, description="Invalid save file extension")
    save_dir = config.SAVE_PATH if config.SAVE_PATH and os.path.exists(config.SAVE_PATH) else None
    if not save_dir:
        abort(404, description="Save directory not configured")
    full_path = os.path.join(save_dir, safe_name)
    if not os.path.exists(full_path):
        abort(404, description="File not found")
    return send_from_directory(save_dir, safe_name, as_attachment=True)


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
    return r"""
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
    
    /* Data Source Badges (Transparency for Live vs Saved Data) */
    .data-source-badge { display:inline-flex; align-items:center; gap:4px; font-size:10.5px; font-weight:600; padding:2px 8px; border-radius:9999px; text-transform:uppercase; letter-spacing:0.04em; margin-top:6px; cursor:help; }
    .data-source-badge.saved { background:rgba(245,158,11,0.12); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); }
    .data-source-badge.live { background:rgba(34,197,94,0.12); color:#22c55e; border:1px solid rgba(34,197,94,0.3); }
    
    /* Day / Night Dial Widget */
    .day-night-card { background:#111a2d; border:1px solid #1c283f; border-radius:14px; padding:20px; box-shadow:0 8px 24px rgba(0,0,0,0.3); margin-bottom:22px; }
    .day-night-layout { display:flex; align-items:center; gap:26px; flex-wrap:wrap; }
    .dial-svg-wrapper { width:120px; height:120px; flex-shrink:0; position:relative; }
    .day-night-clock-svg { width:100%; height:100%; filter:drop-shadow(0 6px 16px rgba(0,0,0,0.6)); }
    .dial-info { flex:1; min-width:240px; }
    .dial-phase-title { font-size:20px; font-weight:bold; color:#f8fafc; display:flex; align-items:center; gap:8px; margin-bottom:4px; }
    .dial-progress-bar-bg { width:100%; height:8px; background:#1a2538; border-radius:9999px; overflow:hidden; margin:10px 0 6px 0; }
    .dial-progress-bar-fill { height:100%; background:linear-gradient(90deg, #f59e0b, #e65100); border-radius:9999px; transition:width 1s linear; }
    .dial-meta-row { display:flex; justify-content:space-between; align-items:center; font-size:12.5px; color:#94a3b8; }
    
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
      #weather-grid { grid-template-columns:repeat(2,1fr) !important; }
      .overview-split { grid-template-columns:1fr; }
      .sidebar { display:none; }
      .mobile-nav { display:flex; }
      .content { padding:20px 16px; }
    }
    @media(max-width:640px){
      .grid { grid-template-columns:1fr; }
      #weather-grid { grid-template-columns:1fr !important; }
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
      <a class="nav-link" data-tab="respawns" onclick="setTab('respawns')">
        <span>Respawns</span>
        <span class="badge" id="nav-respawns-count">0</span>
      </a>
      <a class="nav-link" data-tab="farming" onclick="setTab('farming')">
        <span>Agriculture</span>
      </a>
      <a class="nav-link" data-tab="items" onclick="setTab('items')">
        <span>Items</span>
        <span class="badge" id="nav-items-count">1.7k</span>
      </a>
      <a class="nav-link" data-tab="players" onclick="setTab('players')">
        <span>Players</span>
        <span class="badge" id="nav-players-count">0</span>
      </a>
      <a class="nav-link" data-tab="backups" onclick="setTab('backups')">
        <span>Backups</span>
        <span class="badge" id="nav-backups-count" style="display:none;">0</span>
      </a>
      <a class="nav-link" data-tab="leaderboard" onclick="setTab('leaderboard')">Leaderboard</a>
      <a class="nav-link" data-tab="events" onclick="setTab('events')">Events</a>
      <a class="nav-link" data-tab="logs" onclick="setTab('logs')">Logs</a>
      <hr>
      <a href="/status" target="_blank">
        <span>API Status</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/respawns" target="_blank">
        <span>API Respawns</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/farming" target="_blank">
        <span>API Agriculture</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/items" target="_blank">
        <span>API Items</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/weather" target="_blank">
        <span>API Weather</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/roster" target="_blank">
        <span>API Roster</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/save-files" target="_blank">
        <span>API Save Files</span>
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
      <a class="mobile-link" data-tab="respawns" onclick="setTab('respawns')">Respawns</a>
      <a class="mobile-link" data-tab="farming" onclick="setTab('farming')">Agriculture</a>
      <a class="mobile-link" data-tab="items" onclick="setTab('items')">Items</a>
      <a class="mobile-link" data-tab="players" onclick="setTab('players')">Players</a>
      <a class="mobile-link" data-tab="backups" onclick="setTab('backups')">Backups</a>
      <a class="mobile-link" data-tab="leaderboard" onclick="setTab('leaderboard')">Leaderboard</a>
      <a class="mobile-link" data-tab="events" onclick="setTab('events')">Events</a>
      <a class="mobile-link" data-tab="logs" onclick="setTab('logs')">Logs</a>
    </div>

    <!-- VIEW 1: OVERVIEW -->
    <div id="view-overview">
      <!-- 8 Stat Cards -->
      <div class="grid">
        <div class="card">
          <div class="icon">PL</div>
          <div class="label">Players</div>
          <div class="value" id="stat-players">0 / 6</div>
          <div><span class="data-source-badge live" title="Real-time telemetry streaming from server memory">⚡ Live</span></div>
        </div>
        <div class="card">
          <div class="icon">DAY</div>
          <div class="label">World Day</div>
          <div class="value" id="stat-day" style="font-size:22px; color:#f59e0b;">Day --</div>
          <div><span class="data-source-badge saved" id="badge-stat-day" title="Synchronized from latest world save snapshot">💾 Saved</span></div>
        </div>
        <div class="card">
          <div class="icon">WD</div>
          <div class="label">World</div>
          <div class="value" id="world" style="font-size:18px;">...</div>
          <div><span class="data-source-badge saved" id="badge-world" title="Active save slot name">💾 Saved</span></div>
        </div>
        <div class="card">
          <div class="icon">UP</div>
          <div class="label">Uptime</div>
          <div class="value" id="uptime">...</div>
          <div><span class="data-source-badge live" title="Container and server process execution duration">⚡ Live</span></div>
        </div>
        <div class="card">
          <div class="icon">SV</div>
          <div class="label">Last Save</div>
          <div class="value" id="save">...</div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
            <span class="data-source-badge saved" id="badge-save" title="Most recent world save timestamp">💾 Snapshot</span>
            <a onclick="setTab('backups')" style="color:#f59e0b; font-size:11px; cursor:pointer; text-decoration:underline;">Backups 💾</a>
          </div>
        </div>
        <div class="card">
          <div class="icon">CPU</div>
          <div class="label">CPU</div>
          <div class="value" id="cpu">N/A</div>
          <div><span class="data-source-badge live" title="Real-time CPU telemetry via docker cgroups">⚡ Live</span></div>
        </div>
        <div class="card">
          <div class="icon">RAM</div>
          <div class="label">RAM</div>
          <div class="value" id="ram">N/A</div>
          <div><span class="data-source-badge live" title="Real-time memory usage via docker cgroups">⚡ Live</span></div>
        </div>
        <div class="card">
          <div class="icon">VER</div>
          <div class="label">Version</div>
          <div class="value" id="version" style="font-size:18px;">...</div>
          <div><span class="data-source-badge live" title="Server engine build release">⚡ Process</span></div>
        </div>
      </div>

      <!-- In-Game Day / Night Solar Clock Dial -->
      <div class="day-night-card">
        <div class="day-night-layout">
          <div class="dial-svg-wrapper">
            <svg viewBox="0 0 100 100" class="day-night-clock-svg" id="day-night-svg">
              <defs>
                <!-- Clip path for the full 240° daytime arc (from 210° around to 90°) -->
                <!-- We clip the golden glowing sun artwork to the daytime passed sector (from 210° up to current needle angle) -->
                <clipPath id="clip-day-passed">
                  <path id="path-day-passed" d="M 50,50 Z" />
                </clipPath>
              </defs>

              <!-- Outer metallic brass/gold bezel -->
              <circle cx="50" cy="50" r="48" fill="#0f172a" stroke="#d4af37" stroke-width="2.2" />

              <!-- 1. NIGHT TIME SECTION (Permanent dark periwinkle / slate blue with crescent moon) -->
              <!-- Sits from 90° (3 o'clock) clockwise to 210° (approx 7 o'clock, 120° night arc) -->
              <path d="M 50,50 L 96,50 A 46,46 0 0,1 27,89.84 Z" fill="#6488ad" />
              <!-- Crescent Moon Artwork in Night Sector -->
              <path d="M 64,68 A 12,12 0 0,0 72,84 A 10,10 0 0,1 64,68 Z" fill="#f1f5f9" opacity="0.9" />

              <!-- 2. DAYTIME REMAINING SECTION (Grayed out / Dim muted background for the 240° day arc) -->
              <path d="M 50,50 L 27,89.84 A 46,46 0 1,1 96,50 Z" fill="#2d333f" />
              <!-- Grayed out sunburst rays (future day) -->
              <g stroke="#64748b" stroke-width="1.6" stroke-linecap="round" opacity="0.4">
                <line x1="50" y1="50" x2="26" y2="76" />
                <line x1="50" y1="50" x2="16" y2="60" />
                <line x1="50" y1="50" x2="14" y2="42" />
                <line x1="50" y1="50" x2="20" y2="24" />
                <line x1="50" y1="50" x2="34" y2="12" />
                <line x1="50" y1="50" x2="50" y2="6" />
                <line x1="50" y1="50" x2="66" y2="12" />
                <line x1="50" y1="50" x2="80" y2="24" />
                <line x1="50" y1="50" x2="88" y2="38" />
              </g>

              <!-- 3. DAYTIME PASSED SECTION (Vibrant golden illuminated sunburst, revealed dynamically up to needle) -->
              <g id="day-passed-group" clip-path="url(#clip-day-passed)">
                <path d="M 50,50 L 27,89.84 A 46,46 0 1,1 96,50 Z" fill="#201a09" />
                <!-- Vibrant Gold Radiating Sunburst Rays -->
                <g stroke="#f59e0b" stroke-width="1.8" stroke-linecap="round" opacity="0.95">
                  <line x1="50" y1="50" x2="26" y2="76" />
                  <line x1="50" y1="50" x2="16" y2="60" />
                  <line x1="50" y1="50" x2="14" y2="42" />
                  <line x1="50" y1="50" x2="20" y2="24" />
                  <line x1="50" y1="50" x2="34" y2="12" />
                  <line x1="50" y1="50" x2="50" y2="6" stroke-width="2.2" stroke="#fbbf24" />
                  <line x1="50" y1="50" x2="66" y2="12" />
                  <line x1="50" y1="50" x2="80" y2="24" />
                  <line x1="50" y1="50" x2="88" y2="38" />
                </g>
                <circle cx="50" cy="50" r="14" fill="#f59e0b" />
                <circle cx="50" cy="50" r="8" fill="#fbbf24" />
              </g>

              <!-- Inner border ring & divider spokes -->
              <circle cx="50" cy="50" r="46" fill="none" stroke="#d4af37" stroke-width="0.8" opacity="0.5" />
              <line x1="50" y1="50" x2="27" y2="89.84" stroke="#d4af37" stroke-width="1.2" opacity="0.7" />
              <line x1="50" y1="50" x2="96" y2="50" stroke="#d4af37" stroke-width="1.2" opacity="0.7" />

              <!-- Needle Pointer Hand (authentically anchored at 50,50, pointing up at 12 o'clock / 0°, rotates clockwise) -->
              <g id="dial-needle-group" style="transform-origin:50px 50px; transform:rotate(210deg); transition:transform 0.8s cubic-bezier(0.4, 0, 0.2, 1);">
                <path d="M 48.2,50 L 49.3,9 L 50,5 L 50.7,9 L 51.8,50 Z" fill="#facc15" stroke="#78350f" stroke-width="0.7" />
                <circle cx="50" cy="50" r="5" fill="#facc15" stroke="#78350f" stroke-width="1.4" />
                <circle cx="50" cy="50" r="2" fill="#0f172a" />
              </g>
            </svg>
          </div>

          <div class="dial-info">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
              <div>
                <div class="dial-phase-title">
                  <span id="dial-phase-icon">☀️</span>
                  <span id="dial-phase-label">Day Cycle Initializing...</span>
                </div>
                <div style="font-size:13px; color:#94a3b8;">
                  In-game solar clock tracking real-time day/night progression and active celestial phase
                </div>
              </div>
              <div>
                <span class="data-source-badge saved" id="badge-dial-source" title="Synchronized from latest world save file (updated every ~5m)">
                  💾 Saved Data (as of --)
                </span>
              </div>
            </div>

            <div class="dial-progress-bar-bg">
              <div class="dial-progress-bar-fill" id="dial-progress-bar" style="width:0%;"></div>
            </div>

            <div class="dial-meta-row">
              <div>
                <span style="color:#f8fafc; font-weight:600;" id="dial-progress-text">0%</span> of day completed
              </div>
              <div id="dial-time-countdown">--m --s elapsed in day</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Regional Weather Section -->
      <div class="card" style="margin-bottom:22px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
          <div>
            <h2 style="margin:0; font-size:18px; font-weight:bold; color:#fff; display:flex; align-items:center; gap:8px;">
              <span>🌤️</span> Regional Weather & Biome Forecast
            </h2>
            <div style="font-size:12.5px; color:#94a3b8; margin-top:2px;">Real-time climate conditions and remaining storm durations across all biomes</div>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="data-source-badge saved" id="badge-weather-source" title="Extracted from world save snapshot">💾 Saved Data</span>
            <div style="font-size:12px; color:#f59e0b; background:#1c2438; padding:4px 10px; border-radius:6px; font-weight:600;" id="weather-day-badge">
              Day --
            </div>
          </div>
        </div>
        <div id="weather-grid" style="display:grid; grid-template-columns:repeat(4, minmax(180px, 1fr)); gap:14px;">
          <div style="color:#94a3b8; grid-column:1/-1; padding:12px 0;">Reading weather data from world save...</div>
        </div>
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
      <!-- Active Connected Players -->
      <div class="card" style="margin-bottom:22px;">
        <h2 style="margin-bottom:18px;">Current Connected Players</h2>
        <div id="current-players-list">Loading players...</div>
      </div>

      <!-- All-Time Server Roster -->
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
          <div>
            <h2 style="margin:0; font-size:18px; font-weight:bold; color:#fff;">All-Time Server Roster</h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">Known player profiles from DedicatedServer.ini with linked Steam and EOS identifiers</div>
          </div>
          <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <div class="pill-group">
              <button class="pill-btn active" onclick="setRosterFilter('all', this)">All</button>
              <button class="pill-btn" onclick="setRosterFilter('admins', this)">Admins</button>
              <button class="pill-btn" onclick="setRosterFilter('online', this)">Online</button>
            </div>
            <input type="text" class="search-input" id="roster-search-input" placeholder="Search roster..." oninput="renderRoster()">
          </div>
        </div>

        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr>
                <th>Account / Steam</th>
                <th>Character Name</th>
                <th>Role</th>
                <th>Status</th>
                <th>Steam ID</th>
                <th>EOS User ID</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody id="roster-table-body">
              <tr><td colspan="7" style="color:#94a3b8; text-align:center; padding:18px;">Loading server roster...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- VIEW: SAVE BACKUPS -->
    <div id="view-backups" style="display:none;">
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
          <div>
            <h2 style="margin:0; font-size:18px; font-weight:bold; color:#fff;">Save Games & Backups</h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">Download raw server saves for offline backup, singleplayer exploration, or RS-Dragonwilds-Editor.</div>
          </div>
          <button class="pg-btn" style="padding:6px 14px; font-weight:600; background:#1e293b; border-color:#334155; color:#f8fafc;" onclick="loadSaveFiles()">🔄 Refresh Files</button>
        </div>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr>
                <th>File Name</th>
                <th>Type</th>
                <th>File Size</th>
                <th>Last Modified</th>
                <th style="text-align:right;">Actions</th>
              </tr>
            </thead>
            <tbody id="save-files-table-body">
              <tr><td colspan="5" style="color:#94a3b8; text-align:center; padding:20px;">Scanning save files...</td></tr>
            </tbody>
          </table>
        </div>
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

    <!-- VIEW 6: RESPAWNS TRACKER -->
    <div id="view-respawns" style="display:none;">
      <div class="card" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:16px;">
          <div>
            <h2 style="margin:0; font-size:20px; font-weight:bold; color:#f8fafc; display:flex; align-items:center; gap:8px;">
              <span>⏳</span> World Entities & Live Respawn Tracker
            </h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">
              Objective telemetry tracking live chest respawns from server logs and 770+ game entities directly from server saves.
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="data-source-badge live" title="Direct telemetry from server logs (SetRespawnTimer / PerformRespawn)">⚡ Live Telemetry</span>
            <span class="data-source-badge saved" title="Objective world entity index extracted from latest server .sav file">💾 Server Save Data</span>
          </div>
        </div>

        <!-- Filter & Search Toolbar -->
        <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:center; justify-content:space-between; background:#0c1322; padding:12px 16px; border-radius:10px; border:1px solid #1c283f;">
          <div class="pill-group" id="respawn-pills">
            <button class="pill-btn active" onclick="setRespawnCategory('all', this)">All Entities</button>
            <button class="pill-btn" onclick="setRespawnCategory('Chests & Vaults', this)">Chests & Vaults</button>
            <button class="pill-btn" onclick="setRespawnCategory('Ore & Mineral Veins', this)">Ore Veins</button>
            <button class="pill-btn" onclick="setRespawnCategory('Mining Rocks & Crystals', this)">Rocks & Crystals</button>
            <button class="pill-btn" onclick="setRespawnCategory('Fishing Nodes', this)">Fishing Nodes</button>
            <button class="pill-btn" onclick="setRespawnCategory('Flora & Foraging Spawners', this)">Flora Spawners</button>
            <button class="pill-btn" onclick="setRespawnCategory('NPCs & Creatures', this)">NPCs & Creatures</button>
            <button class="pill-btn" onclick="setRespawnCategory('Bosses, Dragons & Monsters', this)">Bosses & Monsters</button>
          </div>
          <div style="display:flex; gap:8px; align-items:center; flex:1; max-width:320px;">
            <input type="text" id="respawn-search-input" placeholder="Search any entity, mob, ore, chest..." oninput="filterRespawnsLive()"
                   style="width:100%; background:#131c2e; border:1px solid #1e2c45; color:#f8fafc; padding:8px 12px; border-radius:8px; font-size:13px; outline:none;">
          </div>
        </div>
      </div>

      <!-- Respawns Grid / Table -->
      <div class="card">
        <div style="overflow-x:auto;">
          <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
                <th>Status</th>
                <th>Target Resource</th>
                <th>Category</th>
                <th>Cycle Duration</th>
                <th>Remaining / Ready Time</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody id="respawns-table-body">
              <tr><td colspan="6" style="color:#94a3b8; text-align:center; padding:24px;">Scanning server telemetry for active respawns...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- VIEW 7: AGRICULTURE & FARMING -->
    <div id="view-farming" style="display:none;">
      <div class="card" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div>
            <h2 style="margin:0; font-size:20px; font-weight:bold; color:#f8fafc; display:flex; align-items:center; gap:8px;">
              <span>🌱</span> Farming Plots & Agriculture Status
            </h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">
              Server-extracted telemetry of in-world planted crops, medicinal herbs, growing saplings, and hydration infrastructure.
            </div>
          </div>
          <div>
            <span class="data-source-badge saved" title="Extracted from active world save">💾 Save File</span>
          </div>
        </div>
      </div>

      <div class="grid" id="farming-summary-grid">
        <div class="card">
          <div class="icon">🌾</div>
          <div class="label">Planted Crops & Herbs</div>
          <div class="value" id="farm-stat-crops" style="color:#38bdf8;">0</div>
        </div>
        <div class="card">
          <div class="icon">🌳</div>
          <div class="label">Growing Saplings & Trees</div>
          <div class="value" id="farm-stat-trees" style="color:#34d399;">0</div>
        </div>
        <div class="card">
          <div class="icon">💧</div>
          <div class="label">Water Storage Barrels</div>
          <div class="value" id="farm-stat-barrels">0</div>
        </div>
        <div class="card">
          <div class="icon">🌧️</div>
          <div class="label">Rain Catchers</div>
          <div class="value" id="farm-stat-rain">0</div>
        </div>
        <div class="card">
          <div class="icon">🍂</div>
          <div class="label">Composting Stations</div>
          <div class="value" id="farm-stat-composters">0</div>
        </div>
      </div>

      <!-- ACTIVE CROPS TABLE -->
      <div class="card" style="margin-bottom:20px;">
        <h3 style="margin-top:0; color:#f8fafc; font-size:16px; display:flex; align-items:center; gap:8px;">
          <span>🌾</span> Active In-World Crops & Medicinal Herbs
        </h3>
        <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
              <th>Crop / Plant Name</th>
              <th>Category</th>
              <th>World Instances</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="crops-table-body">
            <tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:20px;">Scanning crops and herbs in active save file...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- INFRASTRUCTURE & ARBORICULTURE TABLE -->
      <div class="card">
        <h3 style="margin-top:0; color:#f8fafc; font-size:16px; display:flex; align-items:center; gap:8px;">
          <span>🏡</span> Placed Farming Infrastructure & Arboriculture
        </h3>
        <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
              <th>Infrastructure / Piece</th>
              <th>System Role</th>
              <th>World Count</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="farming-table-body">
            <tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:20px;">Loading agricultural save data...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- VIEW 8: MASTER ITEM CATALOG -->
    <div id="view-items" style="display:none;">
      <div class="card" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
          <div>
            <h2 style="margin:0; font-size:20px; font-weight:bold; color:#f8fafc; display:flex; align-items:center; gap:8px;">
              <span>📦</span> Master Item Catalog
            </h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">
              Exhaustive official catalog of 1,704 items extracted directly from server game packages.
            </div>
          </div>
          <div>
            <span class="data-source-badge live" title="Direct index from game packages">⚡ Official Game Assets</span>
          </div>
        </div>

        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <input type="text" id="items-search-input" placeholder="Search 1,700+ weapons, armor, potions, tools, resources..." oninput="searchItemsLive()"
                 style="flex:1; min-width:280px; background:#131c2e; border:1px solid #1e2c45; color:#f8fafc; padding:10px 14px; border-radius:8px; font-size:13.5px; outline:none;">
          <select id="items-cat-select" onchange="searchItemsLive()"
                  style="background:#131c2e; border:1px solid #1e2c45; color:#f8fafc; padding:10px 14px; border-radius:8px; font-size:13px; outline:none;">
            <option value="all">All Item Categories</option>
            <option value="Ammo">Ammunition & Arrows</option>
            <option value="Armor">Armor & Equipment</option>
            <option value="Weapons">Weapons</option>
            <option value="Resources">Resources & Materials</option>
            <option value="Consumables">Consumables & Food</option>
            <option value="Tools">Tools</option>
          </select>
        </div>
      </div>

      <div class="card">
        <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
              <th>Item Name</th>
              <th>Engine Identifier</th>
              <th>Category</th>
            </tr>
          </thead>
          <tbody id="items-table-body">
            <tr><td colspan="3" style="color:#94a3b8; text-align:center; padding:24px;">Loading master item catalog...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>
</div>

<script>
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

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
  const vBackups = document.getElementById('view-backups');
  const vLeaderboard = document.getElementById('view-leaderboard');
  const vEvents = document.getElementById('view-events');
  const vRespawns = document.getElementById('view-respawns');

  const vFarming = document.getElementById('view-farming');
  const vItems = document.getElementById('view-items');

  vOverview.style.display = 'none';
  vLogs.style.display = 'none';
  vPlayers.style.display = 'none';
  if (vBackups) vBackups.style.display = 'none';
  vLeaderboard.style.display = 'none';
  vEvents.style.display = 'none';
  if (vRespawns) vRespawns.style.display = 'none';
  if (vFarming) vFarming.style.display = 'none';
  if (vItems) vItems.style.display = 'none';

  if (tab === 'overview') {
    title.innerText = 'Overview';
    subtitle.innerText = 'Real-time overview of your Dragonwilds server';
    vOverview.style.display = 'block';
  } else if (tab === 'respawns') {
    title.innerText = 'Respawn Tracker';
    subtitle.innerText = 'Active timers for dungeon chests, fishing nets, world bosses & high-tier ores';
    if (vRespawns) vRespawns.style.display = 'block';
    loadRespawns();
  } else if (tab === 'farming') {
    title.innerText = 'Farming & Agriculture';
    subtitle.innerText = 'Tracking placed hydration, composters, and growing agriculture plots';
    if (vFarming) vFarming.style.display = 'block';
    loadFarming();
  } else if (tab === 'items') {
    title.innerText = 'Master Item Catalog';
    subtitle.innerText = 'Explore and search 1,704 official in-game items, weapons, and resources';
    if (vItems) vItems.style.display = 'block';
    loadMasterItems();
  } else if (tab === 'logs') {
    title.innerText = 'Server Logs';
    subtitle.innerText = 'Stream, filter and search RSDragonwilds server logs';
    vLogs.style.display = 'block';
    fetchLogFiles();
    fetchLogs();
  } else if (tab === 'players') {
    title.innerText = 'Players';
    subtitle.innerText = 'Active players & all-time registered server roster';
    vPlayers.style.display = 'block';
    loadRoster();
  } else if (tab === 'backups') {
    title.innerText = 'Save Backups';
    subtitle.innerText = 'Download server save files for local backups or editing';
    if (vBackups) vBackups.style.display = 'block';
    loadSaveFiles();
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

// ----------------- OVERVIEW STATUS, WEATHER & EVENTS -----------------
async function loadStatus() {
  try {
    const res = await fetch('/status');
    const s = await res.json();

    document.getElementById('stat-players').innerText = `${s.players_online} / ${s.max_players}`;
    document.getElementById('nav-players-count').innerText = s.players_online;
    
    const dayEl = document.getElementById('stat-day');
    if (dayEl) dayEl.innerText = s.day_count ? `Day ${s.day_count}` : 'Day --';
    const weatherDayEl = document.getElementById('weather-day-badge');
    if (weatherDayEl) weatherDayEl.innerText = s.day_count ? `Day ${s.day_count}` : 'Day --';

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
    pContainer.innerHTML = '';
    const details = s.players_detail || (s.players || []).map(p => ({ name: p, character_name: null }));
    if (!details || details.length === 0) {
      pContainer.innerHTML = '<div style="color:#94a3b8; padding:16px 0;">No players currently connected.</div>';
    } else {
      details.forEach(p => {
        const charTitle = p.character_name 
          ? `<span style="color:#f59e0b; font-weight:bold;">${escapeHtml(p.character_name)}</span> <span style="font-weight:normal; color:#94a3b8; font-size:13px;">(${escapeHtml(p.name)})</span>` 
          : `<span style="font-weight:bold; color:#fff;">${escapeHtml(p.name)}</span>`;
        const initial = (p.character_name || p.name || '?')[0].toUpperCase();
        const div = document.createElement('div');
        div.className = 'player-row';
        div.innerHTML = `
          <div class="player-left">
            <div class="avatar">${escapeHtml(initial)}</div>
            <div>
              <div>${charTitle}</div>
              <div style="font-size:12px; color:#94a3b8;">Connected to ${escapeHtml(s.world||'World')}</div>
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
  // Day starts at 210° (approx 7 o'clock) and sweeps clockwise through 270°, 0°, to 90° (3 o'clock)
  const clipPathEl = document.getElementById('path-day-passed');
  if (clipPathEl) {
    const cx = 50, cy = 50, r = 46;
    const startDeg = 210.0;
    const startRad = (startDeg - 90) * Math.PI / 180;
    const x0 = cx + r * Math.cos(startRad);
    const y0 = cy + r * Math.sin(startRad);

    // Current needle clamped to day arc
    let curDeg = angle;
    // Calculate angular distance clockwise from 210°
    let delta = (curDeg - startDeg + 360) % 360;
    // Day arc length is 240° (from 210° to 90°)
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
    grid.innerHTML = '<div style="color:#94a3b8; grid-column:1/-1; padding:12px 0;">No weather forecast available in save file.</div>';
    return;
  }
  grid.innerHTML = list.map(w => `
    <div class="weather-biome-card" style="background:#0c1322; border:1px solid #1c283f; border-radius:10px; padding:14px 16px;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
        <span style="font-size:26px;">${w.icon || '🌤️'}</span>
        <span style="font-size:11px; font-weight:600; padding:2px 8px; border-radius:12px; background:#19253d; color:${w.remaining_seconds > 0 ? '#38bdf8' : '#94a3b8'};">
          ${escapeHtml(w.remaining_text || 'Active')}
        </span>
      </div>
      <div style="font-size:12.5px; font-weight:500; color:#94a3b8; margin-bottom:2px;">${escapeHtml(w.region || w.raw_region)}</div>
      <div style="font-size:15px; font-weight:bold; color:#f8fafc;">${escapeHtml(w.type)}</div>
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
    body.innerHTML = '<tr><td colspan="7" style="color:#94a3b8; text-align:center; padding:18px;">No matching players found in server roster.</td></tr>';
    return;
  }

  body.innerHTML = filtered.map(p => {
    let roleBadge = '<span style="background:#1e293b; color:#94a3b8; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">Member</span>';
    if (p.is_owner) {
      roleBadge = '<span style="background:#78350f; color:#fde68a; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">👑 Owner</span>';
    } else if (p.is_admin) {
      roleBadge = '<span style="background:#581c87; color:#e9d5ff; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">🛡️ Admin</span>';
    }

    const charCell = p.character_name
      ? `<strong style="color:#f59e0b;">${escapeHtml(p.character_name)}</strong>`
      : '<span style="color:#64748b;">—</span>';

    const statusBadge = p.online 
      ? '<span style="background:#064e3b; color:#34d399; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">🟢 Online</span>'
      : '<span style="background:#1e293b; color:#64748b; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">Offline</span>';

    const steamCell = p.steam_id
      ? `<a href="https://steamcommunity.com/profiles/${encodeURIComponent(p.steam_id)}" target="_blank" style="color:#38bdf8; text-decoration:none; font-family:monospace; font-size:12px;">${escapeHtml(p.steam_id)} ↗</a>`
      : '<span style="color:#64748b; font-size:12px;">Unlinked</span>';

    const bannedBadge = p.is_banned
      ? '<span style="background:#7f1d1d; color:#fca5a5; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">Banned</span>'
      : '<span style="color:#10b981; font-size:12px;">Active</span>';

    const shortEos = p.user_id ? `${p.user_id.slice(0, 8)}...${p.user_id.slice(-6)}` : 'N/A';

    return `
      <tr>
        <td><strong>${escapeHtml(p.name)}</strong></td>
        <td>${charCell}</td>
        <td>${roleBadge}</td>
        <td>${statusBadge}</td>
        <td>${steamCell}</td>
        <td><code style="color:#94a3b8; font-size:12px;" title="${escapeHtml(p.user_id)}">${escapeHtml(shortEos)}</code></td>
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
    const badge = document.getElementById('nav-backups-count');
    if (badge) {
      badge.innerText = allSaveFiles.length;
      badge.style.display = allSaveFiles.length > 0 ? 'inline' : 'none';
    }
    if (!body) return;

    if (!allSaveFiles || allSaveFiles.length === 0) {
      body.innerHTML = '<tr><td colspan="5" style="color:#94a3b8; text-align:center; padding:18px;">No save files found in server save directory.</td></tr>';
      return;
    }

    body.innerHTML = allSaveFiles.map(f => {
      const typeBadge = f.is_backup
        ? '<span style="background:#1e293b; color:#94a3b8; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">Backup (.sav.backup)</span>'
        : '<span style="background:#064e3b; color:#34d399; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">Active World (.sav)</span>';

      return `
        <tr>
          <td><strong style="font-family:monospace; color:#f8fafc;">${escapeHtml(f.filename)}</strong></td>
          <td>${typeBadge}</td>
          <td>${escapeHtml(f.size_str)}</td>
          <td style="color:#94a3b8; font-size:13px;">${escapeHtml(f.modified_text)}</td>
          <td style="text-align:right;">
            <a href="/api/save-files/download/${encodeURIComponent(f.filename)}" class="pg-btn" style="text-decoration:none; display:inline-block; padding:4px 12px; background:#e65100; color:#fff; border-color:#e65100; font-weight:600;">
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

    const badge = document.getElementById('nav-respawns-count');
    if (badge) {
      const respawningCount = allRespawns.filter(r => !r.is_ready).length;
      badge.innerText = respawningCount > 0 ? respawningCount : allRespawns.length;
      badge.style.display = allRespawns.length > 0 ? 'inline' : 'none';
    }
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
    body.innerHTML = '<tr><td colspan="6" style="color:#94a3b8; text-align:center; padding:24px;">No matching respawns found.</td></tr>';
    return;
  }

  body.innerHTML = filtered.map(r => {
    const statusBadge = r.is_ready
      ? '<span style="background:#064e3b; color:#34d399; padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">🟢 Ready to Loot</span>'
      : '<span style="background:#78350f; color:#fde68a; padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">⏳ Respawning</span>';

    const sourceBadge = r.source === 'live_log'
      ? '<span class="data-source-badge live" title="Direct telemetry from server logs (SetRespawnTimer / PerformRespawn)">⚡ Live Telemetry</span>'
      : '<span class="data-source-badge saved" title="Extracted from server save game file">💾 Save File</span>';

    const remainingColor = r.is_ready ? '#34d399' : '#f59e0b';

    return `
      <tr style="border-bottom:1px solid #141f33;">
        <td style="padding:12px 14px;">${statusBadge}</td>
        <td style="padding:12px 14px;">
          <div style="font-weight:600; color:#f8fafc; font-size:14px;">${escapeHtml(r.name)}</div>
          <div style="font-family:monospace; font-size:11.5px; color:#64748b; margin-top:2px;">${escapeHtml(r.id)}</div>
        </td>
        <td style="padding:12px 14px; color:#cbd5e1; font-size:13px;">${escapeHtml(r.category)}</td>
        <td style="padding:12px 14px; color:#94a3b8; font-size:13px;">${escapeHtml(r.duration_formatted || '—')}</td>
        <td style="padding:12px 14px;">
          <strong style="color:${remainingColor}; font-size:13.5px;">${escapeHtml(r.remaining_formatted)}</strong>
          ${!r.is_ready && r.respawn_time ? `<div style="color:#64748b; font-size:11px;">at ${escapeHtml(r.respawn_time)}</div>` : ''}
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

  // 1. Render Active In-World Crops & Herbs
  const cropsBody = document.getElementById('crops-table-body');
  if (cropsBody) {
    const crops = farmingData.crops || [];
    if (crops.length === 0) {
      cropsBody.innerHTML = '<tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:20px;">No wild or planted crop instances found in active save file.</td></tr>';
    } else {
      cropsBody.innerHTML = crops.map(c => `
        <tr style="border-bottom:1px solid #141f33;">
          <td style="padding:12px 14px; font-weight:600; color:#f8fafc;">${escapeHtml(c.name)}</td>
          <td style="padding:12px 14px; color:#94a3b8; font-size:13px;">${escapeHtml(c.category)}</td>
          <td style="padding:12px 14px; font-weight:bold; color:#38bdf8;">${c.count || 0}</td>
          <td style="padding:12px 14px;">
            <span style="background:#064e3b; color:#34d399; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">
              ${escapeHtml(c.status || 'Active')}
            </span>
          </td>
        </tr>
      `).join('');
    }
  }

  // 2. Render Placed Farming Infrastructure & Arboriculture
  const tbody = document.getElementById('farming-table-body');
  if (!tbody) return;

  const structures = farmingData.structures || [];
  const growing = farmingData.growing_trees || [];
  const allEntries = [...structures, ...growing];

  if (allEntries.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:20px;">No placed agriculture structures or planted saplings detected in current save file.</td></tr>';
    return;
  }

  tbody.innerHTML = allEntries.map(item => `
    <tr style="border-bottom:1px solid #141f33;">
      <td style="padding:12px 14px; font-weight:600; color:#f8fafc;">${escapeHtml(item.name)}</td>
      <td style="padding:12px 14px; color:#94a3b8; font-size:13px;">${escapeHtml(item.type || item.stage_tracking || item.category || 'Agriculture')}</td>
      <td style="padding:12px 14px; font-weight:bold; color:#38bdf8;">${item.count || 0}</td>
      <td style="padding:12px 14px;">
        <span style="background:#064e3b; color:#34d399; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">
          ${escapeHtml(item.status || 'Active')}
        </span>
      </td>
    </tr>
  `).join('');
}

// ----------------- MASTER ITEMS CATALOG -----------------
let masterItemsList = [];
let itemsSearchTimeout = null;

async function loadMasterItems() {
  await searchItemsLive();
}

function searchItemsLive() {
  clearTimeout(itemsSearchTimeout);
  itemsSearchTimeout = setTimeout(async () => {
    try {
      const q = (document.getElementById('items-search-input')?.value || '').trim();
      const cat = (document.getElementById('items-cat-select')?.value || 'all');
      const res = await fetch(`/api/items?category=${encodeURIComponent(cat)}&search=${encodeURIComponent(q)}`);
      masterItemsList = await res.json();
      renderMasterItems();

      const badge = document.getElementById('nav-items-count');
      if (badge && !q && cat === 'all') {
        badge.innerText = masterItemsList.length > 1000 ? `${(masterItemsList.length/1000).toFixed(1)}k` : masterItemsList.length;
      }
    } catch(e) {}
  }, 200);
}

function renderMasterItems() {
  const tbody = document.getElementById('items-table-body');
  if (!tbody) return;

  if (!masterItemsList || masterItemsList.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" style="color:#94a3b8; text-align:center; padding:24px;">No items match your search.</td></tr>';
    return;
  }

  const itemsToShow = masterItemsList.slice(0, 150);
  tbody.innerHTML = itemsToShow.map(it => `
    <tr style="border-bottom:1px solid #141f33;">
      <td style="padding:10px 14px; font-weight:600; color:#f8fafc;">${escapeHtml(it.name || it.id)}</td>
      <td style="padding:10px 14px; font-family:monospace; color:#38bdf8; font-size:12px;">${escapeHtml(it.id)}</td>
      <td style="padding:10px 14px;">
        <span style="background:#1e293b; color:#cbd5e1; padding:2px 8px; border-radius:6px; font-size:11.5px; font-weight:500;">
          ${escapeHtml(it.category || 'General')}
        </span>
      </td>
    </tr>
  `).join('');

  if (masterItemsList.length > 150) {
    tbody.innerHTML += `<tr><td colspan="3" style="color:#64748b; text-align:center; padding:12px; font-size:12px;">Showing first 150 of ${masterItemsList.length} items. Refine search query to filter further.</td></tr>`;
  }
}

// ----------------- REFRESH LOOPS -----------------
async function refreshAll() {
  await loadStatus();
  await loadLeaderboard();
  await loadSaveFiles();
  await loadRespawns();
  if (currentTab === 'farming') await loadFarming();
  if (currentTab === 'players') await loadRoster();
  if (currentTab === 'logs' && isLive) {
    await fetchLogs();
  }
}

// Initial hash support
const hash = (window.location.hash || '').replace('#', '');
if (['overview', 'respawns', 'farming', 'items', 'players', 'backups', 'leaderboard', 'events', 'logs'].includes(hash)) {
  setTab(hash);
} else {
  setTab('overview');
}

refreshAll();
setInterval(loadStatus, 4000);
setInterval(() => {
  if (currentTab === 'respawns') {
    loadRespawns();
  }
  if (currentTab === 'farming') {
    loadFarming();
  }
  if (currentTab === 'logs' && isLive) {
    fetchLogs();
  }
}, 3000);
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
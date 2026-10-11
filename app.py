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


@app.route("/api/world/actors")
def api_world_actors():
    from worldactors import get_world_actor_manager
    import config
    categories_param = request.args.get("category", "")
    categories = [c.strip() for c in categories_param.split(",") if c.strip()] if categories_param else None
    force_refresh = request.args.get("refresh", "").lower() in ("1", "true", "yes")
    manager = get_world_actor_manager(config.SPUD_CACHE_PATH)
    return jsonify(manager.get_actors(categories=categories, force_refresh=force_refresh))



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


@app.route("/api/storage/units")
def api_storage_units():
    from storage import get_storage_units
    save_file = request.args.get("save")
    return jsonify(get_storage_units(save_filename=save_file))


@app.route("/api/storage/items")
def api_storage_items():
    from storage import search_stored_items, parse_storage_data
    query = request.args.get("search", "").strip()
    save_file = request.args.get("save")
    if not query:
        data = parse_storage_data(save_filename=save_file)
        return jsonify({
            "summary": {
                "total_containers": data.get("total_containers", 0),
                "total_stored_items": data.get("total_stored_items", 0),
                "unique_items_count": data.get("unique_items_count", 0),
                "save_file": data.get("save_file"),
            },
            "items": data.get("items", []),
        })
    results = search_stored_items(query=query, save_filename=save_file)
    data = parse_storage_data(save_filename=save_file)
    return jsonify({
        "summary": {
            "total_containers": data.get("total_containers", 0),
            "total_stored_items": data.get("total_stored_items", 0),
            "unique_items_count": data.get("unique_items_count", 0),
            "save_file": data.get("save_file"),
        },
        "items": results,
    })


@app.route("/api/bosses")
def api_bosses():
    from bosses import get_boss_encounters
    return jsonify(get_boss_encounters())


@app.route("/api/world-events")
def api_world_events():
    from bosses import get_live_world_events
    return jsonify(get_live_world_events())


@app.route("/api/campaign")
def api_campaign():
    from campaign import get_campaign_status
    return jsonify(get_campaign_status())


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
      <a class="nav-link" data-tab="map" onclick="setTab('map')">
        <span>World Map</span>
      </a>
      <a class="nav-link" data-tab="respawns" onclick="setTab('respawns')">
        <span>Respawns</span>
        <span class="badge" id="nav-respawns-count">0</span>
      </a>
      <a class="nav-link" data-tab="farming" onclick="setTab('farming')">
        <span>Agriculture</span>
      </a>
      <a class="nav-link" data-tab="items" onclick="setTab('items')">
        <span>Storage & Items</span>
        <span class="badge" id="nav-items-count">0</span>
      </a>
      <a class="nav-link" data-tab="bosses" onclick="setTab('bosses')">
        <span>Boss Arenas</span>
        <span class="badge" id="nav-bosses-count">0</span>
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
        <span>API Master Items</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/storage/items" target="_blank">
        <span>API Stored Items</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/storage/units" target="_blank">
        <span>API Storage Units</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/bosses" target="_blank">
        <span>API Bosses</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/campaign" target="_blank">
        <span>API Campaign</span>
        <span style="font-size:11px;">↗</span>
      </a>
      <a href="/api/world-events" target="_blank">
        <span>API World Events</span>
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
      <a class="mobile-link" data-tab="map" onclick="setTab('map')">Map</a>
      <a class="mobile-link" data-tab="respawns" onclick="setTab('respawns')">Respawns</a>
      <a class="mobile-link" data-tab="farming" onclick="setTab('farming')">Agriculture</a>
      <a class="mobile-link" data-tab="items" onclick="setTab('items')">Storage</a>
      <a class="mobile-link" data-tab="bosses" onclick="setTab('bosses')">Bosses</a>
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
              <!-- Sits from 240° (approx 8 o'clock) clockwise to 360° / 0° (12 o'clock, 120° night arc) -->
              <path d="M 50,50 L 10.16,73 A 46,46 0 0,1 50,4 Z" fill="#6488ad" />
              <!-- Crescent Moon Artwork in Night Sector (top-left quadrant) -->
              <path d="M 28,34 A 11,11 0 0,0 36,49 A 9,9 0 0,1 28,34 Z" fill="#f1f5f9" opacity="0.9" />

              <!-- 2. DAYTIME REMAINING SECTION (Grayed out / Dim muted background for the 240° day arc: 0° to 240°) -->
              <path d="M 50,50 L 50,4 A 46,46 0 1,1 10.16,73 Z" fill="#2d333f" />
              <!-- Grayed out sunburst rays (future day) -->
              <g stroke="#64748b" stroke-width="1.6" stroke-linecap="round" opacity="0.4">
                <line x1="50" y1="50" x2="66" y2="12" />
                <line x1="50" y1="50" x2="80" y2="24" />
                <line x1="50" y1="50" x2="88" y2="38" />
                <line x1="50" y1="50" x2="94" y2="50" />
                <line x1="50" y1="50" x2="88" y2="66" />
                <line x1="50" y1="50" x2="80" y2="78" />
                <line x1="50" y1="50" x2="66" y2="88" />
                <line x1="50" y1="50" x2="50" y2="94" />
                <line x1="50" y1="50" x2="34" y2="88" />
                <line x1="50" y1="50" x2="20" y2="80" />
              </g>

              <!-- 3. DAYTIME PASSED SECTION (Vibrant golden illuminated sunburst, revealed dynamically up to needle) -->
              <g id="day-passed-group" clip-path="url(#clip-day-passed)">
                <path d="M 50,50 L 50,4 A 46,46 0 1,1 10.16,73 Z" fill="#201a09" />
                <!-- Vibrant Gold Radiating Sunburst Rays -->
                <g stroke="#f59e0b" stroke-width="1.8" stroke-linecap="round" opacity="0.95">
                  <line x1="50" y1="50" x2="66" y2="12" />
                  <line x1="50" y1="50" x2="80" y2="24" />
                  <line x1="50" y1="50" x2="88" y2="38" stroke-width="2.2" stroke="#fbbf24" />
                  <line x1="50" y1="50" x2="94" y2="50" stroke-width="2.2" stroke="#fbbf24" />
                  <line x1="50" y1="50" x2="88" y2="66" />
                  <line x1="50" y1="50" x2="80" y2="78" />
                  <line x1="50" y1="50" x2="66" y2="88" />
                  <line x1="50" y1="50" x2="50" y2="94" />
                  <line x1="50" y1="50" x2="34" y2="88" />
                  <line x1="50" y1="50" x2="20" y2="80" />
                </g>
                <circle cx="50" cy="50" r="14" fill="#f59e0b" />
                <circle cx="50" cy="50" r="8" fill="#fbbf24" />
              </g>

              <!-- Inner border ring & divider spokes -->
              <circle cx="50" cy="50" r="46" fill="none" stroke="#d4af37" stroke-width="0.8" opacity="0.5" />
              <line x1="50" y1="50" x2="50" y2="4" stroke="#d4af37" stroke-width="1.4" opacity="0.8" />
              <line x1="50" y1="50" x2="10.16" y2="73" stroke="#d4af37" stroke-width="1.2" opacity="0.7" />

              <!-- Needle Pointer Hand (authentically anchored at 50,50, pointing up at 12 o'clock / 0°, rotates clockwise) -->
              <g id="dial-needle-group" style="transform-origin:50px 50px; transform:rotate(0deg); transition:transform 0.8s cubic-bezier(0.4, 0, 0.2, 1);">
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

    <!-- VIEW: INTERACTIVE WORLD MAP -->
    <div id="view-map" style="display:none;">
      <div class="card" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
          <div>
            <h2 style="margin:0; font-size:20px; font-weight:bold; color:#f8fafc; display:flex; align-items:center; gap:8px;">
              <span>🗺️</span> Interactive World Map of Ashenfall
            </h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">
              Topographical continent map with real-time loot respawns, boss trials, player landmarks, and regional weather.
            </div>
            <div style="font-size:11.5px; color:#64748b; margin-top:3px;">
              Tip: Hover any pin to preview • Click to inspect details • Drag to pan • Scroll wheel to zoom
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="data-source-badge live" title="Real-time territorial coordinates & telemetry">⚡ Live Telemetry</span>
            <span class="data-source-badge saved" title="Extracted from world save snapshots">💾 Save Data</span>
          </div>
        </div>

        <!-- Map Layer Toggles & Search -->
        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between;">
          <div class="pill-group" id="map-layer-pills">
            <button class="pill-btn active" id="btn-layer-all" onclick="toggleMapLayer('all', this)">All Layers</button>
            <button class="pill-btn" id="btn-layer-fishing" onclick="toggleMapLayer('fishing', this)">🎣 Fishing</button>
            <button class="pill-btn" id="btn-layer-npcs" onclick="toggleMapLayer('npcs', this)">👤 NPCs</button>
            <button class="pill-btn" id="btn-layer-shrines" onclick="toggleMapLayer('shrines', this)">✨ Shrines</button>
            <button class="pill-btn" id="btn-layer-chests" onclick="toggleMapLayer('chests', this)">Chests & Caches</button>
            <button class="pill-btn" id="btn-layer-bosses" onclick="toggleMapLayer('bosses', this)">Boss Arenas</button>
            <button class="pill-btn" id="btn-layer-graves" onclick="toggleMapLayer('graves', this)">🪦 Gravestones</button>
            <button class="pill-btn" id="btn-layer-camps" onclick="toggleMapLayer('camps', this)">⛺ Player Camps</button>
            <button class="pill-btn" id="btn-layer-weather" onclick="toggleMapLayer('weather', this)">Regional Weather</button>
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
            <input type="text" id="map-search-input" placeholder="Find region, NPC, fishing, chest, or grave..." oninput="filterMapMarkersLive()"
                   style="background:#131c2e; border:1px solid #1e2c45; color:#f8fafc; padding:8px 12px; border-radius:8px; font-size:13px; outline:none; min-width:260px;">
          </div>
        </div>
      </div>

      <!-- Map Canvas & Detail Split Card -->
      <div class="card" style="padding:16px;">
        <div style="display:grid; grid-template-columns: 2fr 1fr; gap:16px;" class="map-split-container">
          <!-- Canvas Visualizer -->
          <div style="background:#070b14; border:1px solid #1e2c45; border-radius:12px; position:relative; overflow:hidden; min-height:540px; display:flex; flex-direction:column; align-items:center; justify-content:center;">
            <canvas id="world-map-canvas" width="800" height="540" style="width:100%; height:100%; cursor:grab;"></canvas>
            
            <!-- Zoom & Pan Overlay Controls -->
            <div style="position:absolute; bottom:14px; right:14px; display:flex; gap:6px; background:#0f172a; padding:4px 6px; border-radius:8px; border:1px solid #1e293b; z-index:10;">
              <button onclick="zoomMap(1.2)" style="background:#1e293b; color:#f8fafc; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-weight:bold;">+</button>
              <button onclick="zoomMap(0.8)" style="background:#1e293b; color:#f8fafc; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-weight:bold;">−</button>
              <button onclick="resetMap()" style="background:#1e293b; color:#94a3b8; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:11px;">Reset</button>
            </div>

            <!-- Legend Overlay -->
            <div style="position:absolute; top:14px; left:14px; background:rgba(15, 23, 42, 0.88); padding:8px 12px; border-radius:8px; border:1px solid #1e293b; font-size:11px; z-index:10; backdrop-filter:blur(4px);">
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#06b6d4;"></span>
                <span style="color:#cbd5e1;">🎣 Fishing (Net / Rod)</span>
              </div>
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#f59e0b;"></span>
                <span style="color:#cbd5e1;">👤 NPC / Quest</span>
              </div>
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#ec4899;"></span>
                <span style="color:#cbd5e1;">✨ Shrine / Relic</span>
              </div>
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#38bdf8;"></span>
                <span style="color:#cbd5e1;">Canonical Region</span>
              </div>
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#10b981;"></span>
                <span style="color:#cbd5e1;">Loot Cache</span>
              </div>
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="display:inline-block; width:9px; height:9px; transform:rotate(45deg); background:#ef4444;"></span>
                <span style="color:#cbd5e1;">Boss Arena Gate</span>
              </div>
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#a855f7;"></span>
                <span style="color:#cbd5e1;">🪦 Gravestone</span>
              </div>
            </div>
          </div>

          <!-- Region & Marker Inspector Panel -->
          <div style="background:#0c1322; border:1px solid #1c283f; border-radius:12px; padding:16px; display:flex; flex-direction:column;">
            <div style="border-bottom:1px solid #1e2c45; padding-bottom:10px; margin-bottom:12px;">
              <h3 id="map-inspector-title" style="margin:0; color:#f8fafc; font-size:16px;">Central Ashenfall (Overworld)</h3>
              <div id="map-inspector-sub" style="font-size:12px; color:#94a3b8; margin-top:2px;">Biome: Plains & Heartland | Weather: Rain Light</div>
            </div>
            
            <div id="map-inspector-body" style="flex:1; overflow-y:auto; font-size:13px; color:#cbd5e1;">
              <div style="margin-bottom:12px;">
                <div style="font-weight:600; color:#38bdf8; margin-bottom:4px;">Active Telemetry & Loot Caches</div>
                <div id="map-inspector-chests" style="color:#94a3b8; font-size:12px;">Click any region or marker to inspect localized respawn timers, dungeon caches, and boss gates.</div>
              </div>

              <div style="margin-top:14px; border-top:1px solid #1e2c45; padding-top:10px;">
                <div style="font-weight:600; color:#e2e8f0; margin-bottom:4px;">Current Weather & Lore</div>
                <div id="map-inspector-lore" style="font-size:12px; color:#94a3b8; line-height:1.5;">
                  The central expanse of Dragonwilds where adventurers establish foundations, access initial trial stones, and venture outward to outer territories.
                </div>
              </div>
            </div>
          </div>
        </div>
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

    <!-- VIEW 8: STORAGE & ITEM INVENTORY TRACKER -->
    <div id="view-items" style="display:none;">
      <div class="card" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
          <div>
            <h2 style="margin:0; font-size:20px; font-weight:bold; color:#f8fafc; display:flex; align-items:center; gap:8px;">
              <span>📦</span> Storage & Stored Item Tracker
            </h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">
              Search items across storage containers, inspect server totals, and identify exact container locations and owners.
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:10px;">
            <select id="storage-save-select" onchange="loadStorageTracker()"
                    style="background:#131c2e; border:1px solid #1e2c45; color:#cbd5e1; padding:6px 12px; border-radius:6px; font-size:12px; outline:none;">
              <option value="">Latest World Save</option>
              <option value="The Losers.sav">The Losers.sav</option>
              <option value="Hardcore Losers.sav">Hardcore Losers.sav</option>
            </select>
            <span class="data-source-badge saved" title="Directly parsed from container inventories in active save snapshot">💾 Save File</span>
          </div>
        </div>

        <!-- Metric summary pills -->
        <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-bottom:16px;">
          <div class="card" style="padding:14px; background:#111b2b; border:1px solid #1c283f;">
            <div style="font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px;">Active Storage Units</div>
            <div style="font-size:22px; font-weight:bold; color:#38bdf8; margin-top:4px;" id="storage-stat-units">0</div>
          </div>
          <div class="card" style="padding:14px; background:#111b2b; border:1px solid #1c283f;">
            <div style="font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px;">Server Stored Items</div>
            <div style="font-size:22px; font-weight:bold; color:#10b981; margin-top:4px;" id="storage-stat-items">0</div>
          </div>
          <div class="card" style="padding:14px; background:#111b2b; border:1px solid #1c283f;">
            <div style="font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px;">Unique Item Types</div>
            <div style="font-size:22px; font-weight:bold; color:#f59e0b; margin-top:4px;" id="storage-stat-types">0</div>
          </div>
        </div>

        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <input type="text" id="items-search-input" placeholder="Search stored items by name, category, container, or owner (e.g. Ash Logs, Rune, Dwellberry, Mango)..." oninput="searchStorageLive()"
                 style="flex:1; min-width:280px; background:#131c2e; border:1px solid #1e2c45; color:#f8fafc; padding:10px 14px; border-radius:8px; font-size:13.5px; outline:none;">
          <div class="pill-group">
            <button class="pill-btn active" id="btn-tab-stored-items" onclick="switchStorageTab('items')">Stored Items</button>
            <button class="pill-btn" id="btn-tab-containers" onclick="switchStorageTab('containers')">Storage Units</button>
          </div>
        </div>
      </div>

      <!-- Panel 1: Stored Items Across All Containers -->
      <div id="storage-panel-items" class="card">
        <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
              <th>Item Name / Identifier</th>
              <th>Total Stored Count</th>
              <th>Containers Present In</th>
              <th>Locations & Quantities</th>
            </tr>
          </thead>
          <tbody id="items-table-body">
            <tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:24px;">Loading stored items from save...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- Panel 2: Storage Units Browser -->
      <div id="storage-panel-containers" class="card" style="display:none;">
        <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
              <th>Storage Unit / Chest</th>
              <th>Owner</th>
              <th>Capacity</th>
              <th>Occupied Slots</th>
              <th>Total Items</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="containers-table-body">
            <tr><td colspan="6" style="color:#94a3b8; text-align:center; padding:24px;">Loading storage units...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- VIEW 9: BOSS ENCOUNTERS & WORLD ARENAS -->
    <div id="view-bosses" style="display:none;">
      <div class="card" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div>
            <h2 style="margin:0; font-size:20px; font-weight:bold; color:#f8fafc; display:flex; align-items:center; gap:8px;">
              <span>⚔️</span> Boss Encounters & World Arenas
            </h2>
            <div style="font-size:13px; color:#94a3b8; margin-top:2px;">
              Objective verification of canonical world boss gates, sanctums, and trial arenas in the active save.
            </div>
          </div>
          <div>
            <span class="data-source-badge saved" title="Extracted from active world save teleporters and gateways">💾 Save File</span>
          </div>
        </div>
      </div>

      <div class="grid" style="margin-bottom:20px;">
        <div class="card">
          <div class="icon">🏛️</div>
          <div class="label">Total Major Boss Arenas</div>
          <div class="value" id="boss-stat-total">7</div>
        </div>
        <div class="card">
          <div class="icon">🔓</div>
          <div class="label">Active / Discovered Gates</div>
          <div class="value" id="boss-stat-discovered" style="color:#34d399;">0</div>
        </div>
        <div class="card">
          <div class="icon">🗺️</div>
          <div class="label">Active World Save</div>
          <div class="value" id="boss-stat-save" style="font-size:15px; color:#f8fafc; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">--</div>
        </div>
      </div>

      <!-- CAMPAIGN MILESTONES & WORLD ACHIEVEMENTS -->
      <div class="card" style="margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <h3 style="margin:0; color:#f8fafc; font-size:16px; display:flex; align-items:center; gap:8px;">
            <span>🏆</span> Campaign Milestones & World Progress
          </h3>
          <span class="data-source-badge saved" title="Extracted from active world save progression JSON">💾 Save File</span>
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:10px;" id="campaign-milestones-grid">
          <div style="background:#0c1322; border:1px solid #1c283f; padding:12px; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:4px;">✨</div>
            <div style="font-size:11px; color:#94a3b8; text-transform:uppercase;">Spells Mastered</div>
            <div style="font-size:18px; font-weight:bold; color:#38bdf8;" id="camp-stat-spells">0</div>
          </div>
          <div style="background:#0c1322; border:1px solid #1c283f; padding:12px; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:4px;">📐</div>
            <div style="font-size:11px; color:#94a3b8; text-transform:uppercase;">Blueprints</div>
            <div style="font-size:18px; font-weight:bold; color:#a78bfa;" id="camp-stat-buildings">0</div>
          </div>
          <div style="background:#0c1322; border:1px solid #1c283f; padding:12px; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:4px;">📜</div>
            <div style="font-size:11px; color:#94a3b8; text-transform:uppercase;">Recipes</div>
            <div style="font-size:18px; font-weight:bold; color:#facc15;" id="camp-stat-recipes">0</div>
          </div>
          <div style="background:#0c1322; border:1px solid #1c283f; padding:12px; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:4px;">⛩️</div>
            <div style="font-size:11px; color:#94a3b8; text-transform:uppercase;">Shrines</div>
            <div style="font-size:18px; font-weight:bold; color:#34d399;" id="camp-stat-shrines">0</div>
          </div>
          <div style="background:#0c1322; border:1px solid #1c283f; padding:12px; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:4px;">💀</div>
            <div style="font-size:11px; color:#94a3b8; text-transform:uppercase;">Elites Slain</div>
            <div style="font-size:18px; font-weight:bold; color:#f87171;" id="camp-stat-elites">0</div>
          </div>
          <div style="background:#0c1322; border:1px solid #1c283f; padding:12px; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:4px;">🪦</div>
            <div style="font-size:11px; color:#94a3b8; text-transform:uppercase;">Gravestones</div>
            <div style="font-size:18px; font-weight:bold; color:#c084fc;" id="camp-stat-graves">0</div>
          </div>
          <div style="background:#0c1322; border:1px solid #1c283f; padding:12px; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:4px;">⛺</div>
            <div style="font-size:11px; color:#94a3b8; text-transform:uppercase;">Camps / Beds</div>
            <div style="font-size:18px; font-weight:bold; color:#22d3ee;" id="camp-stat-camps">0</div>
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom:20px;">
        <h3 style="margin-top:0; color:#f8fafc; font-size:16px; display:flex; align-items:center; gap:8px;">
          <span>👑</span> Canonical Boss Sanctums & Arenas
        </h3>
        <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
              <th>Boss Encounter / Arena</th>
              <th>Lore Region</th>
              <th>Classification</th>
              <th>World Status</th>
            </tr>
          </thead>
          <tbody id="bosses-table-body">
            <tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:24px;">Scanning boss teleporters and gateways...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- LIVE SERVER EVENT STREAM -->
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <h3 style="margin:0; color:#f8fafc; font-size:16px; display:flex; align-items:center; gap:8px;">
            <span>⚡</span> Live Server World Events & Raids
          </h3>
          <span class="data-source-badge live" title="Direct telemetry from RSDragonwilds.log">⚡ Live Telemetry</span>
        </div>
        <table class="table" style="width:100%; text-align:left; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:1px solid #1c283f; color:#94a3b8; font-size:12px; text-transform:uppercase;">
              <th>Timestamp</th>
              <th>Event Category</th>
              <th>Telemetry Message</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody id="world-events-table-body">
            <tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:20px;">Streaming live world events from server log...</td></tr>
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

  vOverview.style.display = 'none';
  if (vMap) vMap.style.display = 'none';
  vLogs.style.display = 'none';
  vPlayers.style.display = 'none';
  if (vBackups) vBackups.style.display = 'none';
  vLeaderboard.style.display = 'none';
  vEvents.style.display = 'none';
  if (vRespawns) vRespawns.style.display = 'none';
  if (vFarming) vFarming.style.display = 'none';
  if (vItems) vItems.style.display = 'none';
  if (vBosses) vBosses.style.display = 'none';

  if (tab === 'overview') {
    title.innerText = 'Overview';
    subtitle.innerText = 'Real-time overview of your Dragonwilds server';
    vOverview.style.display = 'block';
  } else if (tab === 'map') {
    title.innerText = 'Interactive World Map';
    subtitle.innerText = 'Territorial radar plotting canonical regions, chest respawn timers & boss gates';
    if (vMap) vMap.style.display = 'block';
    initWorldMap();
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
    title.innerText = 'Storage & Item Tracker';
    subtitle.innerText = 'Search items across storage containers, inspect server totals & track unit locations';
    if (vItems) vItems.style.display = 'block';
    loadStorageTracker();
  } else if (tab === 'bosses') {
    title.innerText = 'Boss Arenas & Events';
    subtitle.innerText = 'Objective encounter gates, boss arenas & live world raid telemetry';
    if (vBosses) vBosses.style.display = 'block';
    loadBosses();
    loadLiveWorldEvents();
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
  // Day starts at top (0° / 12 o'clock) and sweeps clockwise through 90° (3 o'clock) to 240° (8 o'clock)
  const clipPathEl = document.getElementById('path-day-passed');
  if (clipPathEl) {
    const cx = 50, cy = 50, r = 46;
    const startDeg = 0.0;
    const startRad = (startDeg - 90) * Math.PI / 180;
    const x0 = cx + r * Math.cos(startRad);
    const y0 = cy + r * Math.sin(startRad);

    // Current needle clamped to day arc (0° to 240°)
    let curDeg = angle;
    let delta = curDeg;
    // Day arc length is 240°
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
          <div style="font-weight:600; color:#f8fafc; font-size:14px; display:flex; align-items:center; gap:8px;">
            <span>${escapeHtml(r.name)}</span>
            ${r.zone ? `<span style="font-size:10.5px; background:#1e293b; color:#38bdf8; padding:1px 6px; border-radius:4px; font-weight:normal;">${escapeHtml(r.zone)}</span>` : ''}
            <button onclick="switchTabToMapMarker('${escapeHtml(r.id)}')" style="background:transparent; border:1px solid #1e3a8a; color:#38bdf8; font-size:10px; padding:1px 6px; border-radius:4px; cursor:pointer;" title="View location on World Map">📍 Map</button>
          </div>
          <div style="font-family:monospace; font-size:11.5px; color:#64748b; margin-top:2px;">${escapeHtml(r.id)}</div>
        </td>
        <td style="padding:12px 14px; color:#cbd5e1; font-size:13px;">${escapeHtml(r.category)}</td>
        <td style="padding:12px 14px; color:#94a3b8; font-size:13px;">${escapeHtml(r.duration_formatted || '—')}</td>
        <td style="padding:12px 14px;">
          <strong style="color:${remainingColor}; font-size:13.5px;">${escapeHtml(r.remaining_formatted)}</strong>
          ${!r.is_ready && (r.respawn_epoch || r.respawn_time) ? `<div style="color:#64748b; font-size:11px;" title="${escapeHtml(formatLocalDate(r.respawn_epoch || r.respawn_time))}">Ready at ${escapeHtml(formatLocalDateTime(r.respawn_epoch || r.respawn_time))}</div>` : ''}
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
      cropsBody.innerHTML = '<tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:20px;">No wild or planted crop instances found in active save file.</td></tr>';
    } else {
      cropsBody.innerHTML = crops.map((c, cIdx) => {
        const plots = c.plots || [];
        const hasPlots = plots.length > 0;
        const accordionId = `crop-plots-${cIdx}`;

        const plotsHtml = hasPlots ? `
          <tr id="${accordionId}" style="display:none; background:#0b111e; border-bottom:1px solid #1c283f;">
            <td colspan="4" style="padding:14px 18px;">
              <div style="font-size:12px; font-weight:600; color:#38bdf8; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.5px;">
                Distinct In-World Plot Instances (${plots.length} unique locations in save)
              </div>
              <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:8px;">
                ${plots.map(p => `
                  <div style="background:#131d2e; border:1px solid #1e2c45; padding:8px 10px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <div style="font-weight:600; color:#f8fafc; font-size:12px;">Plot #${p.plot_number} (${escapeHtml(p.zone)})</div>
                      <div style="font-family:monospace; font-size:10.5px; color:#64748b;" title="${escapeHtml(p.instance_id)}">...${escapeHtml(p.short_id.slice(-14))}</div>
                    </div>
                    <span style="background:#064e3b; color:#34d399; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:600;">
                      ${escapeHtml(p.status)}
                    </span>
                  </div>
                `).join('')}
              </div>
            </td>
          </tr>
        ` : '';

        return `
          <tr style="border-bottom:1px solid #141f33; cursor:pointer;" onclick="toggleCropAccordion('${accordionId}', this)">
            <td style="padding:12px 14px; font-weight:600; color:#f8fafc; display:flex; align-items:center; gap:8px;">
              <span id="chevron-${accordionId}" style="color:#38bdf8; font-size:12px; transition:transform 0.2s;">▶</span>
              <span>${escapeHtml(c.name)}</span>
            </td>
            <td style="padding:12px 14px; color:#94a3b8; font-size:13px;">${escapeHtml(c.category)}</td>
            <td style="padding:12px 14px; font-weight:bold; color:#38bdf8;">
              ${c.count || 0}
              ${hasPlots ? `<span style="font-size:11px; font-weight:normal; color:#64748b; margin-left:4px;">(${plots.length} plots)</span>` : ''}
            </td>
            <td style="padding:12px 14px;">
              <span style="background:#064e3b; color:#34d399; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;">
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

      // Update badge counts
      const badge = document.getElementById('nav-items-count');
      if (badge && storageData.summary) {
        const total = storageData.summary.total_stored_items || 0;
        badge.innerText = total > 1000 ? `${(total/1000).toFixed(1)}k` : total;
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
    tbody.innerHTML = '<tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:24px;">No stored items match your query.</td></tr>';
    return;
  }

  const itemsToShow = items.slice(0, 150);
  tbody.innerHTML = itemsToShow.map(it => {
    // Generate location badges (up to 4, plus "+X more" if exceeded)
    const conts = it.containers || [];
    const shownConts = conts.slice(0, 4);
    const badgesHtml = shownConts.map(c => {
      const ownerPrefix = c.owner && c.owner !== 'World / Unowned' ? `<strong>${escapeHtml(c.owner)}:</strong> ` : '';
      return `<span style="display:inline-block; margin:2px 4px 2px 0; background:#1e293b; border:1px solid #334155; color:#cbd5e1; padding:3px 8px; border-radius:6px; font-size:11.5px;">
        ${ownerPrefix}${escapeHtml(c.container_name)} <span style="color:#38bdf8; font-weight:bold;">(x${c.count})</span>
      </span>`;
    }).join('');

    const moreHtml = conts.length > 4 
      ? `<span style="font-size:11px; color:#94a3b8; margin-left:4px;">+${conts.length - 4} more units</span>` 
      : '';

    const itemName = it.name || it.item_id;
    const itemSub = (it.raw_id && it.raw_id !== it.name) ? it.raw_id : it.item_id;
    const catBadge = it.category && it.category !== 'General' 
      ? `<span style="background:#1e293b; color:#94a3b8; border:1px solid #334155; font-size:10px; padding:1px 6px; border-radius:4px; font-weight:normal; letter-spacing:0.3px;">${escapeHtml(it.category)}</span>` 
      : '';

    return `
      <tr style="border-bottom:1px solid #141f33;">
        <td style="padding:10px 14px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <strong style="color:#f8fafc; font-size:13.5px;">${escapeHtml(itemName)}</strong>
            ${catBadge}
          </div>
          <div style="font-family:monospace; color:#64748b; font-size:11px; margin-top:2px;">
            ${escapeHtml(itemSub)}
          </div>
        </td>
        <td style="padding:10px 14px; font-weight:bold; color:#10b981; font-size:14px;">
          ${(it.total_count || 0).toLocaleString()}
        </td>
        <td style="padding:10px 14px;">
          <span style="background:#0f172a; color:#94a3b8; border:1px solid #1e293b; padding:2px 8px; border-radius:999px; font-size:11.5px; font-weight:600;">
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
    tbody.innerHTML += `<tr><td colspan="4" style="color:#64748b; text-align:center; padding:12px; font-size:12px;">Showing first 150 of ${items.length} stored item types. Use the search bar above to filter.</td></tr>`;
  }
}

function renderStorageUnits() {
  const tbody = document.getElementById('containers-table-body');
  if (!tbody) return;

  if (!storageUnitsData || storageUnitsData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:#94a3b8; text-align:center; padding:24px;">No storage units detected in current save snapshot.</td></tr>';
    return;
  }

  const unitsToShow = storageUnitsData.slice(0, 150);
  tbody.innerHTML = unitsToShow.map(c => {
    const ownerBadge = c.owner && c.owner !== 'World / Unowned'
      ? `<span style="background:#064e3b; color:#34d399; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">${escapeHtml(c.owner)}</span>`
      : `<span style="background:#1e293b; color:#94a3b8; padding:2px 8px; border-radius:6px; font-size:11px;">World / Unowned</span>`;

    return `
      <tr style="border-bottom:1px solid #141f33;">
        <td style="padding:10px 14px; font-weight:600; color:#f8fafc;">
          ${escapeHtml(c.name)}
        </td>
        <td style="padding:10px 14px;">
          ${ownerBadge}
        </td>
        <td style="padding:10px 14px; color:#cbd5e1; font-size:13px;">
          ${c.capacity} slots
        </td>
        <td style="padding:10px 14px; font-weight:600; color:#38bdf8; font-size:13px;">
          ${c.occupied_slots} used
        </td>
        <td style="padding:10px 14px; font-weight:bold; color:#10b981; font-size:13px;">
          ${(c.total_items || 0).toLocaleString()} items
        </td>
        <td style="padding:10px 14px;">
          <button class="pill-btn" style="font-size:11px; padding:3px 8px;" onclick="inspectContainer('${c.id}')">Inspect Slots</button>
        </td>
      </tr>
    `;
  }).join('');

  if (storageUnitsData.length > 150) {
    tbody.innerHTML += `<tr><td colspan="6" style="color:#64748b; text-align:center; padding:12px; font-size:12px;">Showing first 150 of ${storageUnitsData.length} storage containers.</td></tr>`;
  }
}

function inspectContainer(containerId) {
  const container = storageUnitsData.find(c => c.id === containerId);
  if (!container) return;

  const slots = container.slots || [];
  let modalHtml = `
    <div id="container-modal" style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; z-index:9999;">
      <div style="background:#0f172a; border:1px solid #1e293b; border-radius:12px; max-width:650px; width:90%; max-height:80vh; display:flex; flex-direction:column; padding:20px; box-shadow:0 10px 25px rgba(0,0,0,0.5);">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e2c45; padding-bottom:12px; margin-bottom:14px;">
          <div>
            <h3 style="margin:0; color:#f8fafc; font-size:18px;">${escapeHtml(container.name)}</h3>
            <div style="font-size:12px; color:#94a3b8; margin-top:2px;">Owner: ${escapeHtml(container.owner)} | Capacity: ${container.capacity} slots (${container.occupied_slots} occupied)</div>
          </div>
          <button onclick="document.getElementById('container-modal').remove()" style="background:#1e293b; border:none; color:#f8fafc; padding:6px 10px; border-radius:6px; cursor:pointer;">✕</button>
        </div>
        <div style="overflow-y:auto; flex:1;">
          <table style="width:100%; text-align:left; border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:1px solid #1e293b; color:#94a3b8; font-size:11px; text-transform:uppercase;">
                <th style="padding:8px;">Slot</th>
                <th style="padding:8px;">Item Name / Identifier</th>
                <th style="padding:8px;">Count</th>
                <th style="padding:8px;">Durability</th>
              </tr>
            </thead>
            <tbody>
              ${slots.length === 0 ? '<tr><td colspan="4" style="text-align:center; padding:18px; color:#64748b;">Container is empty</td></tr>' : slots.map(s => `
                <tr style="border-bottom:1px solid #141f33;">
                  <td style="padding:8px; color:#94a3b8; font-family:monospace;">#${s.slot}</td>
                  <td style="padding:8px;">
                    <div style="font-weight:600; color:#38bdf8; font-size:13px; display:flex; align-items:center; gap:6px;">
                      <span>${escapeHtml(s.name || s.item_id)}</span>
                      ${s.category && s.category !== 'General' ? `<span style="background:#1e293b; color:#94a3b8; border:1px solid #334155; font-size:9.5px; padding:0 5px; border-radius:3px;">${escapeHtml(s.category)}</span>` : ''}
                    </div>
                    <div style="font-size:10.5px; color:#64748b; font-family:monospace; margin-top:2px;">
                      ${escapeHtml(s.raw_id && s.raw_id !== s.name ? s.raw_id : s.item_id)}
                    </div>
                  </td>
                  <td style="padding:8px; font-weight:bold; color:#10b981;">x${s.count || 1}</td>
                  <td style="padding:8px; color:#cbd5e1; font-size:12px;">${s.durability !== undefined && s.durability !== null ? s.durability : '—'}</td>
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
  const badge = document.getElementById('nav-bosses-count');

  if (elTotal) elTotal.innerText = s.total_boss_arenas || 7;
  if (elDisc) elDisc.innerText = s.discovered_arenas || 0;
  if (elSave) elSave.innerText = s.active_world_save || 'None';
  if (badge) badge.innerText = `${s.discovered_arenas || 0}/${s.total_boss_arenas || 7}`;

  const tbody = document.getElementById('bosses-table-body');
  if (!tbody) return;

  const encounters = bossesData.encounters || [];
  if (encounters.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:24px;">No boss encounters discovered in active world.</td></tr>';
    return;
  }

  tbody.innerHTML = encounters.map(b => {
    const statusBadge = b.world_discovered
      ? '<span style="background:#064e3b; color:#34d399; padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">🟢 Discovered & Active</span>'
      : '<span style="background:#1e293b; color:#94a3b8; padding:3px 10px; border-radius:999px; font-size:11.5px; font-weight:bold;">🔒 Undiscovered</span>';

    return `
      <tr style="border-bottom:1px solid #141f33;">
        <td style="padding:12px 14px;">
          <div style="font-weight:600; color:#f8fafc; font-size:14px;">${escapeHtml(b.name)}</div>
          <div style="font-size:12px; color:#64748b; margin-top:2px;">${escapeHtml(b.description)}</div>
        </td>
        <td style="padding:12px 14px; color:#cbd5e1; font-size:13px;">${escapeHtml(b.lore_region)}</td>
        <td style="padding:12px 14px;">
          <span style="background:#1e293b; color:#cbd5e1; padding:2px 8px; border-radius:6px; font-size:11.5px; font-weight:500;">
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
    tbody.innerHTML = '<tr><td colspan="4" style="color:#94a3b8; text-align:center; padding:20px;">No recent world events or raids logged.</td></tr>';
    return;
  }

  tbody.innerHTML = worldEventsData.map(ev => {
    let typeStyle = 'background:#1e293b; color:#cbd5e1;';
    if (ev.badge === 'raid') typeStyle = 'background:#7f1d1d; color:#fca5a5;';
    else if (ev.badge === 'combat') typeStyle = 'background:#78350f; color:#fde68a;';
    else if (ev.badge === 'chest') typeStyle = 'background:#064e3b; color:#34d399;';
    else if (ev.badge === 'player') typeStyle = 'background:#1e3a8a; color:#93c5fd;';

    return `
      <tr style="border-bottom:1px solid #141f33;">
        <td style="padding:10px 14px; font-family:monospace; color:#94a3b8; font-size:12px; white-space:nowrap;" title="${escapeHtml(formatLocalDate(ev.epoch || ev.iso || ev.timestamp))}">${escapeHtml(formatLocalDateTime(ev.epoch || ev.iso || ev.timestamp))}</td>
        <td style="padding:10px 14px;">
          <span style="${typeStyle} padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">
            ${escapeHtml(ev.type)}
          </span>
        </td>
        <td style="padding:10px 14px; color:#f8fafc; font-size:13px;">${escapeHtml(ev.message)}</td>
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
  'Desert': { fill: 'rgba(217, 119, 6, 0.22)', stroke: '#f59e0b', text: '#fbbf24' },
  'Plains': { fill: 'rgba(16, 185, 129, 0.18)', stroke: '#10b981', text: '#34d399' },
  'Meadow': { fill: 'rgba(52, 211, 153, 0.18)', stroke: '#34d399', text: '#6ee7b7' },
  'Forest': { fill: 'rgba(5, 150, 105, 0.22)', stroke: '#10b981', text: '#a7f3d0' },
  'Highlands': { fill: 'rgba(14, 165, 233, 0.22)', stroke: '#0284c7', text: '#38bdf8' },
  'Mountains': { fill: 'rgba(125, 211, 252, 0.22)', stroke: '#38bdf8', text: '#bae6fd' },
  'Wasteland': { fill: 'rgba(100, 116, 139, 0.22)', stroke: '#64748b', text: '#94a3b8' },
  'Volcanic': { fill: 'rgba(239, 68, 68, 0.22)', stroke: '#ef4444', text: '#fca5a5' },
  'Fortress': { fill: 'rgba(99, 102, 241, 0.22)', stroke: '#6366f1', text: '#a5b4fc' },
  'Ruins': { fill: 'rgba(139, 92, 246, 0.22)', stroke: '#8b5cf6', text: '#c4b5fd' },
  'Sanctuary': { fill: 'rgba(168, 85, 247, 0.22)', stroke: '#a855f7', text: '#d8b4fe' },
  'Subterranean': { fill: 'rgba(71, 85, 105, 0.30)', stroke: '#64748b', text: '#cbd5e1' },
  'Swamp': { fill: 'rgba(13, 148, 136, 0.22)', stroke: '#0d9488', text: '#5eead4' },
  'Lake': { fill: 'rgba(6, 182, 212, 0.22)', stroke: '#06b6d4', text: '#67e8f9' },
  'Mystic': { fill: 'rgba(192, 132, 252, 0.22)', stroke: '#c084fc', text: '#e9d5ff' },
  'Arcane': { fill: 'rgba(236, 72, 153, 0.22)', stroke: '#ec4899', text: '#f472b6' }
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
      fetch('/api/world/actors?category=fishing,npcs,shrines,shortcuts').then(r => r.json()).catch(() => ({}))
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
  const zone = grave.zone || 'Overworld';
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
  if (index === 0) return { wx: 340, wy: 520 };
  if (index === 1) return { wx: 230, wy: 460 };
  return { wx: 310 + (index * 26), wy: 540 };
}

function getChestWorldCoords(chest, index) {
  const zone = chest.zone || 'Overworld';
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
  const n = ((boss.name || '') + ' ' + (boss.id || '')).toLowerCase();
  if (n.includes('dragon') || n.includes('velgar')) return { wx: 530, wy: 350 };
  if (n.includes('kalphite')) return { wx: 720, wy: 720 };
  if (n.includes('fight cave') || n.includes('fuzan') || n.includes('tztok') || n.includes('fight caves')) return { wx: 690, wy: 230 };
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
    const liveChests = mapRespawns.filter(r => r.source === 'live_log' || r.category === 'Chests & Vaults');
    for (let i = 0; i < liveChests.length; i++) {
      const c = liveChests[i];
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

    // Filter chests in this region
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
      chestsEl.innerHTML = '<span style="color:#64748b; font-size:12px;">No active dungeon chests currently assigned to this sector.</span>';
    } else {
      chestsEl.innerHTML = `
        <div style="font-size:12px; color:#38bdf8; font-weight:600; margin-bottom:6px;">
          ${regChests.length} Localized Dungeon Caches & Loot Nodes:
        </div>
        <div style="display:flex; flex-direction:column; gap:6px;">
          ${regChests.map(c => `
            <div style="background:#131c2e; border:1px solid #1e2c45; padding:6px 10px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
              <div>
                <div style="font-weight:600; color:#f8fafc; font-size:12px;">${escapeHtml(c.name)}</div>
                <div style="font-size:10.5px; color:#64748b;">${escapeHtml(c.duration_formatted ? 'Cycle: ' + c.duration_formatted : '')}</div>
              </div>
              <div>
                ${c.is_ready
                  ? '<span style="background:#064e3b; color:#34d399; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">🟢 Ready to Loot</span>'
                  : `<span style="background:#78350f; color:#fde68a; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold;">⏳ ${escapeHtml(c.remaining_formatted)}</span>`
                }
              </div>
            </div>
          `).join('')}
        </div>
      `;
    }
  } else if (target.type === 'chest') {
    const c = target.data;
    titleEl.innerText = c.name;
    subEl.innerText = `Loot Cache | Territory: ${c.zone || 'Overworld'} | Category: ${c.category}`;
    const readyTimeStr = c.respawn_epoch || c.respawn_time ? formatLocalDateTime(c.respawn_epoch || c.respawn_time) : 'Now';

    chestsEl.innerHTML = `
      <div style="background:#131c2e; border:1px solid #1e2c45; padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:#f8fafc;">Loot Status</span>
          ${c.is_ready
            ? '<span style="background:#064e3b; color:#34d399; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟢 Ready to Loot</span>'
            : '<span style="background:#78350f; color:#fde68a; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">⏳ Respawning</span>'
          }
        </div>
        <div style="font-size:12px; color:#94a3b8; line-height:1.6;">
          <div><strong>Remaining Time:</strong> <span style="color:#f8fafc;">${escapeHtml(c.remaining_formatted)}</span></div>
          ${!c.is_ready ? `<div><strong>Ready At:</strong> <span style="color:#38bdf8;">${escapeHtml(readyTimeStr)}</span></div>` : ''}
          <div><strong>Cycle Interval:</strong> <span style="color:#94a3b8;">${escapeHtml(c.duration_formatted || 'Standard')}</span></div>
          <div><strong>Entity ID:</strong> <span style="font-family:monospace; font-size:11px; color:#64748b;">${escapeHtml(c.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Objective treasure container tracked live from dedicated server logs. Loot respawn timers operate on continuous server-side ticks.`;
  } else if (target.type === 'boss') {
    const b = target.data;
    titleEl.innerText = b.name;
    subEl.innerText = `Boss Arena | Lore Region: ${b.lore_region} | Category: ${b.category}`;
    chestsEl.innerHTML = `
      <div style="background:#131c2e; border:1px solid #1e2c45; padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:#f8fafc;">Encounter Gate</span>
          ${b.unlocked
            ? '<span style="background:#064e3b; color:#34d399; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🟢 Discovered & Active</span>'
            : '<span style="background:#1e293b; color:#94a3b8; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔒 Undiscovered</span>'
          }
        </div>
        <div style="font-size:12px; color:#cbd5e1; line-height:1.5;">${escapeHtml(b.description || 'Major world encounter.')}</div>
      </div>
    `;
    loreEl.innerText = `Canonical sanctum or portal arena for high-tier combat trials. Verified through in-world teleporter blueprints in active server saves.`;
  } else if (target.type === 'grave') {
    const g = target.data;
    titleEl.innerText = g.name || `Player Gravestone #${g.index}`;
    subEl.innerText = `Death Marker | Sector: ${g.zone || 'Overworld'} | Permanent In-World Grave`;
    chestsEl.innerHTML = `
      <div style="background:#131c2e; border:1px solid #1e2c45; padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:#f8fafc;">Death Marker Status</span>
          <span style="background:#581c87; color:#d8b4fe; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🪦 Persistent Grave</span>
        </div>
        <div style="font-size:12px; color:#94a3b8; line-height:1.6;">
          <div><strong>Grave Number:</strong> <span style="color:#f8fafc;">#${g.index}</span></div>
          <div><strong>Territory Sector:</strong> <span style="color:#38bdf8;">${escapeHtml(g.zone)}</span></div>
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:#64748b;">${escapeHtml(g.short_id || g.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Permanent player death gravestone in Hardcore mode. Holds the fallen adventurer's belongings and inventory.`;
  } else if (target.type === 'camp') {
    const camp = target.data;
    titleEl.innerText = camp.name || `Settlement Bedroll #${camp.index}`;
    subEl.innerText = `Settlement Landmark | Sector: ${camp.zone} | Type: Claimed Bedroll`;
    chestsEl.innerHTML = `
      <div style="background:#131c2e; border:1px solid #1e2c45; padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:#f8fafc;">Camp Status</span>
          <span style="background:#083344; color:#67e8f9; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">⛺ Active Spawn Point</span>
        </div>
        <div style="font-size:12px; color:#94a3b8; line-height:1.6;">
          <div><strong>Bedroll Index:</strong> <span style="color:#f8fafc;">#${camp.index}</span></div>
          <div><strong>Territory Sector:</strong> <span style="color:#38bdf8;">${escapeHtml(camp.zone)}</span></div>
          <div><strong>Spawn Point Type:</strong> <span style="color:#f8fafc;">Territorial Bedroll Camp</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Active player bedroll anchor registered in active server save. Functions as territorial respawn point.`;
  } else if (target.type === 'fishing') {
    const f = target.data;
    titleEl.innerText = f.title;
    subEl.innerText = `Fishing Resource • Grid Cell: ${f.cell} • Water Elevation: ${f.world_pos.z} cm`;
    chestsEl.innerHTML = `
      <div style="background:#131c2e; border:1px solid #1e2c45; padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:#f8fafc;">Fishing Node Details</span>
          <span style="background:#083344; color:#67e8f9; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🎣 Active Spot</span>
        </div>
        <div style="font-size:12px; color:#94a3b8; line-height:1.6;">
          <div><strong>Fishing Method:</strong> <span style="color:#f8fafc;">${escapeHtml(f.title)}</span></div>
          <div><strong>Requirement:</strong> <span style="color:#67e8f9;">${escapeHtml(f.hint)}</span></div>
          <div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:#cbd5e1;">${escapeHtml(f.cell)}</span></div>
          <div><strong>Exact 3D Coordinates:</strong> <span style="color:#38bdf8;">X=${f.world_pos.x}, Y=${f.world_pos.y}, Z=${f.world_pos.z}</span></div>
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:#64748b;">${escapeHtml(f.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = `Permanent world fishing spawner stream-loaded from Unreal Engine level geometry. Harvestable by players with appropriate tackle.`;
  } else if (target.type === 'npc') {
    const n = target.data;
    titleEl.innerText = n.title;
    subEl.innerText = `Interactive NPC • Grid Cell: ${n.cell} • Elevation: ${n.world_pos.z} cm`;
    chestsEl.innerHTML = `
      <div style="background:#131c2e; border:1px solid #1e2c45; padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:#f8fafc;">Character Status</span>
          <span style="background:#78350f; color:#fde68a; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">👤 Persistent Character</span>
        </div>
        <div style="font-size:12px; color:#94a3b8; line-height:1.6;">
          <div><strong>Role & Interaction:</strong> <span style="color:#f8fafc;">${escapeHtml(n.hint)}</span></div>
          <div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:#cbd5e1;">${escapeHtml(n.cell)}</span></div>
          <div><strong>Blueprint Class:</strong> <span style="font-family:monospace; font-size:11px; color:#cbd5e1;">${escapeHtml(n.class_name)}</span></div>
          <div><strong>Exact 3D Coordinates:</strong> <span style="color:#38bdf8;">X=${n.world_pos.x}, Y=${n.world_pos.y}, Z=${n.world_pos.z}</span></div>
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:#64748b;">${escapeHtml(n.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = n.hint || `World character registered in active level persistence cache.`;
  } else if (target.type === 'shrine') {
    const s = target.data;
    titleEl.innerText = s.title;
    subEl.innerText = `Sacred Monument • Grid Cell: ${s.cell} • Elevation: ${s.world_pos.z} cm`;
    chestsEl.innerHTML = `
      <div style="background:#131c2e; border:1px solid #1e2c45; padding:10px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:13px; font-weight:600; color:#f8fafc;">Monument Blessing</span>
          <span style="background:#500724; color:#fbcfe8; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">✨ Active Shrine</span>
        </div>
        <div style="font-size:12px; color:#94a3b8; line-height:1.6;">
          <div><strong>Sanctuary Effect:</strong> <span style="color:#f8fafc;">${escapeHtml(s.hint)}</span></div>
          <div><strong>World Grid Cell:</strong> <span style="font-family:monospace; color:#cbd5e1;">${escapeHtml(s.cell)}</span></div>
          <div><strong>Exact 3D Coordinates:</strong> <span style="color:#38bdf8;">X=${s.world_pos.x}, Y=${s.world_pos.y}, Z=${s.world_pos.z}</span></div>
          <div><strong>Persistence UAID:</strong> <span style="font-family:monospace; font-size:11px; color:#64748b;">${escapeHtml(s.id)}</span></div>
        </div>
      </div>
    `;
    loreEl.innerText = s.hint || `Sacred landmark in Ashenfall.`;
  }

  if (doRender) renderWorldMap();
}

function switchTabToMapMarker(markerId) {
  setTab('map');
  const findChest = mapRespawns.find(r => r.id === markerId);
  if (findChest) {
    const idx = mapRespawns.indexOf(findChest);
    const coords = getChestWorldCoords(findChest, idx);
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

function drawMapLabel(ctx, text, x, y, textColor = '#f8fafc', bgColor = 'rgba(15, 23, 42, 0.88)') {
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
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
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
  ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(217, 119, 6, 0.6)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // North needle
  ctx.fillStyle = '#ef4444';
  ctx.beginPath();
  ctx.moveTo(cx, cy - 16);
  ctx.lineTo(cx - 5, cy);
  ctx.lineTo(cx, cy - 2);
  ctx.fill();

  // South needle
  ctx.fillStyle = '#94a3b8';
  ctx.beginPath();
  ctx.moveTo(cx, cy + 16);
  ctx.lineTo(cx + 5, cy);
  ctx.lineTo(cx, cy + 2);
  ctx.fill();

  ctx.fillStyle = '#f8fafc';
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
  let badgeColor = '#38bdf8';

  if (target.type === 'region') {
    title = target.data.name;
    badge = `Territory • ${target.data.biome || 'Plains'}`;
  } else if (target.type === 'boss') {
    title = target.data.name;
    badge = '⚔️ Boss Arena Gate';
    badgeColor = '#f87171';
  } else if (target.type === 'chest') {
    title = target.data.name;
    badge = target.data.is_ready ? '🟢 Ready to Loot' : `⏳ ${target.data.remaining_formatted}`;
    badgeColor = target.data.is_ready ? '#34d399' : '#f59e0b';
  } else if (target.type === 'grave') {
    title = target.data.name;
    badge = `🪦 Grave (${target.data.zone || 'Overworld'})`;
    badgeColor = '#c084fc';
  } else if (target.type === 'camp') {
    title = target.data.name;
    badge = '⛺ Claimed Bedroll Camp';
    badgeColor = '#67e8f9';
  } else if (target.type === 'fishing') {
    title = target.data.title;
    badge = `🎣 Fishing Spot (${target.data.cell})`;
    badgeColor = '#06b6d4';
  } else if (target.type === 'npc') {
    title = target.data.title;
    badge = `👤 NPC / Quest (${target.data.cell})`;
    badgeColor = '#f59e0b';
  } else if (target.type === 'shrine') {
    title = target.data.title;
    badge = `✨ Shrine (${target.data.cell})`;
    badgeColor = '#ec4899';
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

  ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(bx, by, boxWidth, boxHeight, 6);
  } else {
    ctx.rect(bx, by, boxWidth, boxHeight);
  }
  ctx.fill();
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.5)';
  ctx.lineWidth = 1.2;
  ctx.stroke();

  ctx.fillStyle = '#f8fafc';
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
  ctx.fillStyle = '#070b14';
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.translate(width / 2 + mapTransform.x, height / 2 + mapTransform.y);
  ctx.scale(mapTransform.scale, mapTransform.scale);
  ctx.translate(-500, -500);

  // 1. Draw Ashenfall Topographical Continent Map
  if (worldMapImgLoaded && worldMapImg.complete && worldMapImg.naturalWidth > 0) {
    ctx.drawImage(worldMapImg, 0, 0, 1000, 1000);
    ctx.strokeStyle = 'rgba(217, 119, 6, 0.4)';
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, 1000, 1000);
  } else {
    ctx.fillStyle = '#111827';
    ctx.fillRect(0, 0, 1000, 1000);
    ctx.fillStyle = '#64748b';
    ctx.font = '14px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Loading Ashenfall Topographical Map...', 500, 500);
  }

  // 2. Travel Roads / Leyline Pathways (amber trails)
  const regionMap = {};
  for (const reg of mapRegions) {
    regionMap[reg.id] = reg;
  }

  ctx.strokeStyle = 'rgba(251, 191, 36, 0.35)';
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
      ctx.strokeStyle = isSelected ? '#38bdf8' : '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(rx, ry, 7, 0, Math.PI * 2);
    ctx.fillStyle = isMatch ? theme.stroke : '#475569';
    ctx.fill();
    ctx.strokeStyle = '#070b14';
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
      drawMapLabel(ctx, reg.name, rx, ry + 16, '#f8fafc', 'rgba(15, 23, 42, 0.9)');
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
      ctx.fillStyle = isMatch ? 'rgba(239, 68, 68, 0.9)' : 'rgba(71, 85, 105, 0.5)';
      ctx.fill();
      ctx.strokeStyle = isSelected ? '#38bdf8' : (isHovered ? '#ffffff' : '#fbbf24');
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.stroke();
      ctx.restore();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(bw.wx, bw.wy, 18, 0, Math.PI * 2);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, '⚔️ ' + b.name, bw.wx, bw.wy - 18, '#fca5a5', 'rgba(69, 10, 10, 0.9)');
      }
    }
  }

  // 5. Live Loot Chests & Dungeon Caches
  if (mapFilterLayer === 'all' || mapFilterLayer === 'chests') {
    const liveChests = mapRespawns.filter(r => r.source === 'live_log' || r.category === 'Chests & Vaults');
    for (let i = 0; i < liveChests.length; i++) {
      const c = liveChests[i];
      const cw = getChestWorldCoords(c, i);
      const isSelected = mapSelectedTarget && mapSelectedTarget.type === 'chest' && mapSelectedTarget.data.id === c.id;
      const isHovered = mapHoveredTarget && mapHoveredTarget.type === 'chest' && mapHoveredTarget.data.id === c.id;
      const isMatch = !mapSearchQuery || c.name.toLowerCase().includes(mapSearchQuery);

      const pinColor = c.is_ready ? '#10b981' : '#f59e0b';

      ctx.beginPath();
      ctx.arc(cw.wx, cw.wy, 6, 0, Math.PI * 2);
      ctx.fillStyle = isMatch ? pinColor : '#475569';
      ctx.fill();
      ctx.strokeStyle = '#070b14';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (!c.is_ready && isMatch) {
        ctx.beginPath();
        ctx.arc(cw.wx, cw.wy, 11, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.6)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(cw.wx, cw.wy, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#38bdf8' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        const labelText = c.is_ready ? `${c.name} (Ready)` : `${c.name} (${c.remaining_formatted})`;
        drawMapLabel(ctx, labelText, cw.wx, cw.wy + 15, c.is_ready ? '#34d399' : '#fde68a');
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
      ctx.fillStyle = isMatch ? 'rgba(168, 85, 247, 0.95)' : '#475569';
      ctx.fill();
      ctx.strokeStyle = '#070b14';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(gw.wx, gw.wy, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#38bdf8' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, `🪦 #${g.index} Grave`, gw.wx, gw.wy + 15, '#e9d5ff', 'rgba(46, 16, 101, 0.9)');
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
      ctx.fillStyle = isMatch ? 'rgba(6, 182, 212, 0.95)' : '#475569';
      ctx.fill();
      ctx.strokeStyle = '#070b14';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(cw.wx, cw.wy, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#38bdf8' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, `⛺ #${camp.index} Camp`, cw.wx, cw.wy + 15, '#67e8f9', 'rgba(8, 51, 68, 0.9)');
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
      ctx.fillStyle = isMatch ? '#06b6d4' : '#475569';
      ctx.fill();
      ctx.strokeStyle = '#070b14';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(f.map_coords.x, f.map_coords.y, 10, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.45)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(f.map_coords.x, f.map_coords.y, 15, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#38bdf8' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.35) && isMatch) {
        drawMapLabel(ctx, '🎣 ' + f.title, f.map_coords.x, f.map_coords.y + 15, '#a5f3fc', 'rgba(8, 51, 68, 0.9)');
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
      ctx.fillStyle = isMatch ? '#f59e0b' : '#475569';
      ctx.fill();
      ctx.strokeStyle = '#070b14';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(n.map_coords.x, n.map_coords.y, 11, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.55)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(n.map_coords.x, n.map_coords.y, 16, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#38bdf8' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.25) && isMatch) {
        drawMapLabel(ctx, '👤 ' + n.title, n.map_coords.x, n.map_coords.y + 16, '#fef08a', 'rgba(69, 26, 3, 0.9)');
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
      ctx.fillStyle = isMatch ? '#ec4899' : '#475569';
      ctx.fill();
      ctx.strokeStyle = '#070b14';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(s.map_coords.x, s.map_coords.y, 16, 0, Math.PI * 2);
        ctx.strokeStyle = isSelected ? '#38bdf8' : '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if ((isSelected || isHovered || mapTransform.scale >= 1.25) && isMatch) {
        drawMapLabel(ctx, '✨ ' + s.title, s.map_coords.x, s.map_coords.y + 16, '#fbcfe8', 'rgba(80, 7, 36, 0.9)');
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
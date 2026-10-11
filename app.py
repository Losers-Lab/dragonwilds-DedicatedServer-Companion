from flask import Flask, jsonify, request, send_from_directory, abort, render_template
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
    return render_template("index.html")


if __name__ == "__main__":
    init_db()
    start_monitor()
    start_dockerstats()
    start_savewatcher()

    app.run(
        host="0.0.0.0",
        port=config.PORT
    )

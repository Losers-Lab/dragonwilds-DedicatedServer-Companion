import os
import re
import time
from datetime import datetime, timezone
import config
from utils import seconds_to_human

_cache = {
    "path": None,
    "mtime": 0,
    "data": {
        "day_count": 0,
        "weather": [],
        "steam_map": {},
        "active_save": None
    }
}

WEATHER_NAME_MAP = {
    "base": "Central",
    "dowdun": "Dowdun Reach",
    "sands": "Umbral Sands",
    "Scorned Wilderness": "Scorned Wilderness"
}

WEATHER_ICON_MAP = {
    "Sunny": "☀️",
    "Cloudy": "⛅",
    "Rain Storm": "⛈️",
    "Rain": "🌧️",
    "Fog": "🌫️",
    "Snow": "❄️"
}


def find_newest_save():
    if not config.SAVE_PATH or not os.path.exists(config.SAVE_PATH):
        return None

    newest_path = None
    newest_mtime = -1

    try:
        for root, _, files in os.walk(config.SAVE_PATH):
            for file in files:
                if file.endswith(".sav"):
                    path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(path)
                        if mtime > newest_mtime:
                            newest_mtime = mtime
                            newest_path = path
                    except Exception:
                        continue
    except Exception:
        pass

    return newest_path


def format_remaining_time(seconds):
    if seconds <= 0:
        return "Ending soon"
    sec = int(seconds)
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m left"
    if minutes > 0:
        return f"{minutes}m left"
    return f"{sec}s left"


def get_world_data():
    global _cache
    save_path = find_newest_save()
    if not save_path or not os.path.exists(save_path):
        return _cache["data"]

    try:
        mtime = os.path.getmtime(save_path)
    except Exception:
        return _cache["data"]

    # Return cached data if save has not been updated
    if _cache["path"] == save_path and _cache["mtime"] == mtime:
        return _cache["data"]

    day_count = 0
    weather_list = []
    steam_map = {}

    try:
        with open(save_path, "rb") as f:
            content = f.read()

        # 1. Weather and Day Count Extraction
        m = content.find(b'"WeatherName"')
        if m != -1:
            start = content.rfind(b'{', 0, m)
            end = content.find(b']\r\n}', start)
            if end == -1:
                end = content.find(b']\n}', start)
            if end != -1:
                chunk = content[start:end + 4].decode("utf-8", errors="ignore")
                pattern = r'"WeatherName":\s*"([^"]+)"[^}]*"TYPE":\s*"([^"]+)"[^}]*"DAY_COUNT":\s*(\d+)[^}]*"REMAINING_TIME":\s*([\d\.]+)'
                for wm in re.finditer(pattern, chunk):
                    raw_name = wm.group(1)
                    raw_type = wm.group(2).replace("EWeatherType::", "").replace("_", " ")
                    dc = int(wm.group(3))
                    rem_sec = float(wm.group(4))

                    if not day_count:
                        day_count = dc

                    region_label = WEATHER_NAME_MAP.get(raw_name, raw_name)
                    icon = WEATHER_ICON_MAP.get(raw_type, "🌤️")

                    weather_list.append({
                        "raw_region": raw_name,
                        "region": region_label,
                        "type": raw_type,
                        "icon": icon,
                        "remaining_seconds": rem_sec,
                        "remaining_text": format_remaining_time(rem_sec)
                    })

        # 2. Steam ID and EOS GUID Mapping
        pattern_steam = rb"RedpointEOS:([a-f0-9]{32}),STEAM:(\d{17})"
        for sm in re.finditer(pattern_steam, content):
            eos_id = sm.group(1).decode()
            steam_id = sm.group(2).decode()
            steam_map[eos_id] = steam_id

    except Exception as e:
        print(f"Error parsing save {save_path}: {e}")

    parsed = {
        "day_count": day_count,
        "weather": weather_list,
        "steam_map": steam_map,
        "active_save": os.path.basename(save_path)
    }

    _cache["path"] = save_path
    _cache["mtime"] = mtime
    _cache["data"] = parsed

    return parsed


def get_save_files_list():
    if not config.SAVE_PATH or not os.path.exists(config.SAVE_PATH):
        return []

    files_list = []
    try:
        for file in os.listdir(config.SAVE_PATH):
            if file.endswith(".sav") or file.endswith(".sav.backup"):
                full_path = os.path.join(config.SAVE_PATH, file)
                try:
                    stat = os.stat(full_path)
                    size_kb = stat.st_size / 1024
                    size_mb = size_kb / 1024
                    size_str = f"{size_mb:.2f} MB" if size_mb >= 1.0 else f"{size_kb:.0f} KB"
                    mtime_dt = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                    files_list.append({
                        "filename": file,
                        "size_bytes": stat.st_size,
                        "size_str": size_str,
                        "modified_iso": mtime_dt.isoformat(),
                        "modified_text": mtime_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "is_backup": file.endswith(".backup")
                    })
                except Exception:
                    continue
    except Exception:
        pass

    files_list.sort(key=lambda x: x["filename"])
    return files_list

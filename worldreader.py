import os
import re
import time
from datetime import datetime, timezone
import config

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

# Cumulative mapping across all discovered save files
_known_steam_map = {}

# Throttled save-path scan cache
_save_scan_cache = {
    "timestamp": 0,
    "path": None
}

WEATHER_NAME_MAP = {
    "base": "Central Ashenfall (Overworld)",
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

# 30+ canonical world map regions discovered from game binary (ST_UI_MapRegions)
CANONICAL_MAP_REGIONS = [
    {"id": "MapRegionAlcarridOasis", "name": "Al Kharid Oasis", "biome": "Desert"},
    {"id": "MapRegionApproach", "name": "The Approach", "biome": "Plains"},
    {"id": "MapRegionBastion", "name": "The Bastion", "biome": "Fortress"},
    {"id": "MapRegionBleakfields", "name": "Bleakfields", "biome": "Wasteland"},
    {"id": "MapRegionBloodblight", "name": "Bloodblight Swamp", "biome": "Swamp"},
    {"id": "MapRegionBramblemead", "name": "Bramblemead", "biome": "Meadow"},
    {"id": "MapRegionCathedral", "name": "Cathedral Ruins", "biome": "Sanctuary"},
    {"id": "MapRegionCoalridge", "name": "Coalridge", "biome": "Highlands"},
    {"id": "MapRegionCourtyard", "name": "Ancient Courtyard", "biome": "Ruins"},
    {"id": "MapRegionCrypt", "name": "Ashen Crypts", "biome": "Subterranean"},
    {"id": "MapRegionDemonGate", "name": "Demon Gate", "biome": "Volcanic"},
    {"id": "MapRegionDragonsRun", "name": "Dragon's Run", "biome": "Mountains"},
    {"id": "MapRegionDunesOfUzzer", "name": "Dunes of Uzer", "biome": "Desert"},
    {"id": "MapRegionEmberwood", "name": "Emberwood", "biome": "Forest"},
    {"id": "MapRegionFracturedPlains", "name": "Fractured Plains", "biome": "Plains"},
    {"id": "MapRegionGarrison", "name": "Imperial Garrison", "biome": "Fortress"},
    {"id": "MapRegionGrandHall", "name": "Grand Hall", "biome": "Ruins"},
    {"id": "MapRegionHopesFall", "name": "Hope's Fall", "biome": "Highlands"},
    {"id": "MapRegionLake", "name": "Mirror Lake", "biome": "Lake"},
    {"id": "MapRegionLakeOfLostSouls", "name": "Lake of Lost Souls", "biome": "Mystic"},
    {"id": "MapRegionLibrary", "name": "Forgotten Library", "biome": "Sanctuary"},
    {"id": "MapRegionManafemPlains", "name": "Manafem Plains", "biome": "Plains"},
    {"id": "MapRegionMenagerie", "name": "Royal Menagerie", "biome": "Ruins"},
    {"id": "MapRegionNexus", "name": "The Nexus", "biome": "Arcane"},
    {"id": "MapRegionPastures", "name": "Ashenfall Pastures", "biome": "Plains"},
    {"id": "MapRegionSilverthorn", "name": "Silverthorn Woods", "biome": "Forest"},
    {"id": "MapRegionHighlands", "name": "Dowdun Highlands", "biome": "Highlands"},
    {"id": "MapRegionTempleWoods", "name": "Temple Woods", "biome": "Forest"},
    {"id": "MapRegionTheBurningSpire", "name": "The Burning Spire", "biome": "Volcanic"},
    {"id": "MapRegionWhisperingSwamp", "name": "Whispering Swamp", "biome": "Swamp"},
    {"id": "MapRegionWItchWillow", "name": "Witch Willow Mire", "biome": "Swamp"}
]


CANONICAL_REGION_LOOKUP = {r["id"]: r["name"] for r in CANONICAL_MAP_REGIONS}


def format_region_name(raw_name: str) -> str:
    """Format raw weather/world region identifiers into human-readable labels."""
    if not raw_name or not isinstance(raw_name, str):
        return "Unknown Region"
    
    raw_name_clean = raw_name.strip()
    if not raw_name_clean:
        return "Unknown Region"

    if raw_name_clean in WEATHER_NAME_MAP:
        return WEATHER_NAME_MAP[raw_name_clean]
    
    if raw_name_clean in CANONICAL_REGION_LOOKUP:
        return CANONICAL_REGION_LOOKUP[raw_name_clean]
    
    # Check if prefixed with MapRegion
    if raw_name_clean.startswith("MapRegion"):
        stripped = raw_name_clean[9:]
        if raw_name_clean in CANONICAL_REGION_LOOKUP:
            return CANONICAL_REGION_LOOKUP[raw_name_clean]
        name = stripped
    else:
        # Check if adding MapRegion matches canonical database
        prefixed = f"MapRegion{raw_name_clean}"
        if prefixed in CANONICAL_REGION_LOOKUP:
            return CANONICAL_REGION_LOOKUP[prefixed]
        name = raw_name_clean
    
    # Space out CamelCase (e.g. WhisperingSwamp -> Whispering Swamp)
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name)
    formatted = name.replace('_', ' ').strip().title()
    return formatted if formatted else "Unknown Region"


def get_canonical_regions():
    """Return all canonical map regions in the game with fresh dictionary copies."""
    return [dict(region) for region in CANONICAL_MAP_REGIONS]


def find_newest_save():
    global _save_scan_cache
    now = time.time()
    if now - _save_scan_cache["timestamp"] < 5.0 and _save_scan_cache["path"]:
        return _save_scan_cache["path"]

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

    _save_scan_cache["timestamp"] = now
    _save_scan_cache["path"] = newest_path
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


def _extract_steam_ids_from_content(content):
    """Extract RedpointEOS -> Steam ID mappings with case-insensitive hex support."""
    pattern_steam = rb"(?i)RedpointEOS:([a-f0-9]{32}),STEAM:(\d{17})"
    found = {}
    for sm in re.finditer(pattern_steam, content):
        eos_id = sm.group(1).decode().lower()
        steam_id = sm.group(2).decode()
        found[eos_id] = steam_id
    return found


def scan_all_saves_for_steam_ids():
    """Scans all .sav files to discover and preserve Steam IDs across world saves."""
    global _known_steam_map
    if not config.SAVE_PATH or not os.path.exists(config.SAVE_PATH):
        return

    try:
        for file in os.listdir(config.SAVE_PATH):
            if file.endswith(".sav"):
                full_path = os.path.join(config.SAVE_PATH, file)
                try:
                    with open(full_path, "rb") as f:
                        data = f.read()
                    _known_steam_map.update(_extract_steam_ids_from_content(data))
                except Exception:
                    pass
    except Exception:
        pass


DAY_CYCLE_LENGTH_SECONDS = 840.0  # ~14 minutes default day/night cycle in Dragonwilds


def calculate_day_cycle(day_count: int, save_mtime: float = 0.0) -> dict:
    """Calculates smooth in-game day/night cycle progression, angle, and phase."""
    if not day_count:
        return {
            "day_count": 0,
            "progress_percent": 0.0,
            "phase": "Unknown",
            "phase_icon": "☀️",
            "needle_angle_deg": 0.0,
            "seconds_in_day": 0.0,
            "cycle_duration_seconds": int(DAY_CYCLE_LENGTH_SECONDS),
            "is_night": False
        }

    now = time.time()
    elapsed = max(0.0, now - save_mtime) if save_mtime > 0 else 0.0
    cycle_pos = (elapsed % DAY_CYCLE_LENGTH_SECONDS) / DAY_CYCLE_LENGTH_SECONDS
    angle_deg = (cycle_pos * 360.0) % 360.0

    if 0 <= angle_deg < 45:
        phase = "Morning"
        icon = "🌅"
        is_night = False
    elif 45 <= angle_deg < 135:
        phase = "Midday"
        icon = "☀️"
        is_night = False
    elif 135 <= angle_deg < 180:
        phase = "Afternoon"
        icon = "🌤️"
        is_night = False
    elif 180 <= angle_deg < 270:
        phase = "Dusk / Twilight"
        icon = "🌇"
        is_night = True
    else:
        phase = "Night"
        icon = "🌙"
        is_night = True

    return {
        "day_count": day_count,
        "progress_percent": round(cycle_pos * 100.0, 1),
        "phase": phase,
        "phase_icon": icon,
        "needle_angle_deg": round(angle_deg, 1),
        "seconds_in_day": round(elapsed % DAY_CYCLE_LENGTH_SECONDS, 1),
        "cycle_duration_seconds": int(DAY_CYCLE_LENGTH_SECONDS),
        "is_night": is_night
    }


def get_world_data():
    global _cache, _known_steam_map
    save_path = find_newest_save()
    if not save_path or not os.path.exists(save_path):
        return _cache["data"]

    try:
        mtime = os.path.getmtime(save_path)
    except Exception:
        return _cache["data"]

    # Return cached data if save has not been updated, but recalculate dynamic day cycle
    if _cache["path"] == save_path and _cache["mtime"] == mtime:
        cached_data = dict(_cache["data"])
        if cached_data.get("day_count"):
            cached_data["day_cycle"] = calculate_day_cycle(cached_data["day_count"], mtime)
        return cached_data

    day_count = 0
    weather_list = []

    try:
        with open(save_path, "rb") as f:
            content = f.read()

        # 1. Weather and Day Count Extraction
        m = content.find(b'"WeatherName"')
        if m != -1:
            start = content.rfind(b'{', 0, m)
            end_bracket = content.find(b']', m)
            if end_bracket != -1:
                end_brace = content.find(b'}', end_bracket)
                if end_brace != -1:
                    chunk = content[start:end_brace + 1].decode("utf-8", errors="ignore")
                    pattern = (
                        r'"WeatherName":\s*"([^"]+)"[^}]*'
                        r'"TYPE":\s*"([^"]+)"[^}]*'
                        r'"DAY_COUNT":\s*(\d+)[^}]*'
                        r'"REMAINING_TIME":\s*([\-0-9\.eE\+]+)'
                    )
                    for wm in re.finditer(pattern, chunk):
                        raw_name = wm.group(1)
                        raw_type = wm.group(2).replace("EWeatherType::", "").replace("_", " ")
                        dc = int(wm.group(3))
                        try:
                            rem_sec = float(wm.group(4))
                        except Exception:
                            rem_sec = 0.0

                        if not day_count:
                            day_count = dc

                        region_label = format_region_name(raw_name)
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
        new_steam_entries = _extract_steam_ids_from_content(content)
        _known_steam_map.update(new_steam_entries)

        # If this save has few/no Steam mappings, scan older saves once to populate
        if len(_known_steam_map) <= len(new_steam_entries):
            scan_all_saves_for_steam_ids()

    except Exception as e:
        print(f"Error parsing save {save_path}: {e}")
        # Crucial fix: DO NOT overwrite _cache["mtime"] on transient read failure
        return _cache["data"]

    parsed = {
        "day_count": day_count,
        "day_cycle": calculate_day_cycle(day_count, mtime),
        "weather": weather_list,
        "steam_map": dict(_known_steam_map),
        "active_save": os.path.basename(save_path),
        "save_mtime": mtime
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
                        "mtime": stat.st_mtime,
                        "is_backup": file.endswith(".backup")
                    })
                except Exception:
                    continue
    except Exception:
        pass

    # Sort newest modified first
    files_list.sort(key=lambda x: -x["mtime"])
    return files_list

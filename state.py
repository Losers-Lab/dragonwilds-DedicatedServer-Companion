import time
from threading import Lock
from datetime import datetime, timezone
import config

_lock = Lock()

state = {
    "status": "online",
    "server": config.SERVER_NAME,
    "world": "Unknown",
    "version": "Unknown",
    "players": {},
    "cpu": "Unknown",
    "memory": "Unknown",
    "uptime": "Unknown",
    "last_save": "Unknown",
    "day_count": 0,
    "weather": [],
    "events": [],
    "updated": int(time.time())
}


def add_event(message, category=None):
    if not category:
        msg_lower = message.lower()
        if "joined" in msg_lower or "left" in msg_lower:
            category = "user"
        elif any(k in msg_lower for k in ["dragon", "boss", "wave", "monster", "combat"]):
            category = "dragon"
        else:
            category = "server"

    now_epoch = time.time()
    with _lock:
        state["events"].insert(0, {
            "epoch": now_epoch,
            "iso": datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat(),
            "timestamp": datetime.fromtimestamp(now_epoch, tz=timezone.utc).strftime("%H:%M:%S UTC"),
            "full_time": datetime.fromtimestamp(now_epoch, tz=timezone.utc).strftime("%m/%d/%Y %I:%M:%S %p UTC"),
            "category": category,
            "message": message
        })
        state["events"] = state["events"][:100]
        state["updated"] = int(time.time())


_character_names = {}


def set_character_name(account, char_name):
    if not account or not char_name:
        return
    key = account.strip().lower()
    with _lock:
        _character_names[key] = char_name.strip()
        state["updated"] = int(time.time())


def get_character_name(account):
    if not account:
        return None
    with _lock:
        return _character_names.get(account.strip().lower())


def get_all_character_names():
    with _lock:
        return dict(_character_names)


def set_player(account, name, notify=True):
    key = account.strip().lower() if account else ""
    with _lock:
        char_name = _character_names.get(key)
        state["players"][account] = {
            "account": account,
            "name": name,
            "character_name": char_name
        }
        state["updated"] = int(time.time())
    if notify:
        char_label = f" ({char_name})" if char_name and char_name != name else ""
        add_event(f"{name}{char_label} joined")


def remove_player(account, name=None, notify=True):
    key = account.strip().lower() if account else ""
    with _lock:
        old_val = state["players"].pop(account, None)
        old_name = old_val.get("name") if isinstance(old_val, dict) else old_val
        char_name = _character_names.get(key)
        state["updated"] = int(time.time())
    if notify:
        pname = name or old_name or account
        char_label = f" ({char_name})" if char_name and char_name != pname else ""
        add_event(f"{pname}{char_label} left")


def clear_players():
    with _lock:
        state["players"] = {}
        state["updated"] = int(time.time())


def update_field(key, value):
    with _lock:
        state[key] = value
        state["updated"] = int(time.time())


def get_state():
    from worldreader import get_world_data
    from roster import get_roster

    with _lock:
        raw_players = list(state["players"].values())
        players = []
        players_detail = []
        for p in raw_players:
            if isinstance(p, dict):
                p_name = p.get("name")
                c_name = p.get("character_name") or _character_names.get(str(p.get("account", "")).lower())
                players.append(p_name)
                players_detail.append({
                    "name": p_name,
                    "account": p.get("account"),
                    "character_name": c_name
                })
            else:
                players.append(p)
                players_detail.append({
                    "name": p,
                    "account": None,
                    "character_name": None
                })
        day_count = state.get("day_count", 0)
        weather = state.get("weather", [])
        status_val = state["status"]
        server_val = state["server"]
        world_val = state["world"]
        version_val = state["version"]
        cpu_val = state["cpu"]
        memory_val = state["memory"]
        uptime_val = state["uptime"]
        last_save_val = state["last_save"]
        events_val = list(state["events"])
        updated_val = state["updated"]
        char_names_copy = dict(_character_names)

    # Outside the lock to prevent disk I/O from blocking companion threads
    day_cycle = None
    try:
        wdata = get_world_data()
        day_cycle = wdata.get("day_cycle")
        if wdata.get("day_count") and not day_count:
            day_count = wdata["day_count"]
        if wdata.get("weather") and not weather:
            weather = wdata["weather"]
        with _lock:
            state["day_count"] = day_count
            state["weather"] = weather
            if wdata.get("active_save") and state["world"] in ["Unknown", ""]:
                state["world"] = wdata["active_save"].replace(".sav", "")
                world_val = state["world"]
    except Exception:
        pass

    try:
        full_roster = get_roster(players)
    except Exception:
        full_roster = []

    return {
        "status": status_val,
        "server": server_val,
        "world": world_val,
        "version": version_val,
        "players_online": len(players),
        "max_players": config.MAX_PLAYERS,
        "players": players,
        "players_detail": players_detail,
        "players_text": ", ".join(players) if players else "None",
        "cpu": cpu_val,
        "memory": memory_val,
        "uptime": uptime_val,
        "last_save": last_save_val,
        "day_count": day_count,
        "day_cycle": day_cycle,
        "weather": weather,
        "roster": full_roster,
        "character_names": char_names_copy,
        "events": events_val,
        "updated": updated_val
    }
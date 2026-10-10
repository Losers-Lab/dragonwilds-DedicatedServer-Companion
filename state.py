import time
from threading import Lock
from datetime import datetime
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

    with _lock:
        state["events"].insert(0, {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "full_time": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"),
            "category": category,
            "message": message
        })
        state["events"] = state["events"][:100]
        state["updated"] = int(time.time())


def set_player(account, name, notify=True):
    with _lock:
        state["players"][account] = name
        state["updated"] = int(time.time())
    if notify:
        add_event(f"{name} joined")


def remove_player(account, name=None, notify=True):
    with _lock:
        old_name = state["players"].pop(account, None)
        state["updated"] = int(time.time())
    if notify:
        add_event(f"{name or old_name or account} left")


def clear_players():
    with _lock:
        state["players"] = {}
        state["updated"] = int(time.time())


def update_field(key, value):
    with _lock:
        state[key] = value
        state["updated"] = int(time.time())


def get_state():
    with _lock:
        players = list(state["players"].values())

        return {
            "status": state["status"],
            "server": state["server"],
            "world": state["world"],
            "version": state["version"],
            "players_online": len(players),
            "max_players": config.MAX_PLAYERS,
            "players": players,
            "players_text": ", ".join(players) if players else "None",
            "cpu": state["cpu"],
            "memory": state["memory"],
            "uptime": state["uptime"],
            "last_save": state["last_save"],
            "events": state["events"],
            "updated": state["updated"]
        }
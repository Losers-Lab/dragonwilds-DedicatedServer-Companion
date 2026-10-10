import os
import re
import config
from worldreader import get_world_data

_roster_cache = {
    "mtime": 0,
    "players": []
}


def get_roster(active_online_names=None):
    global _roster_cache
    cfg_path = config.SERVER_CONFIG_PATH
    if not cfg_path or not os.path.exists(cfg_path):
        return []

    try:
        mtime = os.path.getmtime(cfg_path)
    except Exception:
        mtime = 0

    if _roster_cache["mtime"] == mtime and _roster_cache["players"]:
        raw_players = _roster_cache["players"]
    else:
        raw_players = []
        try:
            with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            owner_match = re.search(r"OwnerId\s*=\s*([a-f0-9]+)", content, re.IGNORECASE)
            owner_id = owner_match.group(1).lower() if owner_match else ""

            pattern = (
                r'KnownPlayerList\s*=\s*\(\s*UserId\s*=\s*([a-f0-9]+)\s*,\s*'
                r'UserName\s*=\s*"([^"]*)"\s*'
                r'(?:,\s*Privileges\s*=\s*\(\s*PrivilegeMask\s*=\s*(\d+)\s*\)\s*)?'
                r',\s*bIsBanned\s*=\s*(True|False)\s*\)'
            )
            for m in re.finditer(pattern, content, re.IGNORECASE):
                uid, uname, priv, banned = m.groups()
                uid_clean = uid.strip().lower()
                is_owner = (uid_clean == owner_id)
                priv_val = int(priv) if priv else 0
                is_admin = is_owner or (priv_val > 0)
                is_banned = (banned.lower() == "true")

                raw_players.append({
                    "user_id": uid_clean,
                    "name": uname,
                    "is_owner": is_owner,
                    "is_admin": is_admin,
                    "is_banned": is_banned
                })

            _roster_cache["mtime"] = mtime
            _roster_cache["players"] = raw_players
        except Exception as e:
            print(f"Error parsing DedicatedServer.ini: {e}")

    # Fetch steam mapping from world data
    world_info = get_world_data()
    steam_map = world_info.get("steam_map", {})

    # Attach dynamic live online status, steam IDs & character names
    from state import get_character_name
    online_set = set(active_online_names or [])
    enriched_roster = []

    for p in raw_players:
        uid = p["user_id"]
        steam_id = steam_map.get(uid)
        char_name = get_character_name(uid)
        is_online = (p["name"] in online_set)

        enriched_roster.append({
            "user_id": uid,
            "name": p["name"],
            "character_name": char_name,
            "steam_id": steam_id,
            "is_owner": p["is_owner"],
            "is_admin": p["is_admin"],
            "is_banned": p["is_banned"],
            "online": is_online
        })

    # Sort online players first, then owners, admins, then alphabetical
    enriched_roster.sort(key=lambda x: (
        not x["online"],
        not x["is_owner"],
        not x["is_admin"],
        x["name"].lower()
    ))

    return enriched_roster

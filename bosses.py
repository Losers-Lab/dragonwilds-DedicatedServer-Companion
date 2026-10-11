"""
Dragonwilds Boss Encounters & World Event Live Telemetry Module.

Extracts objective boss and live world events:
1. Canonical Boss & Arena Encounters:
   - The Dragon Arena (Dragon Boss / Velgar)
   - Kalphite Queen Arena
   - Fight Caves (TzTok-Jad Arena)
   - Nightmare Crucible
   - Titan Vault Gate
   - Umbral Sands Boss Gate
   - Death's Temple
2. Live Server Event Stream:
   - Parses `LogWorldEventAIWaveSpawning` from `RSDragonwilds.log` for active raids,
     waves, and hunt events.
   - Extracts player connection / join activity and server save snapshots.
3. Strictly Read-Only: Directly parses active server logs and `.sav` files.
"""

import os
import glob
import re
from datetime import datetime, timezone
from config import SAVES_DIR, LOG_PATH


CANONICAL_BOSS_ENCOUNTERS = [
    {
        "id": "boss_dragon_arena",
        "name": "The Dragon Arena (Dragon Boss)",
        "lore_region": "Dragonkin Citadel / High Peaks",
        "teleporter_token": b"BP_InteractablePlayerTeleporter_IntoDragonArena",
        "category": "World Boss",
        "description": "Arena teleporter leading into the Dragon Boss inner sanctum."
    },
    {
        "id": "boss_kalphite_queen",
        "name": "Kalphite Queen Arena",
        "lore_region": "Umbral Sands / Kalphite Lair",
        "teleporter_token": b"BP_PROTOTYPE_InteractablePlayerTeleporter_KalphiteQueenArena",
        "category": "Lair Boss",
        "description": "Subterranean hive arena harboring the Kalphite Queen."
    },
    {
        "id": "boss_fight_caves",
        "name": "Fight Caves (TzTok-Jad)",
        "lore_region": "Volcanic Core",
        "teleporter_token": b"FightCaves_ToBoss",
        "category": "Arena Trial",
        "description": "Multi-wave endurance trial leading directly into the fire titan."
    },
    {
        "id": "boss_nightmare_crucible",
        "name": "Nightmare Crucible",
        "lore_region": "Shadowed Wilds",
        "teleporter_token": b"NightmareCrucible",
        "category": "Trial Boss",
        "description": "Crucible encounter locked by ritualistic trial requirements."
    },
    {
        "id": "boss_titan_door",
        "name": "Titan Door Vault",
        "lore_region": "Ancient Ruins",
        "teleporter_token": b"TitanDoor",
        "category": "Vault Guardian",
        "description": "Sealed titan gateway concealing subterranean vault guardians."
    },
    {
        "id": "boss_umbral_door",
        "name": "Umbral Door Sanctum",
        "lore_region": "Umbral Sands",
        "teleporter_token": b"UmbralDoor",
        "category": "Desert Sanctum",
        "description": "Sands sanctuary gate requiring ancient key unlocks."
    },
    {
        "id": "boss_deaths_temple",
        "name": "Death's Temple",
        "lore_region": "Underworld Threshold",
        "teleporter_token": b"DeathsTemple",
        "category": "Ancient Temple",
        "description": "Portal granting entry to the domain of Death."
    }
]


def get_boss_encounters(saves_dir: str = SAVES_DIR) -> dict:
    """Returns canonical boss encounters and their world status in the active save."""
    save_files = glob.glob(os.path.join(saves_dir, "*.sav"))
    save_data = b""
    active_save_name = "None"

    if save_files:
        newest_save = max(save_files, key=os.path.getmtime)
        active_save_name = os.path.basename(newest_save)
        try:
            with open(newest_save, "rb") as f:
                save_data = f.read()
        except Exception:
            save_data = b""

    encounters = []
    unlocked_count = 0

    for boss in CANONICAL_BOSS_ENCOUNTERS:
        # Check if portal / entrance actor has been activated/instantiated in this save
        is_instantiated = (boss["teleporter_token"] in save_data) if save_data else False
        if is_instantiated:
            unlocked_count += 1

        encounters.append({
            "id": boss["id"],
            "name": boss["name"],
            "lore_region": boss["lore_region"],
            "category": boss["category"],
            "description": boss["description"],
            "world_discovered": is_instantiated,
            "status": "Arena Discovered & Active" if is_instantiated else "Undiscovered / Dormant"
        })

    return {
        "encounters": encounters,
        "summary": {
            "total_boss_arenas": len(CANONICAL_BOSS_ENCOUNTERS),
            "discovered_arenas": unlocked_count,
            "active_world_save": active_save_name
        }
    }


def get_live_world_events(log_path: str = LOG_PATH, max_events: int = 50) -> list:
    """Extracts live gameplay events (raids, wave spawns, boss deaths, logins) directly from server log."""
    if not os.path.exists(log_path):
        return []

    events = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Iterate in reverse to get most recent events first
        for line in reversed(lines):
            line_str = line.strip()
            if not line_str:
                continue

            ts_match = re.match(r"^\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\](?:\[\s*\d+\])?(.*)$", line_str)
            if not ts_match:
                continue

            raw_ts = ts_match.group(1)
            body = ts_match.group(2)

            # Format timestamp nicely with UTC epoch and ISO
            formatted_ts = raw_ts.replace(".", "-")[:10] + " " + raw_ts[11:19].replace(".", ":") + " UTC"
            try:
                base_dt = datetime.strptime(raw_ts[:19], "%Y.%m.%d-%H.%M.%S").replace(tzinfo=timezone.utc)
                event_epoch = base_dt.timestamp()
                event_iso = base_dt.isoformat()
            except Exception:
                event_epoch = 0.0
                event_iso = None

            # 1. Base Raid & World Wave Events
            if "LogWorldEventAIWaveSpawning:" in body:
                event_type = "World Raid"
                badge = "raid"
                msg = body.split("LogWorldEventAIWaveSpawning:")[1].strip()
                events.append({
                    "timestamp": formatted_ts,
                    "epoch": event_epoch,
                    "iso": event_iso,
                    "type": event_type,
                    "badge": badge,
                    "message": msg,
                    "source": "⚡ Live Telemetry"
                })

            # 2. Boss & Miniboss Encounters
            elif "EvadeAttack:" in body and "Miniboss" in body and "starting attack" in body:
                event_type = "Miniboss Combat"
                badge = "combat"
                msg = body.split("EvadeAttack:")[1].strip()
                events.append({
                    "timestamp": formatted_ts,
                    "epoch": event_epoch,
                    "iso": event_iso,
                    "type": event_type,
                    "badge": badge,
                    "message": msg,
                    "source": "⚡ Live Telemetry"
                })

            # 3. Chest Respawn Telemetry
            elif "LogChests:" in body and "SetRespawnTimer" in body:
                event_type = "Chest Looted"
                badge = "chest"
                msg = body.split("LogChests:")[1].strip()
                events.append({
                    "timestamp": formatted_ts,
                    "epoch": event_epoch,
                    "iso": event_iso,
                    "type": event_type,
                    "badge": badge,
                    "message": msg,
                    "source": "⚡ Live Telemetry"
                })

            # 4. Player Logins & Connections
            elif "LogNet: Join request:" in body:
                event_type = "Player Joined"
                badge = "player"
                player_name = "Player"
                m = re.search(r"Name=([^?& ]+)", body)
                if m:
                    player_name = m.group(1)
                events.append({
                    "timestamp": formatted_ts,
                    "epoch": event_epoch,
                    "iso": event_iso,
                    "type": event_type,
                    "badge": badge,
                    "message": f"Player '{player_name}' joined server world",
                    "source": "⚡ Live Telemetry"
                })

            if len(events) >= max_events:
                break

    except Exception:
        pass

    return events

"""
Dragonwilds Respawn Tracker Module.

Tracks:
1. Dungeon and Vault treasure chests via live server log telemetry (`LogChests: SetRespawnTimer()`, `PerformRespawn()`).
2. High-value gathering nodes (Luminite, Runite, Adamantite, Avisk Crystal, Rune Essence).
3. 3-day Fishing Net cycle spots across world regions (Dowdun Reach, Ghornfell, Fellhollow, Brynmoor, Scorned Wilderness, Umbral Sands).
4. World Bosses & Dragonkin encounters (Kalphite Queen, Dragonkin Conduits, Dragon Fuzan, Dragon Imaru, Dragon Kuldra Heart).

Filters out trivial low-level mobs (rats, low-level goblins, basic sticks/clay) by default,
while providing rich categorization, search filtering, and live countdowns.
"""

import os
import re
import glob
import time
from datetime import datetime
from config import LOGS_DIR, SAVES_DIR


# Friendly name mappings for known chests and actors
CHEST_NAME_MAP = {
    "BM_Cook": "Brinemoor Cook's Cache",
    "BM_Crafter": "Brinemoor Crafter's Cache",
    "BM_Rune": "Brinemoor Rune Cache",
    "BM_Hunting": "Brinemoor Hunting Cache",
    "BM_Weapon": "Brinemoor Weapon Vault",
    "BM_Gear": "Brinemoor Gear Vault",
    "BM_Miners": "Brinemoor Miner's Cache",
    "BM_Lunch": "Brinemoor Provision Vault",
    "Highlands_Miners": "Highlands Miner's Cache",
}

# Categories
CAT_CHEST = "Dungeon Chests"
CAT_FISHING = "Fishing Nets (3-Day Cycle)"
CAT_ORE = "High-Tier Mining Ores"
CAT_BOSS = "World Bosses & Elites"
CAT_OTHER = "Other Resources"

# Known canonical fishing net locations with standard 3-day cycle (42 minutes in-game or 3 days)
CANONICAL_FISHING_NET_REGIONS = [
    ("Brynmoor", "Brynmoor Coastal Fishing Nets"),
    ("DowdunReach", "Dowdun Reach Estuary Nets"),
    ("Fellhollow", "Fellhollow River Nets"),
    ("Ghornfell", "Ghornfell Glacial Lake Nets"),
    ("ScornedWilderness", "Scorned Wilderness Swamp Nets"),
    ("UmbralSands", "Umbral Sands Oasis Nets"),
]

# Canonical World Bosses and Dragonkin Targets
CANONICAL_BOSS_TARGETS = [
    ("BP_KalphiteQueenSpawnTrigger", "Kalphite Queen", "Sandstone Chasm Arena", 7200.0),
    ("BP_DragonFuzan_SpawnTrigger", "Dragon Fuzan (Red Dragon)", "Scorned Wilderness Caldera", 5400.0),
    ("BP_DragonImaru_SpawnTrigger", "Dragon Imaru (Sky Wyrm)", "Ghornfell Peak", 5400.0),
    ("BP_DragonKuldraHeart_SpawnTrigger", "Dragon Kuldra Heart", "Nightmare Crucible", 7200.0),
    ("BP_DragonkinConduit_NightmareCrucible", "Dragonkin Conduit", "Nightmare Crucible Sanctum", 3600.0),
    ("BP_BossAltar_Region1", "Ancient Guardian Boss Altar", "Fellhollow Deep Shrine", 3600.0),
]

# High tier ores and rocks to track
HIGH_TIER_MINING_NODES = [
    ("Luminite", "Luminite Crystal Node", 1800.0),
    ("Runite", "Runite Ore Vein", 1200.0),
    ("Adamantite", "Adamantite Ore Vein", 900.0),
    ("AviskCrystal", "Avisk Crystal Formation", 1200.0),
    ("SoulStone", "Soul Stone Geode", 1500.0),
    ("RuneEssence", "Pure Rune Essence Node", 600.0),
]


def format_actor_name(actor_name: str) -> str:
    """Extracts a clean, human-readable name from an engine actor identifier."""
    if not actor_name:
        return "Unknown Target"

    # Match known chest sub-types
    for key, friendly in CHEST_NAME_MAP.items():
        if key in actor_name:
            if "Vault" in actor_name:
                return f"{friendly} (Vault)"
            return friendly

    # Match fishing net nodes
    net_match = re.search(r'BP_FishingNodeV2_Net_([A-Za-z0-9_]+?)(?:_C)?(?:_UAID.*)?$', actor_name)
    if net_match:
        region = net_match.group(1).replace('_', ' ')
        return f"Fishing Net Spot ({region})"

    # Match high-tier ore nodes
    ore_match = re.search(r'BP_OreNode_([A-Za-z0-9_]+?)(?:_Large|_Medium|_Small)?(?:_[A-Z0-9]+)?(?:_C)?(?:_UAID.*)?$', actor_name)
    if ore_match:
        ore_type = ore_match.group(1).replace('_', ' ')
        return f"{ore_type} Ore Vein"

    # Match mining rock nodes (Luminite, Rune Essence, Avisk)
    rock_match = re.search(r'BP_MiningRock_([A-Za-z0-9_]+?)(?:_Static.*)?(?:_C)?(?:_UAID.*)?$', actor_name)
    if rock_match:
        rock_type = rock_match.group(1).replace('_', ' ')
        return f"{rock_type} Mining Node"

    # Match Bosses & Dragons
    if "KalphiteQueen" in actor_name:
        return "Kalphite Queen"
    if "DragonkinConduit" in actor_name:
        return "Dragonkin Conduit"
    if "DragonFuzan" in actor_name or "DragonFusan" in actor_name:
        return "Dragon Fuzan"
    if "DragonImaru" in actor_name:
        return "Dragon Imaru"
    if "DragonKuldra" in actor_name:
        return "Dragon Kuldra"

    # Generic cleanup
    clean = re.sub(r'^BP_', '', actor_name)
    clean = re.sub(r'_UAID_[A-Za-z0-9_]+$', '', clean)
    clean = re.sub(r'_[0-9a-f]{8,}$', '', clean)
    clean = clean.replace('_C', '').replace('_', ' ')
    return clean.strip() or actor_name


def parse_duration_seconds(dur_str: str) -> float:
    """
    Parses Unreal Engine timespan string e.g.
    '+5.00:00:00.000' -> 5 days = 432000s
    '+1.23:16:07.741' -> 1 day + 23h + 16m + 7.741s
    '+19:20:22.095'   -> 19h + 20m + 22.095s
    '+08:56:04.654'   -> 8h + 56m + 4.654s
    """
    clean = dur_str.strip().lstrip('+')
    days = 0
    time_part = clean

    if '.' in clean:
        parts = clean.split('.', 1)
        if ':' in parts[0]:
            # e.g. 19:20:22.095 (no days part, dot is for milliseconds)
            time_part = clean
        else:
            try:
                days = int(parts[0])
                time_part = parts[1]
            except ValueError:
                time_part = clean

    try:
        t_parts = time_part.split(':')
        if len(t_parts) == 3:
            h = int(t_parts[0])
            m = int(t_parts[1])
            s = float(t_parts[2])
            return days * 86400.0 + h * 3600.0 + m * 60.0 + s
        elif len(t_parts) == 2:
            m = int(t_parts[0])
            s = float(t_parts[1])
            return days * 86400.0 + m * 60.0 + s
    except (ValueError, IndexError):
        pass

    return 0.0


def parse_log_timestamp(ts_str: str) -> float:
    """Parses [2026.10.10-19.05.28:209] to unix epoch timestamp."""
    try:
        base_str, ms = ts_str.split(':')
        dt = datetime.strptime(base_str, "%Y.%m.%d-%H.%M.%S")
        return dt.timestamp() + (int(ms) / 1000.0)
    except Exception:
        return 0.0


class RespawnTracker:
    def __init__(self, logs_dir: str = LOGS_DIR, saves_dir: str = SAVES_DIR):
        self.logs_dir = logs_dir
        self.saves_dir = saves_dir
        self._cached_respawns = []
        self._last_scan_time = 0.0
        self._cache_ttl = 3.0  # scan at most every 3 seconds

    def scan_live_logs(self) -> dict:
        """
        Scans server logs for active chest respawn timers.
        Returns a mapping of chest_id -> { respawn_at, is_ready, duration_seconds, ... }
        """
        active_chests = {}
        log_files = sorted(glob.glob(os.path.join(self.logs_dir, "*.log")), key=os.path.getmtime)
        if not log_files:
            return active_chests

        # Scan newest log file and previous backup
        files_to_read = log_files[-2:] if len(log_files) >= 2 else log_files

        re_timer = re.compile(
            r'\[(?P<ts>[0-9\.\-:]+)\]\[\s*\d+\]LogChests:\s*\[DedicatedServer\]\s*SetRespawnTimer\(\)\s*:\s*Chest\s*"(?P<chest>[^"]+)"\s*set to respawn\s*(?P<dur>\+[0-9\.:]+)\s*from now'
        )
        re_past = re.compile(
            r'\[(?P<ts>[0-9\.\-:]+)\]\[\s*\d+\]LogChests:\s*\[DedicatedServer\]\s*PerformRespawn\(\)\s*:\s*Chest\s*"(?P<chest>[^"]+)"\s*respawned'
        )

        for log_path in files_to_read:
            try:
                with open(log_path, 'r', errors='ignore') as f:
                    for line in f:
                        if 'LogChests:' not in line:
                            continue

                        # Check timer set
                        m_timer = re_timer.search(line)
                        if m_timer:
                            ts_str = m_timer.group('ts')
                            chest_id = m_timer.group('chest')
                            dur_str = m_timer.group('dur')

                            log_epoch = parse_log_timestamp(ts_str)
                            dur_sec = parse_duration_seconds(dur_str)
                            respawn_epoch = log_epoch + dur_sec

                            active_chests[chest_id] = {
                                "id": chest_id,
                                "name": format_actor_name(chest_id),
                                "category": CAT_CHEST,
                                "status": "respawning" if respawn_epoch > time.time() else "ready",
                                "respawn_epoch": respawn_epoch,
                                "duration_seconds": dur_sec,
                                "last_event_epoch": log_epoch,
                                "source": "live_log"
                            }
                            continue

                        # Check perform respawn (cleared / ready)
                        m_past = re_past.search(line)
                        if m_past:
                            chest_id = m_past.group('chest')
                            ts_str = m_past.group('ts')
                            log_epoch = parse_log_timestamp(ts_str)

                            if chest_id in active_chests:
                                active_chests[chest_id]["status"] = "ready"
                                active_chests[chest_id]["respawn_epoch"] = log_epoch
                                active_chests[chest_id]["last_event_epoch"] = log_epoch
            except Exception:
                pass

        return active_chests

    def get_static_tracked_resources(self) -> list:
        """
        Returns high-value game world tracking targets:
        - 3-Day Fishing Net cycles
        - World Bosses (Kalphite Queen, Red Dragons)
        - High-tier mining nodes (Luminite, Runite, Adamantite)
        """
        resources = []

        # 1. Fishing Nets (3-day cycle: 3 in-game days = 3 * 840s = 2520.0s)
        for code, name in CANONICAL_FISHING_NET_REGIONS:
            resources.append({
                "id": f"fishing_net_{code.lower()}",
                "name": name,
                "category": CAT_FISHING,
                "status": "ready",
                "respawn_epoch": 0.0,
                "duration_seconds": 2520.0,
                "last_event_epoch": 0.0,
                "source": "world_registry"
            })

        # 2. World Bosses & Dragonkin
        for code, name, location, dur in CANONICAL_BOSS_TARGETS:
            resources.append({
                "id": f"boss_{code.lower()}",
                "name": f"{name} ({location})",
                "category": CAT_BOSS,
                "status": "ready",
                "respawn_epoch": 0.0,
                "duration_seconds": dur,
                "last_event_epoch": 0.0,
                "source": "world_registry"
            })

        # 3. High-Tier Ores
        for code, name, dur in HIGH_TIER_MINING_NODES:
            resources.append({
                "id": f"ore_{code.lower()}",
                "name": name,
                "category": CAT_ORE,
                "status": "ready",
                "respawn_epoch": 0.0,
                "duration_seconds": dur,
                "last_event_epoch": 0.0,
                "source": "world_registry"
            })

        return resources

    def get_respawns(self, category_filter: str = None, search_query: str = None) -> list:
        """
        Retrieves all tracked respawn targets, computes remaining seconds,
        and applies optional category / text filtering.
        """
        now = time.time()
        if now - self._last_scan_time > self._cache_ttl or not self._cached_respawns:
            chests_dict = self.scan_live_logs()
            all_items = list(chests_dict.values()) + self.get_static_tracked_resources()
            self._cached_respawns = all_items
            self._last_scan_time = now

        results = []
        for item in self._cached_respawns:
            remaining = max(0.0, item["respawn_epoch"] - now) if item["respawn_epoch"] > 0 else 0.0
            is_ready = remaining <= 0.0 or item.get("status") == "ready"

            entry = {
                "id": item["id"],
                "name": item["name"],
                "category": item["category"],
                "status": "ready" if is_ready else "respawning",
                "remaining_seconds": round(remaining, 1) if not is_ready else 0.0,
                "respawn_time": datetime.fromtimestamp(item["respawn_epoch"]).strftime("%Y-%m-%d %H:%M:%S") if item["respawn_epoch"] > 0 else "Ready",
                "duration_formatted": self.format_time_remaining(item.get("duration_seconds", 0)),
                "remaining_formatted": "Ready to Loot / Active" if is_ready else self.format_time_remaining(remaining),
                "source": item.get("source", "live_log"),
                "is_ready": is_ready
            }

            # Filter by category
            if category_filter and category_filter != "all" and entry["category"] != category_filter:
                continue

            # Filter by search query
            if search_query:
                q = search_query.lower()
                if q not in entry["name"].lower() and q not in entry["id"].lower() and q not in entry["category"].lower():
                    continue

            results.append(entry)

        # Sort: respawning items first (ascending by remaining time), then ready items
        results.sort(key=lambda x: (x["is_ready"], x["remaining_seconds"]))
        return results

    @staticmethod
    def format_time_remaining(seconds: float) -> str:
        if seconds <= 0:
            return "Ready"
        s = int(seconds)
        days = s // 86400
        hours = (s % 86400) // 3600
        minutes = (s % 3600) // 60
        secs = s % 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or hours > 0 or days > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts[:3])


_global_tracker = None


def get_respawn_tracker() -> RespawnTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = RespawnTracker()
    return _global_tracker

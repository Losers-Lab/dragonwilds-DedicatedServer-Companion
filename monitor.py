import os
import re
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
import config
from state import set_player, remove_player, update_field, add_event, clear_players, set_character_name
from database import log_event, player_join, player_leave

_server_started_at = None


def get_server_started_at():
    return _server_started_at


def set_server_started_at(dt):
    global _server_started_at
    _server_started_at = dt


def container_running():
    if not config.CONTAINER:
        return False
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", config.CONTAINER],
        capture_output=True,
        text=True
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def parse_line(line, is_replay=False):
    global _server_started_at

    # Track player character name assignments
    char_info = re.search(r"Account\[XP:([a-f0-9]+)\]\s+Character Name\[(.*?)\]", line, re.IGNORECASE)
    if char_info:
        set_character_name(char_info.group(1).lower(), char_info.group(2).strip())

    # Track server start time from early timestamps if not set
    if _server_started_at is None:
        ts_match = re.search(r"\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})", line)
        if ts_match:
            try:
                _server_started_at = datetime.strptime(
                    ts_match.group(1), "%Y.%m.%d-%H.%M.%S"
                ).replace(tzinfo=timezone.utc)
            except Exception:
                pass

    # Check for server exit / shutdown
    if "Engine exit requested" in line or "Exit: Exiting" in line:
        clear_players()
        add_event("Server stopped")
        if not is_replay:
            log_event("Server stopped")
        update_field("status", "offline")
        return

    # Check for player join
    added = re.search(r"Player ADDED to session \[(.*?)\]-\[(.*?)\]", line)
    if added:
        account = added.group(1)
        name = added.group(2)

        set_player(account, name, notify=not is_replay)
        if not is_replay:
            player_join(account, name)
            log_event(f"{name} joined")
        return

    # Check for player leave
    removed = re.search(r"Player Removed from session \[(.*?)\]-\[(.*?)\]", line)
    if removed:
        account = removed.group(1)
        name = removed.group(2)

        remove_player(account, name, notify=not is_replay)
        if not is_replay:
            player_leave(account)
            log_event(f"{name} left")
        return

    # Check for save completed & world name
    world = re.search(r"Save completed SUCCESSFULLY \(slot:\s*(.*?)\)", line)
    if world:
        slot = world.group(1)
        update_field("world", slot)
        add_event(f"World saved (slot: {slot})", category="server")
        if not is_replay:
            log_event(f"World saved (slot: {slot})")
        return

    # ProjectVersion detection (from sirhakon fork)
    project_version = re.search(r"LogNetVersion:\s*Set ProjectVersion\s+to\s+([0-9]+(?:\.[0-9]+)*)\.", line)
    if project_version:
        update_field("version", project_version.group(1))
        return



# --- File-based log monitoring (for native host servers like C:\DragonwildsServer) ---

def load_recent_file_logs():
    global _server_started_at
    if not config.LOG_PATH or not os.path.exists(config.LOG_PATH):
        return

    try:
        # First read the beginning of the file to determine start timestamp and version
        with open(config.LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(1200):
                early_line = f.readline()
                if not early_line:
                    break
                if _server_started_at is None:
                    ts_match = re.search(r"\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})", early_line)
                    if ts_match:
                        try:
                            _server_started_at = datetime.strptime(
                                ts_match.group(1), "%Y.%m.%d-%H.%M.%S"
                            ).replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                pv_match = re.search(r"LogNetVersion:\s*Set ProjectVersion\s+to\s+([0-9]+(?:\.[0-9]+)*)\.", early_line)
                if pv_match:
                    update_field("version", pv_match.group(1))
                    print(f"Detected ProjectVersion from startup: {pv_match.group(1)}", flush=True)

        # Pre-scan for character name assignments across the log
        with open(config.LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "Character Name[" in line:
                    char_info = re.search(r"Account\[XP:([a-f0-9]+)\]\s+Character Name\[(.*?)\]", line, re.IGNORECASE)
                    if char_info:
                        set_character_name(char_info.group(1).lower(), char_info.group(2).strip())

        # Then replay the tail lines into state without sending alert spam
        with open(config.LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            lines = deque(f, maxlen=config.LOG_LINES_ON_START)

        for line in lines:
            parse_line(line, is_replay=True)

        # Check if the log was recently written (within last 3 minutes)
        stat = os.stat(config.LOG_PATH)
        if time.time() - stat.st_mtime <= 180:
            update_field("status", "online")
        else:
            update_field("status", "offline")

    except Exception as e:
        print(f"Error loading recent file logs: {e}")


def follow_file_logs_forever():
    was_running = False
    file_handle = None
    last_size = 0

    while True:
        log_path = config.LOG_PATH
        if not log_path or not os.path.exists(log_path):
            if was_running:
                clear_players()
                add_event("Server log unavailable")
                log_event("Server log unavailable")
                update_field("status", "offline")
                was_running = False
            time.sleep(5)
            continue

        try:
            stat = os.stat(log_path)

            # Check if file was rotated or truncated (new file or size shrank)
            if file_handle is None or stat.st_size < last_size:
                if file_handle:
                    try:
                        file_handle.close()
                    except Exception:
                        pass
                file_handle = open(log_path, "r", encoding="utf-8", errors="ignore")

                if stat.st_size < last_size:
                    # Log file was truncated / server restarted
                    clear_players()
                    add_event("Server restarted")
                    log_event("Server restarted")
                    update_field("status", "online")
                    last_size = 0
                else:
                    file_handle.seek(0, os.SEEK_END)
                    last_size = file_handle.tell()

                if not was_running:
                    update_field("status", "online")
                    was_running = True

            line = file_handle.readline()
            if line:
                last_size = file_handle.tell()
                if not was_running:
                    update_field("status", "online")
                    was_running = True
                parse_line(line, is_replay=False)
            else:
                last_size = file_handle.tell()
                # If no log activity for > 3 minutes, check if server is offline
                idle_seconds = time.time() - stat.st_mtime
                if was_running and idle_seconds > 180:
                    clear_players()
                    add_event("Server heartbeat lost")
                    update_field("status", "offline")
                    was_running = False
                elif not was_running and idle_seconds <= 60:
                    update_field("status", "online")
                    was_running = True

                time.sleep(0.5)

        except Exception as e:
            add_event(f"Log watcher error: {e}")
            if file_handle:
                try:
                    file_handle.close()
                except Exception:
                    pass
                file_handle = None
            time.sleep(5)


# --- Docker-based log monitoring (for game servers running inside Docker) ---

def load_recent_docker_logs():
    cmd = ["docker", "logs", "--tail", str(config.LOG_LINES_ON_START), config.CONTAINER]
    result = subprocess.run(cmd, capture_output=True, text=True)

    logs = result.stdout + "\n" + result.stderr
    for line in logs.splitlines():
        parse_line(line, is_replay=True)


def follow_docker_logs_forever():
    was_running = False

    while True:
        if not container_running():
            if was_running:
                clear_players()
                add_event("Server stopped")
                log_event("Server stopped")
                update_field("status", "offline")
                was_running = False

            time.sleep(5)
            continue

        if not was_running:
            clear_players()
            add_event("Server started")
            log_event("Server started")
            update_field("status", "online")
            was_running = True

        process = subprocess.Popen(
            ["docker", "logs", "-f", "--tail", "0", config.CONTAINER],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        try:
            for line in process.stdout:
                parse_line(line, is_replay=False)
        except Exception as e:
            add_event(f"Log watcher error: {e}")

        clear_players()
        add_event("Log stream reconnecting")
        time.sleep(5)


def capture_startup_docker_version():
    """Read full startup logs from docker container to find ProjectVersion (sirhakon feature)"""
    if not config.CONTAINER:
        return
    try:
        result = subprocess.run(
            ["docker", "logs", config.CONTAINER],
            capture_output=True,
            text=True,
            timeout=10
        )
        logs = result.stdout + "\n" + result.stderr

        for line in logs.splitlines():
            project_version = re.search(
                r"LogNetVersion:\s*Set ProjectVersion\s+to\s+([0-9]+(?:\.[0-9]+)*)\.",
                line,
            )
            if project_version:
                version = project_version.group(1)
                update_field("version", version)
                print(f"Captured startup ProjectVersion: {version}", flush=True)
                return
    except Exception as e:
        print(f"Error capturing startup version: {e}", flush=True)


# --- Entrypoint ---

def start_monitor():
    if config.LOG_PATH or not config.CONTAINER:
        load_recent_file_logs()
        thread = threading.Thread(target=follow_file_logs_forever, daemon=True)
        thread.start()
    else:
        capture_startup_docker_version()
        if container_running():
            load_recent_docker_logs()
        thread = threading.Thread(target=follow_docker_logs_forever, daemon=True)
        thread.start()
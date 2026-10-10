import threading
import time
from datetime import datetime, timezone
import config
from state import update_field
from utils import run_cmd, seconds_to_human


def update_stats():
    if config.CONTAINER:
        output, _, code = run_cmd([
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{.CPUPerc}}|{{.MemUsage}}",
            config.CONTAINER
        ])

        if code == 0 and "|" in output:
            cpu, memory = output.split("|", 1)
            memory = memory.split("/")[0].strip()

            update_field("cpu", cpu)
            update_field("memory", memory)

        started, _, code = run_cmd([
            "docker",
            "inspect",
            "-f",
            "{{.State.StartedAt}}",
            config.CONTAINER
        ])

        if code == 0 and started:
            try:
                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                uptime = datetime.now(timezone.utc) - started_dt
                update_field("uptime", seconds_to_human(uptime.total_seconds()))
            except Exception:
                update_field("uptime", "Unknown")
    else:
        # Host-based server monitoring (no container)
        update_field("cpu", "N/A (Host)")
        update_field("memory", "N/A (Host)")

        # Compute uptime from server log start timestamp
        try:
            from monitor import get_server_started_at
            started_dt = get_server_started_at()
            if started_dt:
                uptime = datetime.now(timezone.utc) - started_dt
                update_field("uptime", seconds_to_human(uptime.total_seconds()))
        except Exception:
            pass


def stats_loop():
    while True:
        update_stats()
        time.sleep(5)


def start_dockerstats():
    thread = threading.Thread(target=stats_loop, daemon=True)
    thread.start()
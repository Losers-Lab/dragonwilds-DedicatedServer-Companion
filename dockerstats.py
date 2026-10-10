import os
import json
import threading
import time
from datetime import datetime, timezone
import config
from state import update_field
from utils import run_cmd, seconds_to_human


_last_cpu_idle = None
_last_cpu_total = None


def get_proc_stats():
    global _last_cpu_idle, _last_cpu_total
    cpu_str = "0.0%"
    mem_str = "N/A"

    # 1. Real-time CPU percentage from /proc/stat
    try:
        with open("/proc/stat", "r") as f:
            fields = [float(x) for x in f.readline().split()[1:]]
            idle = fields[3] + fields[4]
            total = sum(fields)
            if _last_cpu_total is not None and (total - _last_cpu_total) > 0:
                diff_idle = idle - _last_cpu_idle
                diff_total = total - _last_cpu_total
                pct = max(0.0, min(100.0, 100.0 * (1.0 - diff_idle / diff_total)))
                cpu_str = f"{pct:.1f}%"
            _last_cpu_idle = idle
            _last_cpu_total = total
    except Exception:
        pass

    # 2. Real-time RAM usage from /proc/meminfo
    try:
        mem = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].split()[0])
        total_mb = mem.get("MemTotal", 0) / 1024
        avail_mb = mem.get("MemAvailable", mem.get("MemFree", 0)) / 1024
        used_mb = max(0, total_mb - avail_mb)
        if used_mb >= 1024:
            mem_str = f"{used_mb / 1024:.1f} GiB"
        else:
            mem_str = f"{used_mb:.0f} MiB"
    except Exception:
        pass

    return cpu_str, mem_str


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
        # Host-based server monitoring: calculate live system CPU and RAM
        cpu, memory = get_proc_stats()
        update_field("cpu", cpu)
        update_field("memory", memory)

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
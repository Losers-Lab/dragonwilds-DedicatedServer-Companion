import os
import time
import threading
import config
from state import update_field
from utils import seconds_to_human


_last_mtime = None


def newest_save_mtime():
    newest = None

    if not os.path.exists(config.SAVE_PATH):
        return None

    for root, dirs, files in os.walk(config.SAVE_PATH):
        for file in files:
            path = os.path.join(root, file)

            try:
                mtime = os.path.getmtime(path)
            except Exception:
                continue

            if newest is None or mtime > newest:
                newest = mtime

    return newest


def save_loop():
    global _last_mtime

    while True:
        newest = newest_save_mtime()

        if newest:
            update_field("last_save", seconds_to_human(time.time() - newest) + " ago")
            if _last_mtime is None or newest > _last_mtime:
                try:
                    from worldreader import get_world_data
                    wdata = get_world_data()
                    if wdata.get("day_count"):
                        update_field("day_count", wdata["day_count"])
                    if wdata.get("weather"):
                        update_field("weather", wdata["weather"])
                except Exception:
                    pass
            _last_mtime = newest

        time.sleep(5)


def start_savewatcher():
    thread = threading.Thread(target=save_loop, daemon=True)
    thread.start()
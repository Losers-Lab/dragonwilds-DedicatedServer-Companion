import os

CONTAINER = os.getenv("CONTAINER", "")
SAVE_PATH = os.getenv(
    "SAVE_PATH",
    "/savegames" if os.path.exists("/savegames") else r"C:\DragonwildsServer\RSDragonwilds\Saved\SaveGames"
)
LOG_PATH = os.getenv(
    "LOG_PATH",
    "/logs/RSDragonwilds.log" if os.path.exists("/logs/RSDragonwilds.log") else (
        r"C:\DragonwildsServer\RSDragonwilds\Saved\Logs\RSDragonwilds.log"
        if os.path.exists(r"C:\DragonwildsServer\RSDragonwilds\Saved\Logs\RSDragonwilds.log")
        else ""
    )
)
MAX_PLAYERS = int(os.getenv("MAX_PLAYERS", "6"))
PORT = int(os.getenv("PORT", "9876"))
SERVER_NAME = os.getenv("SERVER_NAME", "Dragonwilds")

LOG_LINES_ON_START = int(os.getenv("LOG_LINES_ON_START", "10000"))

SERVER_CONFIG_PATH = os.getenv(
    "SERVER_CONFIG_PATH",
    "/serverconfig/DedicatedServer.ini" if os.path.exists("/serverconfig/DedicatedServer.ini") else (
        r"C:\DragonwildsServer\RSDragonwilds\Saved\Config\WindowsServer\DedicatedServer.ini"
        if os.path.exists(r"C:\DragonwildsServer\RSDragonwilds\Saved\Config\WindowsServer\DedicatedServer.ini")
        else ""
    )
)
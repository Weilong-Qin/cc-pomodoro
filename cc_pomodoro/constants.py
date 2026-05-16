from pathlib import Path

APP_NAME = "cc-pomodoro"
VERSION = "0.1.0"

CONFIG_DIR = Path.home() / ".config" / "cc-pomodoro"
STATE_FILE = CONFIG_DIR / "state.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_FILE = CONFIG_DIR / "sessions.jsonl"

DEFAULT_DURATION = 50

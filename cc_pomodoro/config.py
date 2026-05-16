from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cc_pomodoro.constants import CONFIG_DIR, CONFIG_FILE, DEFAULT_DURATION

DEFAULT_CONFIG: dict[str, Any] = {
    "duration": DEFAULT_DURATION,
    "auto_start": False,
    "auto_start_apps": ["claude-code", "codex-cli"],
    "notify_on_complete": True,
    "notify_sound": True,
}


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_config() -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        raw = CONFIG_FILE.read_text(encoding="utf-8")
        if raw.strip():
            stored = json.loads(raw)
            config.update(stored)
    return config


def get(key: str) -> Any:
    return get_config()[key]


def set_config(key: str, value: Any) -> None:
    config = get_config()
    config[key] = value
    _ensure_config_dir()
    _atomic_write(CONFIG_FILE, json.dumps(config, indent=2, ensure_ascii=False) + "\n")


def ensure_default_config() -> dict[str, Any]:
    _ensure_config_dir()
    if not CONFIG_FILE.exists():
        _atomic_write(
            CONFIG_FILE,
            json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n",
        )
    return get_config()

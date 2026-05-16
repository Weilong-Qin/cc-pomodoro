from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cc_pomodoro.constants import STATE_FILE
from cc_pomodoro.config import _atomic_write, _ensure_config_dir


def _default_state() -> dict[str, Any]:
    return {
        "active": False,
        "session_id": None,
        "started_at": None,
        "end_at": None,
        "duration": 0,
        "app": None,
    }


def get_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        raw = STATE_FILE.read_text(encoding="utf-8")
        if raw.strip():
            stored = json.loads(raw)
            return stored
    return dict(_default_state())


def is_active() -> bool:
    state = get_state()
    if not state.get("active"):
        return False
    remaining = get_remaining_seconds()
    if remaining <= 0:
        return False
    return True


def get_remaining_seconds() -> int:
    state = get_state()
    if not state.get("active"):
        return 0
    end_at_str = state.get("end_at")
    if not end_at_str:
        return 0
    try:
        end_at = datetime.fromisoformat(end_at_str)
        now = datetime.now(timezone.utc)
        remaining = (end_at - now).total_seconds()
        return max(0, int(remaining))
    except (ValueError, TypeError):
        return 0


def get_session_id() -> str | None:
    state = get_state()
    return state.get("session_id")


def start_session(duration_min: int, app: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    started_at = now.isoformat()
    end_at = (now + timedelta(minutes=duration_min)).isoformat()
    state = {
        "active": True,
        "session_id": session_id,
        "started_at": started_at,
        "end_at": end_at,
        "duration": duration_min,
        "app": app,
    }
    _ensure_config_dir()
    _atomic_write(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return session_id


def end_session() -> dict[str, Any]:
    state = get_state()
    state["active"] = False
    _ensure_config_dir()
    _atomic_write(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return state

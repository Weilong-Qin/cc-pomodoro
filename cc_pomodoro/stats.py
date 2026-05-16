from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cc_pomodoro.constants import CONFIG_DIR, SESSIONS_FILE


def make_record(
    *,
    session_id: str,
    started_at: str,
    ended_at: str,
    duration_planned: int,
    duration_actual: int,
    ended_by: str,
    app: str,
    blocking_requests_queued: int = 0,
    label: str = "",
) -> dict[str, Any]:
    """Create a session record dict following the stats schema.

    Schema version 1 fields:
      - id: unique session identifier (uuid)
      - started_at: ISO-8601 timestamp when the session began
      - ended_at: ISO-8601 timestamp when the session ended
      - duration_planned: planned duration in minutes
      - duration_actual: actual elapsed minutes
      - ended_by: "completed" | "user_stop" | "process_killed"
      - app: application name (e.g. "claude-code", "codex-cli")
      - blocking_requests_queued: number of blocked tool requests
      - label: optional user label
      - schema_version: 1
    """
    return {
        "id": session_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_planned": duration_planned,
        "duration_actual": duration_actual,
        "ended_by": ended_by,
        "app": app,
        "blocking_requests_queued": blocking_requests_queued,
        "label": label,
        "schema_version": 1,
    }


def append_session(record: dict[str, Any]) -> None:
    """Append one JSON line to sessions.jsonl (atomic-ish via O_APPEND).

    Creates the config directory and file if they do not exist.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with SESSIONS_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def read_sessions() -> list[dict[str, Any]]:
    """Read all session records from sessions.jsonl.

    Returns an empty list if the file does not exist or is empty.
    Silently skips empty or malformed lines.
    """
    if not SESSIONS_FILE.exists():
        return []

    sessions: list[dict[str, Any]] = []
    with SESSIONS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                sessions.append(json.loads(stripped))
            except json.JSONDecodeError:
                # Skip malformed lines silently
                continue
    return sessions


def get_stats() -> dict[str, Any]:
    """Aggregate statistics from all recorded sessions.

    Returns a dict with:
      - today_minutes: total actual minutes spent today (UTC)
      - week_minutes: total actual minutes this week (UTC, Mon-Sun)
      - by_app: {app_name: total_minutes}
      - recent_sessions: last 5 sessions sorted by ended_at descending
    """
    sessions = read_sessions()
    if not sessions:
        return {
            "today_minutes": 0,
            "week_minutes": 0,
            "by_app": {},
            "recent_sessions": [],
        }

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_monday = today_start.weekday()
    week_start = today_start - timedelta(days=days_since_monday)

    today_minutes = 0
    week_minutes = 0
    by_app: dict[str, int] = {}

    for s in sessions:
        ended_at_str = s.get("ended_at")
        if not ended_at_str:
            continue
        try:
            ended_at = datetime.fromisoformat(ended_at_str)
        except (ValueError, TypeError):
            continue

        duration_actual = s.get("duration_actual", 0) or 0
        app_name = s.get("app", "unknown") or "unknown"

        if ended_at >= today_start:
            today_minutes += duration_actual
        if ended_at >= week_start:
            week_minutes += duration_actual

        by_app[app_name] = by_app.get(app_name, 0) + duration_actual

    # Last 5 sessions sorted by ended_at descending
    sorted_sessions = sorted(
        sessions,
        key=lambda s: s.get("ended_at", "") or "",
        reverse=True,
    )[:5]

    return {
        "today_minutes": today_minutes,
        "week_minutes": week_minutes,
        "by_app": by_app,
        "recent_sessions": sorted_sessions,
    }

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from cc_pomodoro.stats import (
    append_session,
    get_stats,
    make_record,
    read_sessions,
)


# -- Helpers -----------------------------------------------------------------

def _sample_record(**overrides: Any) -> dict:
    base: dict = {
        "session_id": "test-uuid",
        "started_at": "2026-05-16T10:00:00+00:00",
        "ended_at": "2026-05-16T10:50:00+00:00",
        "duration_planned": 50,
        "duration_actual": 50,
        "ended_by": "completed",
        "app": "claude-code",
    }
    base.update(**overrides)
    return make_record(**base)


# -- Tests -------------------------------------------------------------------

def test_make_record_schema() -> None:
    record = _sample_record()
    assert record["id"] == "test-uuid"
    assert record["started_at"] == "2026-05-16T10:00:00+00:00"
    assert record["ended_at"] == "2026-05-16T10:50:00+00:00"
    assert record["duration_planned"] == 50
    assert record["duration_actual"] == 50
    assert record["ended_by"] == "completed"
    assert record["app"] == "claude-code"
    assert record["blocking_requests_queued"] == 0
    assert record["label"] == ""
    assert record["schema_version"] == 1


def test_make_record_defaults() -> None:
    record = make_record(
        session_id="abc",
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:50:00+00:00",
        duration_planned=50,
        duration_actual=42,
        ended_by="user_stop",
        app="codex-cli",
        blocking_requests_queued=3,
        label="refactor auth",
    )
    assert record["blocking_requests_queued"] == 3
    assert record["label"] == "refactor auth"
    assert record["schema_version"] == 1
    assert record["ended_by"] == "user_stop"


def test_append_and_read_sessions(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    with mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file):
        r1 = _sample_record(session_id="sess-1", duration_planned=25, duration_actual=25)
        r2 = _sample_record(session_id="sess-2", duration_planned=50, duration_actual=42)

        append_session(r1)
        append_session(r2)

        sessions = read_sessions()
        assert len(sessions) == 2
        assert sessions[0]["id"] == "sess-1"
        assert sessions[1]["id"] == "sess-2"


def test_read_sessions_empty(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    with mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file):
        assert read_sessions() == []


def test_read_sessions_no_file(tmp_path: Path) -> None:
    sessions_file = tmp_path / "nonexistent" / "sessions.jsonl"
    with mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file):
        assert read_sessions() == []


def test_read_sessions_skips_empty_lines(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    sessions_file.write_text(
        '{"id":"a"}\n\n{"id":"b"}\n\n', encoding="utf-8"
    )
    with mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file):
        sessions = read_sessions()
        assert len(sessions) == 2


def test_read_sessions_skips_malformed_lines(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    sessions_file.write_text(
        '{"id":"a"}\nnot-json\n{"id":"b"}\n', encoding="utf-8"
    )
    with mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file):
        sessions = read_sessions()
        assert len(sessions) == 2


def test_get_stats_empty(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    with mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file):
        stats = get_stats()
        assert stats["today_minutes"] == 0
        assert stats["week_minutes"] == 0
        assert stats["by_app"] == {}
        assert stats["recent_sessions"] == []


def test_get_stats_today_counts(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    with (
        mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file),
        mock.patch("cc_pomodoro.stats.datetime") as mock_dt,
    ):
        # Freeze time to a known point
        now = datetime(2026, 5, 16, 14, 30, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.timezone = timezone
        mock_dt.timedelta = __import__("datetime").timedelta

        # Session today
        append_session(
            _sample_record(
                session_id="today-1",
                ended_at="2026-05-16T12:00:00+00:00",
                duration_actual=30,
            )
        )
        # Session yesterday
        append_session(
            _sample_record(
                session_id="yesterday-1",
                started_at="2026-05-15T10:00:00+00:00",
                ended_at="2026-05-15T10:50:00+00:00",
                duration_actual=50,
            )
        )

        stats = get_stats()
        assert stats["today_minutes"] == 30
        assert stats["week_minutes"] == 80  # both today and yesterday
        assert stats["by_app"] == {"claude-code": 80}
        assert len(stats["recent_sessions"]) == 2


def test_get_stats_by_app(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    with (
        mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file),
        mock.patch("cc_pomodoro.stats.datetime") as mock_dt,
    ):
        now = datetime(2026, 5, 16, 14, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.timezone = timezone
        mock_dt.timedelta = __import__("datetime").timedelta

        append_session(
            _sample_record(app="claude-code", duration_actual=50)
        )
        append_session(
            _sample_record(
                session_id="cc2",
                app="claude-code",
                duration_actual=30,
            )
        )
        append_session(
            _sample_record(
                session_id="codex1",
                app="codex-cli",
                duration_actual=25,
            )
        )

        stats = get_stats()
        assert stats["by_app"] == {"claude-code": 80, "codex-cli": 25}


def test_get_stats_recent_sessions(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    with (
        mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file),
        mock.patch("cc_pomodoro.stats.datetime") as mock_dt,
    ):
        now = datetime(2026, 5, 16, 14, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.timezone = timezone
        mock_dt.timedelta = __import__("datetime").timedelta

        for i in range(7):
            append_session(
                _sample_record(
                    session_id=f"sess-{i}",
                    ended_at=f"2026-05-16T0{i}:00:00+00:00",
                    duration_actual=25,
                )
            )

        stats = get_stats()
        assert len(stats["recent_sessions"]) == 5
        # Most recent first
        assert stats["recent_sessions"][0]["id"] == "sess-6"
        assert stats["recent_sessions"][-1]["id"] == "sess-2"


def test_append_creates_directory(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "dir"
    sessions_file = nested / "sessions.jsonl"
    with (
        mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file),
        mock.patch("cc_pomodoro.stats.CONFIG_DIR", nested),
    ):
        record = _sample_record()
        append_session(record)

        assert sessions_file.exists()
        sessions = read_sessions()
        assert len(sessions) == 1


def test_append_file_is_jsonl(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.jsonl"
    with mock.patch("cc_pomodoro.stats.SESSIONS_FILE", sessions_file):
        r1 = _sample_record(session_id="a")
        r2 = _sample_record(session_id="b")
        append_session(r1)
        append_session(r2)

        raw = sessions_file.read_text(encoding="utf-8")
        lines = [l for l in raw.split("\n") if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == "a"
        assert json.loads(lines[1])["id"] == "b"

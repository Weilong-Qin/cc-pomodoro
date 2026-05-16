from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from cc_pomodoro.state import (
    end_session,
    get_remaining_seconds,
    get_session_id,
    get_state,
    is_active,
    start_session,
)


def test_default_state_when_no_file(tmp_path: Path) -> None:
    with mock.patch("cc_pomodoro.state.STATE_FILE", tmp_path / "state.json"):
        state = get_state()
        assert state["active"] is False
        assert state["session_id"] is None
        assert state["started_at"] is None
        assert state["end_at"] is None
        assert state["duration"] == 0
        assert state["app"] is None


def test_start_session_creates_active_state(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        session_id = start_session(duration_min=25, app="claude-code")

        assert session_id is not None
        assert isinstance(session_id, str)

        state = get_state()
        assert state["active"] is True
        assert state["session_id"] == session_id
        assert state["duration"] == 25
        assert state["app"] == "claude-code"
        assert state["started_at"] is not None
        assert state["end_at"] is not None


def test_start_session_generates_unique_ids(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        id1 = start_session(duration_min=25, app="claude-code")
        id2 = start_session(duration_min=50, app="codex-cli")
        assert id1 != id2


def test_end_session_clears_active(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        start_session(duration_min=25, app="claude-code")
        final_state = end_session()

        assert final_state["active"] is False
        assert final_state["session_id"] is not None

        state = get_state()
        assert state["active"] is False


def test_is_active_true_when_session_running(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        start_session(duration_min=25, app="claude-code")
        assert is_active() is True


def test_is_active_false_after_end(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        start_session(duration_min=25, app="claude-code")
        end_session()
        assert is_active() is False


def test_is_active_false_when_no_session(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        assert is_active() is False


def test_get_remaining_seconds_active(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        with mock.patch(
            "cc_pomodoro.state.datetime"
        ) as mock_dt:
            now = datetime(2026, 5, 16, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.timezone = timezone

            start_session(duration_min=10, app="claude-code")

            remaining = get_remaining_seconds()
            assert remaining == 10 * 60


def test_get_remaining_seconds_expired(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        start_session(duration_min=0, app="claude-code")
        remaining = get_remaining_seconds()
        assert remaining == 0


def test_get_remaining_seconds_inactive(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        assert get_remaining_seconds() == 0


def test_get_session_id(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        assert get_session_id() is None

        sid = start_session(duration_min=25, app="claude-code")
        assert get_session_id() == sid

        end_session()
        assert get_session_id() == sid


def test_state_file_atomicity(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        start_session(duration_min=25, app="claude-code")

        raw = state_file.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert parsed["active"] is True
        assert parsed["duration"] == 25

        tmp_file = state_file.with_suffix(".tmp")
        assert not tmp_file.exists()


def test_directory_auto_creation(tmp_path: Path) -> None:
    nested_dir = tmp_path / "nonexistent" / "deep"
    state_file = nested_dir / "state.json"

    with (
        mock.patch("cc_pomodoro.state.STATE_FILE", state_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", nested_dir),
    ):
        session_id = start_session(duration_min=25, app="claude-code")
        assert state_file.exists()
        assert get_session_id() == session_id


def test_start_session_overwrites_previous(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        session_id_1 = start_session(duration_min=25, app="claude-code")
        session_id_2 = start_session(duration_min=50, app="codex-cli")

        assert session_id_1 != session_id_2
        state = get_state()
        assert state["session_id"] == session_id_2
        assert state["duration"] == 50
        assert state["app"] == "codex-cli"


def test_get_remaining_seconds_counts_down(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    with mock.patch("cc_pomodoro.state.STATE_FILE", state_file):
        start_session(duration_min=25, app="claude-code")

        remaining_1 = get_remaining_seconds()
        time.sleep(0.01)
        remaining_2 = get_remaining_seconds()

        assert remaining_2 <= remaining_1

"""Tests for cc_pomodoro.cli — parser construction and command dispatch.

These tests validate argument parsing via ``create_parser()`` and the
helper functions.  Actual subprocess spawning and side-effectful command
handlers (start / stop / status) are NOT exercised here.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from cc_pomodoro.cli import (
    _format_dt,
    _parse_config_value,
    create_parser,
)
from cc_pomodoro.stats import make_record


# -- Parser tests ------------------------------------------------------------

def test_create_parser() -> None:
    parser = create_parser()
    assert parser.prog == "cc-pomodoro"


def test_start_no_args() -> None:
    parser = create_parser()
    args = parser.parse_args(["start"])
    assert args.command == "start"
    assert args.duration is None  # resolved at runtime from config
    assert args.app is None  # resolved at runtime
    assert args.prompt_text is None


def test_start_with_duration() -> None:
    parser = create_parser()
    args = parser.parse_args(["start", "--duration", "25"])
    assert args.duration == 25


def test_start_with_app() -> None:
    parser = create_parser()
    args = parser.parse_args(["start", "--app", "codex-cli"])
    assert args.app == "codex-cli"


def test_start_with_prompt_text() -> None:
    parser = create_parser()
    args = parser.parse_args(["start", "重构 auth 模块"])
    assert args.prompt_text == "重构 auth 模块"
    assert args.duration is None  # defaults preserved


def test_start_with_all_options() -> None:
    parser = create_parser()
    args = parser.parse_args(
        ["start", "--duration", "30", "--app", "codex-cli", "fix bugs"]
    )
    assert args.duration == 30
    assert args.app == "codex-cli"
    assert args.prompt_text == "fix bugs"


def test_stop() -> None:
    parser = create_parser()
    args = parser.parse_args(["stop"])
    assert args.command == "stop"


def test_status() -> None:
    parser = create_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_stats() -> None:
    parser = create_parser()
    args = parser.parse_args(["stats"])
    assert args.command == "stats"
    assert args.json is False


def test_stats_json() -> None:
    parser = create_parser()
    args = parser.parse_args(["stats", "--json"])
    assert args.command == "stats"
    assert args.json is True


def test_config_no_args() -> None:
    parser = create_parser()
    args = parser.parse_args(["config"])
    assert args.command == "config"
    assert args.config_action is None
    assert args.key is None
    assert args.value is None


def test_config_set() -> None:
    parser = create_parser()
    args = parser.parse_args(["config", "set", "duration", "25"])
    assert args.command == "config"
    assert args.config_action == "set"
    assert args.key == "duration"
    assert args.value == "25"


def test_config_set_auto_start() -> None:
    parser = create_parser()
    args = parser.parse_args(["config", "set", "auto_start", "false"])
    assert args.key == "auto_start"
    assert args.value == "false"


def test_config_set_notify_on_complete() -> None:
    parser = create_parser()
    args = parser.parse_args(
        ["config", "set", "notify_on_complete", "true"]
    )
    assert args.key == "notify_on_complete"
    assert args.value == "true"


def test_unknown_command_shows_help() -> None:
    """Unknown subcommand should exit with status 2 (argparse default)."""
    parser = create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["unknown"])


# -- Helper: _parse_config_value ---------------------------------------------

class TestParseConfigValue:
    def test_true(self) -> None:
        assert _parse_config_value("true") is True
        assert _parse_config_value("yes") is True
        assert _parse_config_value("on") is True
        assert _parse_config_value("1") is True

    def test_false(self) -> None:
        assert _parse_config_value("false") is False
        assert _parse_config_value("no") is False
        assert _parse_config_value("off") is False
        assert _parse_config_value("0") is False

    def test_int(self) -> None:
        assert _parse_config_value("25") == 25
        assert _parse_config_value("0") is False  # "0" is falsy, caught earlier
        assert _parse_config_value("42") == 42

    def test_float(self) -> None:
        assert _parse_config_value("3.14") == 3.14
        assert _parse_config_value("0.5") == 0.5

    def test_str(self) -> None:
        assert _parse_config_value("hello") == "hello"
        assert _parse_config_value("claude-code") == "claude-code"


# -- Helper: _format_dt ------------------------------------------------------

class TestFormatDt:
    def test_formats_iso(self) -> None:
        result = _format_dt("2026-05-16T10:30:00+00:00")
        assert result == "05-16 10:30"

    def test_empty_string(self) -> None:
        assert _format_dt("") == ""

    def test_none(self) -> None:
        assert _format_dt(None) == ""  # type: ignore[arg-type]

    def test_invalid_fallback(self) -> None:
        result = _format_dt("not-a-date")
        assert result == "not-a-date"


# -- Integration: stats command helpers --------------------------------------

def test_make_and_format_record() -> None:
    """Verify the record schema cli.py depends on matches stats.py."""
    record = make_record(
        session_id="int-test",
        started_at="2026-05-16T10:00:00+00:00",
        ended_at="2026-05-16T10:50:00+00:00",
        duration_planned=50,
        duration_actual=42,
        ended_by="completed",
        app="claude-code",
    )
    assert record["id"] == "int-test"
    assert record["ended_by"] == "completed"
    assert record["app"] == "claude-code"
    assert record["schema_version"] == 1

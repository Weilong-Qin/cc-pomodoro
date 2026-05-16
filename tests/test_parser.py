"""Unit tests for cc_pomodoro.parser — /pomodoro prefix command parsing.

Tests cover all command variants, edge cases, and whitespace handling.
"""

from __future__ import annotations

from cc_pomodoro.parser import parse_pomodoro_command


# -- No prefix ----------------------------------------------------------------

def test_no_prefix() -> None:
    """Plain text with no /pomodoro prefix returns command=None."""
    result = parse_pomodoro_command("fix the auth bug")
    assert result == {"command": None, "duration": None, "text": None}


def test_no_prefix_with_leading_whitespace() -> None:
    result = parse_pomodoro_command("  hello world")
    assert result == {"command": None, "duration": None, "text": None}


def test_empty_string() -> None:
    result = parse_pomodoro_command("")
    assert result == {"command": None, "duration": None, "text": None}


def test_whitespace_only() -> None:
    result = parse_pomodoro_command("   ")
    assert result == {"command": None, "duration": None, "text": None}


# -- Bare /pomodoro -----------------------------------------------------------

def test_bare_pomodoro() -> None:
    """/pomodoro with no sub-command returns command=None."""
    result = parse_pomodoro_command("/pomodoro")
    assert result == {"command": None, "duration": None, "text": None}


def test_bare_pomodoro_trailing_space() -> None:
    result = parse_pomodoro_command("/pomodoro   ")
    assert result == {"command": None, "duration": None, "text": None}


# -- /pomodoro start ----------------------------------------------------------

def test_start_with_duration_and_text() -> None:
    result = parse_pomodoro_command("/pomodoro start 25 fix the auth bug")
    assert result["command"] == "start"
    assert result["duration"] == 25
    assert result["text"] == "fix the auth bug"


def test_start_without_duration() -> None:
    result = parse_pomodoro_command("/pomodoro start fix the auth bug")
    assert result["command"] == "start"
    assert result["duration"] is None
    assert result["text"] == "fix the auth bug"


def test_start_no_text() -> None:
    result = parse_pomodoro_command("/pomodoro start")
    assert result["command"] == "start"
    assert result["duration"] is None
    assert result["text"] is None


def test_start_only_duration() -> None:
    result = parse_pomodoro_command("/pomodoro start 25")
    assert result["command"] == "start"
    assert result["duration"] == 25
    assert result["text"] is None


def test_start_zero_duration_is_text() -> None:
    """Duration must be > 0; 0 is treated as text."""
    result = parse_pomodoro_command("/pomodoro start 0 hello")
    assert result["command"] == "start"
    assert result["duration"] is None
    assert result["text"] == "0 hello"


def test_start_negative_number_is_text() -> None:
    result = parse_pomodoro_command("/pomodoro start -5 hello")
    assert result["command"] == "start"
    assert result["duration"] is None
    assert result["text"] == "-5 hello"


def test_start_with_leading_whitespace() -> None:
    result = parse_pomodoro_command("  /pomodoro start 30  test message  ")
    assert result["command"] == "start"
    assert result["duration"] == 30
    assert result["text"] == "test message"


def test_start_mixed_case_command() -> None:
    """Command token is case-insensitive."""
    result = parse_pomodoro_command("/Pomodoro Start 15 my task")
    assert result["command"] == "start"
    assert result["duration"] == 15
    assert result["text"] == "my task"


# -- /pomodoro stop -----------------------------------------------------------

def test_stop() -> None:
    result = parse_pomodoro_command("/pomodoro stop")
    assert result["command"] == "stop"
    assert result["duration"] is None
    assert result["text"] is None


def test_stop_with_extra_args() -> None:
    """Extra text after 'stop' is preserved as text."""
    result = parse_pomodoro_command("/pomodoro stop now")
    assert result["command"] == "stop"
    assert result["text"] == "now"


# -- /pomodoro status ---------------------------------------------------------

def test_status() -> None:
    result = parse_pomodoro_command("/pomodoro status")
    assert result["command"] == "status"
    assert result["duration"] is None
    assert result["text"] is None


def test_status_with_args() -> None:
    result = parse_pomodoro_command("/pomodoro status verbose")
    assert result["command"] == "status"
    assert result["text"] == "verbose"


# -- /pomodoro stats ----------------------------------------------------------

def test_stats() -> None:
    result = parse_pomodoro_command("/pomodoro stats")
    assert result["command"] == "stats"
    assert result["text"] is None


def test_stats_with_json_flag() -> None:
    result = parse_pomodoro_command("/pomodoro stats --json")
    assert result["command"] == "stats"
    assert result["text"] == "--json"


# -- /pomodoro config ---------------------------------------------------------

def test_config_set() -> None:
    result = parse_pomodoro_command("/pomodoro config set duration 25")
    assert result["command"] == "config"
    assert result["text"] == "set duration 25"


def test_config_show() -> None:
    result = parse_pomodoro_command("/pomodoro config")
    assert result["command"] == "config"
    assert result["text"] is None


def test_config_set_bool() -> None:
    result = parse_pomodoro_command("/pomodoro config set auto_start false")
    assert result["command"] == "config"
    assert result["text"] == "set auto_start false"


# -- Edge cases ---------------------------------------------------------------

def test_pomodoro_like_prefix_not_matched() -> None:
    """Similar prefixes (e.g. /pomodoro-helper) must not match."""
    result = parse_pomodoro_command("/pomodoro-helper start")
    assert result["command"] is None


def test_pomodoro_with_newlines() -> None:
    result = parse_pomodoro_command("/pomodoro start\n25\ntask")
    assert result["command"] == "start"
    # split() handles newlines as whitespace
    assert result["duration"] == 25
    assert result["text"] == "task"

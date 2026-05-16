"""Tests for cc_pomodoro.timer — argument parsing and timer lifecycle.

These tests validate argument parsing and the main() lifecycle with
mocked time, state, and notification dependencies.
"""

from __future__ import annotations

import signal
from unittest import mock

import pytest

from cc_pomodoro.timer import parse_args


# -- parse_args tests ---------------------------------------------------------

class TestParseArgs:
    def test_all_required(self) -> None:
        args = parse_args(["--duration", "25", "--session-id", "abc", "--app", "claude-code"])
        assert args.duration == 25
        assert args.session_id == "abc"
        assert args.app == "claude-code"

    def test_duration_as_int(self) -> None:
        args = parse_args(["--duration", "50", "--session-id", "x", "--app", "codex-cli"])
        assert args.duration == 50

    def test_missing_duration(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--session-id", "abc", "--app", "claude-code"])

    def test_missing_session_id(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--duration", "25", "--app", "claude-code"])

    def test_missing_app(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--duration", "25", "--session-id", "abc"])


# -- main() lifecycle tests ---------------------------------------------------

def _make_state(
    active: bool = True,
    session_id: str = "sess-1",
    started_at: str = "2026-05-16T10:00:00+00:00",
    **kwargs: object,
) -> dict:
    state = {
        "active": active,
        "session_id": session_id,
        "started_at": started_at,
        "end_at": "2026-05-16T10:50:00+00:00",
        "duration": 50,
        "app": "claude-code",
    }
    state.update(kwargs)
    return state


def _timer_main() -> None:
    """Call timer.main() with controlled sys.argv."""
    from cc_pomodoro.timer import main as _main

    _main()


def test_main_completed() -> None:
    """Timer runs to completion naturally (no interruption)."""
    # monotonic sequence:
    #   call 1: end_time calc  -> return 0,   end_time = 3000
    #   call 2: while check    -> return 0,   enters loop
    #   call 3: remaining      -> return 0,   remaining = 3000, sleep(1.0)
    #   call 4: while check    -> return 3001, loop exits (3001 >= 3000)
    mono_vals = [0, 0, 0, 3001]

    with (
        mock.patch("cc_pomodoro.timer.get_state", return_value=_make_state()),
        mock.patch("cc_pomodoro.timer.end_session") as mock_end,
        mock.patch("cc_pomodoro.timer.notify") as mock_notify,
        mock.patch("cc_pomodoro.timer.append_session"),
        mock.patch("cc_pomodoro.timer.make_record", return_value={"id": "sess-1"}),
        mock.patch("cc_pomodoro.timer.time.monotonic", side_effect=mono_vals),
        mock.patch("cc_pomodoro.timer.time.sleep"),
        mock.patch("sys.argv", ["timer", "--duration", "50", "--session-id", "sess-1", "--app", "claude-code"]),
    ):
        _timer_main()

        mock_end.assert_called_once()
        mock_notify.assert_called_once()


def test_main_keyboard_interrupt() -> None:
    """Timer interrupted via KeyboardInterrupt inside time.sleep()."""
    mono_vals = [0, 0, 0, 3001]

    def _sleep_side_effect(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt()

    with (
        mock.patch("cc_pomodoro.timer.get_state", return_value=_make_state()),
        mock.patch("cc_pomodoro.timer.end_session") as mock_end,
        mock.patch("cc_pomodoro.timer.notify") as mock_notify,
        mock.patch("cc_pomodoro.timer.append_session"),
        mock.patch("cc_pomodoro.timer.make_record", return_value={"id": "sess-1"}),
        mock.patch("cc_pomodoro.timer.time.monotonic", side_effect=mono_vals),
        mock.patch("cc_pomodoro.timer.time.sleep", side_effect=_sleep_side_effect),
        mock.patch("sys.argv", ["timer", "--duration", "50", "--session-id", "sess-1", "--app", "claude-code"]),
    ):
        _timer_main()

        # Should end the session (process_killed)
        mock_end.assert_called_once()
        # Should NOT notify (interrupted, not completed)
        mock_notify.assert_not_called()


def test_main_double_end_detection() -> None:
    """Session already ended externally (e.g. /pomodoro stop) — state.active is False."""
    mono_vals = [0, 0, 0, 3001]
    state = _make_state(active=False)

    with (
        mock.patch("cc_pomodoro.timer.get_state", return_value=state),
        mock.patch("cc_pomodoro.timer.end_session") as mock_end,
        mock.patch("cc_pomodoro.timer.notify") as mock_notify,
        mock.patch("cc_pomodoro.timer.append_session"),
        mock.patch("cc_pomodoro.timer.make_record", return_value={"id": "sess-1"}),
        mock.patch("cc_pomodoro.timer.time.monotonic", side_effect=mono_vals),
        mock.patch("cc_pomodoro.timer.time.sleep"),
        mock.patch("sys.argv", ["timer", "--duration", "50", "--session-id", "sess-1", "--app", "claude-code"]),
    ):
        _timer_main()

        # end_session should NOT be called again (already ended externally)
        mock_end.assert_not_called()
        mock_notify.assert_not_called()


def test_main_session_replaced() -> None:
    """Session was replaced by a new one — timer exits silently without writing a record."""
    mono_vals = [0, 0, 0, 3001]
    state = _make_state(session_id="new-session", active=True)

    with (
        mock.patch("cc_pomodoro.timer.get_state", return_value=state),
        mock.patch("cc_pomodoro.timer.end_session") as mock_end,
        mock.patch("cc_pomodoro.timer.notify") as mock_notify,
        mock.patch("cc_pomodoro.timer.append_session") as mock_append,
        mock.patch("cc_pomodoro.timer.make_record"),
        mock.patch("cc_pomodoro.timer.time.monotonic", side_effect=mono_vals),
        mock.patch("cc_pomodoro.timer.time.sleep"),
        mock.patch("sys.argv", ["timer", "--duration", "50", "--session-id", "old-session", "--app", "claude-code"]),
    ):
        with pytest.raises(SystemExit):
            _timer_main()

        # Timer should exit without writing anything
        mock_end.assert_not_called()
        mock_notify.assert_not_called()
        mock_append.assert_not_called()


def test_main_sigterm() -> None:
    """Timer interrupted via SIGTERM signal before natural completion."""
    mono_vals = [0, 0, 0, 3001]

    # Patch signal.signal to capture the handler, then trigger it via side effect
    captured_handler = [None]

    def _capture_signal(signum: int, handler: object) -> None:
        captured_handler[0] = handler

    # Set interrupted=True via the signal handler before the loop exits
    with (
        mock.patch("cc_pomodoro.timer.get_state", return_value=_make_state()),
        mock.patch("cc_pomodoro.timer.end_session") as mock_end,
        mock.patch("cc_pomodoro.timer.notify") as mock_notify,
        mock.patch("cc_pomodoro.timer.append_session"),
        mock.patch("cc_pomodoro.timer.make_record", return_value={"id": "sess-1"}),
        mock.patch("cc_pomodoro.timer.time.monotonic", side_effect=mono_vals),
        mock.patch("cc_pomodoro.timer.signal.signal", _capture_signal),
        mock.patch("sys.argv", ["timer", "--duration", "50", "--session-id", "sess-1", "--app", "claude-code"]),
    ):
        # Make time.sleep trigger the signal handler
        def _sleep_then_signal(duration: float) -> None:
            if captured_handler[0] is not None:
                captured_handler[0](signal.SIGTERM, None)  # type: ignore[misc]

        with mock.patch("cc_pomodoro.timer.time.sleep", side_effect=_sleep_then_signal):
            _timer_main()

        # For process_killed: end_session called, notify NOT called
        mock_end.assert_called_once()
        mock_notify.assert_not_called()


def test_main_no_started_at() -> None:
    """Timer handles missing/empty started_at gracefully (uses planned duration)."""
    mono_vals = [0, 0, 0, 3001]
    state = _make_state(started_at="")

    with (
        mock.patch("cc_pomodoro.timer.get_state", return_value=state),
        mock.patch("cc_pomodoro.timer.end_session") as mock_end,
        mock.patch("cc_pomodoro.timer.notify") as mock_notify,
        mock.patch("cc_pomodoro.timer.append_session"),
        mock.patch("cc_pomodoro.timer.make_record", return_value={"id": "sess-1"}),
        mock.patch("cc_pomodoro.timer.time.monotonic", side_effect=mono_vals),
        mock.patch("cc_pomodoro.timer.time.sleep"),
        mock.patch("sys.argv", ["timer", "--duration", "50", "--session-id", "sess-1", "--app", "claude-code"]),
    ):
        _timer_main()

        # Should not crash; should complete normally
        mock_end.assert_called_once()
        mock_notify.assert_called_once()

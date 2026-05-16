"""Unit tests for cc_pomodoro.hooks -- hook decision logic.

All side-effectful dependencies (state, config, subprocess) are mocked so
that tests are fast, deterministic, and require no filesystem setup.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from cc_pomodoro.hooks import (
    handle_pre_tool_use,
    handle_stop,
    handle_user_prompt_submit,
    main as hooks_main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_state(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Mock the *state* module inside ``cc_pomodoro.hooks``.

    Returns a ``Mock`` with pre-configured defaults (session inactive).
    Callers override ``.is_active``, ``.get_remaining_seconds`` etc. as
    needed for each test case.
    """
    m = mock.MagicMock()
    m.is_active.return_value = False
    m.get_remaining_seconds.return_value = 0
    m.get_state.return_value = {
        "active": False,
        "session_id": None,
        "started_at": None,
        "end_at": None,
        "duration": 0,
        "app": None,
    }
    m.start_session.return_value = "mock-session-id"
    monkeypatch.setattr("cc_pomodoro.hooks.is_active", m.is_active)
    monkeypatch.setattr("cc_pomodoro.hooks.get_remaining_seconds", m.get_remaining_seconds)
    monkeypatch.setattr("cc_pomodoro.hooks.get_state", m.get_state)
    monkeypatch.setattr("cc_pomodoro.hooks.start_session", m.start_session)
    monkeypatch.setattr("cc_pomodoro.hooks.end_session", m.end_session)
    # _write_state is called by handle_stop; mock it to avoid real filesystem writes
    monkeypatch.setattr("cc_pomodoro.hooks._write_state", m._write_state)
    return m


@pytest.fixture
def mock_config(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Mock config with default values."""
    m = mock.MagicMock()
    m.get_config.return_value = {
        "duration": 50,
        "auto_start": True,
        "auto_start_apps": ["claude-code", "codex-cli"],
        "notify_on_complete": True,
        "notify_sound": True,
    }
    monkeypatch.setattr("cc_pomodoro.hooks.config.get_config", m.get_config)
    monkeypatch.setattr("cc_pomodoro.hooks.config.set_config", m.set_config)
    return m


@pytest.fixture
def mock_spawn(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Prevent background subprocesses from actually spawning."""
    m = mock.MagicMock()
    monkeypatch.setattr("cc_pomodoro.hooks._spawn_timer", m)
    return m


# ===== handle_user_prompt_submit ===========================================


class TestHandleUserPromptSubmit:
    """Tests for the UserPromptSubmit handler."""

    # -- /pomodoro start ----------------------------------------------------

    def test_start_with_duration(self, mock_state, mock_config, mock_spawn):
        event = {"prompt": "/pomodoro start 25 fix the auth bug", "app": "claude-code"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "continue"
        mock_state.start_session.assert_called_once_with(25, "claude-code")
        mock_spawn.assert_called_once()

    def test_start_uses_default_duration(self, mock_state, mock_config, mock_spawn):
        event = {"prompt": "/pomodoro start fix the auth bug", "app": "claude-code"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "continue"
        # Default is 50 from config
        mock_state.start_session.assert_called_once_with(50, "claude-code")
        mock_spawn.assert_called_once()

    def test_start_overrides_active_session(self, mock_state, mock_config, mock_spawn):
        """Starting a new session while one is active should override."""
        mock_state.is_active.return_value = True
        mock_state.get_remaining_seconds.return_value = 600
        event = {"prompt": "/pomodoro start 15 new task", "app": "claude-code"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "continue"
        mock_state.start_session.assert_called_once_with(15, "claude-code")
        mock_spawn.assert_called_once()

    # -- /pomodoro stop -----------------------------------------------------

    def test_stop_active(self, mock_state, mock_config):
        mock_state.is_active.return_value = True
        event = {"prompt": "/pomodoro stop"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"
        mock_state.end_session.assert_called_once()

    def test_stop_inactive(self, mock_state, mock_config):
        mock_state.is_active.return_value = False
        event = {"prompt": "/pomodoro stop"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"
        mock_state.end_session.assert_not_called()

    # -- /pomodoro status ---------------------------------------------------

    def test_status_active(self, mock_state, mock_config):
        mock_state.is_active.return_value = True
        mock_state.get_remaining_seconds.return_value = 1234
        event = {"prompt": "/pomodoro status"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"

    def test_status_inactive(self, mock_state, mock_config):
        mock_state.is_active.return_value = False
        event = {"prompt": "/pomodoro status"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"

    # -- /pomodoro stats ----------------------------------------------------

    def test_stats(self, mock_state, mock_config):
        event = {"prompt": "/pomodoro stats"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"

    def test_stats_with_json_flag(self, mock_state, mock_config):
        event = {"prompt": "/pomodoro stats --json"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"

    # -- /pomodoro config ---------------------------------------------------

    def test_config_show(self, mock_state, mock_config):
        event = {"prompt": "/pomodoro config"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"

    def test_config_set(self, mock_state, mock_config):
        event = {"prompt": "/pomodoro config set duration 30"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"
        mock_config.set_config.assert_called_once_with("duration", 30)

    def test_config_set_bool(self, mock_state, mock_config):
        event = {"prompt": "/pomodoro config set auto_start false"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"
        mock_config.set_config.assert_called_once_with("auto_start", False)

    # -- Active session (no /pomodoro prefix) -------------------------------

    def test_active_blocks_prompt(self, mock_state, mock_config):
        mock_state.is_active.return_value = True
        mock_state.get_remaining_seconds.return_value = 1500
        event = {"prompt": "fix the auth bug"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "block"
        assert "Pomodoro" in result.get("reason", "")

    # -- Auto-start (no /pomodoro prefix, inactive) ------------------------

    def test_auto_start_inactive(self, mock_state, mock_config, mock_spawn):
        mock_state.is_active.return_value = False
        event = {"prompt": "fix the auth bug", "app": "claude-code"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "continue"
        mock_state.start_session.assert_called_once_with(50, "claude-code")
        mock_spawn.assert_called_once()

    def test_auto_start_no_app_fallback(self, mock_state, mock_config, mock_spawn):
        """When event has no 'app' field, default to claude-code."""
        mock_state.is_active.return_value = False
        event = {"prompt": "hello"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "continue"
        mock_state.start_session.assert_called_once_with(50, "claude-code")

    # -- Auto-start disabled ------------------------------------------------

    def test_auto_start_off(self, mock_state, mock_config):
        mock_state.is_active.return_value = False
        mock_config.get_config.return_value = {
            "duration": 50,
            "auto_start": False,
        }
        event = {"prompt": "fix the auth bug"}
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "continue"
        mock_state.start_session.assert_not_called()

    # -- Event with no prompt field -----------------------------------------

    def test_empty_prompt(self, mock_state, mock_config):
        """Empty prompt should not crash - handled as no prefix."""
        event = {"prompt": ""}
        mock_state.is_active.return_value = False
        result = handle_user_prompt_submit(event)
        assert result["decision"] == "continue"


# ===== handle_pre_tool_use ==================================================


class TestHandlePreToolUse:
    """Tests for the PreToolUse handler."""

    def test_active_allows(self, mock_state):
        mock_state.is_active.return_value = True
        event = {"tool": {"name": "bash"}}
        result = handle_pre_tool_use(event)
        assert result == {"permissionDecision": "allow"}

    def test_inactive_empty(self, mock_state):
        mock_state.is_active.return_value = False
        event = {"tool": {"name": "bash"}}
        result = handle_pre_tool_use(event)
        assert result == {}

    def test_empty_event_active(self, mock_state):
        mock_state.is_active.return_value = True
        result = handle_pre_tool_use({})
        assert result == {"permissionDecision": "allow"}

    def test_empty_event_inactive(self, mock_state):
        mock_state.is_active.return_value = False
        result = handle_pre_tool_use({})
        assert result == {}


# ===== handle_stop ==========================================================


class TestHandleStop:
    """Tests for the Stop hook handler."""

    @staticmethod
    def _make_state(active=False, stop_hook_blocked=False):
        state = {
            "active": active,
            "session_id": "s1" if active else None,
            "started_at": None,
            "end_at": None,
            "duration": 25 if active else 0,
            "app": "claude-code" if active else None,
        }
        if stop_hook_blocked:
            state["_stop_hook_blocked"] = True
        return state

    def test_active_blocks(self, mock_state):
        mock_state.is_active.return_value = True
        mock_state.get_state.return_value = self._make_state(active=True)
        event = {"turn": 1}
        result = handle_stop(event)
        assert result["decision"] == "block"

    def test_active_already_blocked_returns_empty(self, mock_state):
        """Once stop is blocked for a turn, subsequent calls let through."""
        mock_state.is_active.return_value = True
        mock_state.get_state.return_value = self._make_state(
            active=True, stop_hook_blocked=True
        )
        event = {"turn": 1}
        result = handle_stop(event)
        assert result == {}

    def test_inactive_empty(self, mock_state):
        mock_state.is_active.return_value = False
        mock_state.get_state.return_value = self._make_state(active=False)
        event = {"turn": 1}
        result = handle_stop(event)
        assert result == {}

    def test_inactive_clears_stale_flag(self, mock_state, monkeypatch):
        """When session is inactive, any stale _stop_hook_blocked is removed."""
        mock_state.is_active.return_value = False
        stale_state = self._make_state(active=False, stop_hook_blocked=True)
        mock_state.get_state.return_value = stale_state

        write_mock = mock.MagicMock()
        monkeypatch.setattr("cc_pomodoro.hooks._write_state", write_mock)

        event = {"turn": 1}
        result = handle_stop(event)
        assert result == {}
        # _write_state should have been called with the flag removed
        written = write_mock.call_args[0][0]
        assert "_stop_hook_blocked" not in written

    def test_codex_suppresses_output(self, mock_state, monkeypatch):
        """Codex CLI stop hook should include suppressOutput."""
        monkeypatch.setenv("CC_POMODORO_APP", "codex-cli")
        mock_state.is_active.return_value = True
        mock_state.get_state.return_value = self._make_state(active=True)
        event = {"turn": 1}
        result = handle_stop(event)
        assert result["decision"] == "block"
        assert result.get("suppressOutput") is True

    def test_claude_no_suppress(self, mock_state, monkeypatch):
        """Claude Code stop hook should NOT include suppressOutput."""
        monkeypatch.delenv("CC_POMODORO_APP", raising=False)
        mock_state.is_active.return_value = True
        mock_state.get_state.return_value = self._make_state(active=True)
        event = {"turn": 1}
        result = handle_stop(event)
        assert result["decision"] == "block"
        assert "suppressOutput" not in result


# ===== main() entry point ===================================================


class TestMainEntryPoint:
    """Tests for ``hooks.main()`` -- stdin/stdout dispatch."""

    def test_user_prompt_submit_roundtrip(
            self, mock_state, mock_config, mock_spawn, monkeypatch, capsys):
        """Simulate full stdin -> stdout roundtrip."""
        mock_state.is_active.return_value = False
        mock_stdin = mock.MagicMock()
        mock_stdin.read.return_value = json.dumps(
            {"prompt": "hello world", "app": "claude-code"}
        )
        monkeypatch.setattr("sys.argv", ["hooks.py", "user_prompt_submit"])
        monkeypatch.setattr("sys.stdin", mock_stdin)
        hooks_main()
        out, _ = capsys.readouterr()
        decision = json.loads(out.strip())
        assert decision["decision"] == "continue"

    def test_unknown_event(self, monkeypatch, capsys):
        """Unknown event name returns empty decision (no intervention)."""
        mock_stdin = mock.MagicMock()
        mock_stdin.read.return_value = "{}"
        monkeypatch.setattr("sys.argv", ["hooks.py", "unknown_event"])
        monkeypatch.setattr("sys.stdin", mock_stdin)
        with pytest.raises(SystemExit):
            hooks_main()
        out, _ = capsys.readouterr()
        assert json.loads(out.strip()) == {}

    def test_invalid_json_input(self, monkeypatch, capsys):
        """Malformed JSON input should not crash -- returns empty decision."""
        mock_stdin = mock.MagicMock()
        mock_stdin.read.return_value = "not json"
        monkeypatch.setattr("sys.argv", ["hooks.py", "user_prompt_submit"])
        monkeypatch.setattr("sys.stdin", mock_stdin)
        with pytest.raises(SystemExit):
            hooks_main()
        out, _ = capsys.readouterr()
        assert json.loads(out.strip()) == {}

    def test_no_stdin_input(self, monkeypatch, capsys):
        """Empty stdin returns empty decision."""
        mock_stdin = mock.MagicMock()
        mock_stdin.read.return_value = ""
        monkeypatch.setattr("sys.argv", ["hooks.py", "user_prompt_submit"])
        monkeypatch.setattr("sys.stdin", mock_stdin)
        with pytest.raises(SystemExit):
            hooks_main()
        out, _ = capsys.readouterr()
        assert json.loads(out.strip()) == {}

    def test_handler_exception(self, mock_state, monkeypatch, capsys):
        """Handler exceptions should be caught, returning empty decision."""
        mock_state.is_active.side_effect = RuntimeError("boom")
        mock_stdin = mock.MagicMock()
        mock_stdin.read.return_value = "{}"
        monkeypatch.setattr("sys.argv", ["hooks.py", "pre_tool_use"])
        monkeypatch.setattr("sys.stdin", mock_stdin)
        with pytest.raises(SystemExit):
            hooks_main()
        out, _ = capsys.readouterr()
        assert json.loads(out.strip()) == {}

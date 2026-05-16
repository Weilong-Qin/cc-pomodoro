"""Hook decision logic for Claude Code and Codex CLI hook events.

This module provides one function per hook event type.  Each function
receives the event *dict* (parsed from the JSON the CLI sends on stdin)
and returns a decision *dict* that the CLI interprets.

Module entry point
------------------
The module can be invoked directly so that shell scripts stay razor-thin::

    echo '<event-json>' | python -m cc_pomodoro.hooks user_prompt_submit
    echo '<event-json>' | python -m cc_pomodoro.hooks pre_tool_use
    echo '<event-json>' | python -m cc_pomodoro.hooks stop

It reads a single JSON line from stdin, dispatches to the relevant
handler, and writes the decision JSON to stdout.

Error handling
--------------
Any exception raised by a handler is caught and logged to stderr.  The
process exits with an empty JSON object ``{}`` on stdout so that the CLI
falls back to default (non‑intervention) behaviour.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from cc_pomodoro import config
from cc_pomodoro.constants import STATE_FILE
from cc_pomodoro.parser import parse_pomodoro_command
from cc_pomodoro.state import (
    end_session,
    get_remaining_seconds,
    get_state,
    is_active,
    start_session,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STOP_HOOK_KEY = "_stop_hook_blocked"


def _is_codex() -> bool:
    """Return ``True`` when the caller is Codex CLI (set via env var)."""
    return os.environ.get("CC_POMODORO_APP", "").lower() == "codex-cli"


def _write_state(state: dict[str, Any]) -> None:
    config._ensure_config_dir()
    config._atomic_write(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def _spawn_timer(duration: int, session_id: str, app: str) -> None:
    """Launch timer.py as a detached background process (non‑blocking)."""
    cmd = [
        sys.executable,
        "-m",
        "cc_pomodoro.timer",
        "--duration",
        str(duration),
        "--session-id",
        session_id,
        "--app",
        app,
    ]
    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **popen_kwargs)


def _format_remaining(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _eprint(*args: Any, **kwargs: Any) -> None:
    """Print to stderr so status messages reach the user's terminal."""
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_user_prompt_submit(event: dict) -> dict:
    """Decide how to handle a new user prompt.

    Logic — in priority order:

    1. If the prompt starts with ``/pomodoro``, parse and execute the
       command directly (start / stop / status / stats / config), then
       return ``block`` so the command is **not** forwarded to the LLM.
       Exception: ``/pomodoro start`` returns ``continue`` so the prompt
       (with prefix) is passed through.

    2. If a pomodoro session is currently **active**, block the prompt
       and tell the user how much time remains.

    3. If ``auto_start`` is enabled in config and **no** session is
       running, automatically begin a pomodoro session and let the
       prompt through (``continue``).

    4. Otherwise (auto_start is off, no session) — let the prompt
       through with no intervention.
    """
    prompt = event.get("prompt", "").strip()
    parsed = parse_pomodoro_command(prompt)
    command = parsed["command"]

    active = is_active()
    cfg = config.get_config()

    # -- /pomodoro meta‑commands ------------------------------------------
    if command is not None:
        return _handle_pomodoro_command(command, parsed, event, cfg)

    # -- Plain prompt (no /pomodoro prefix) --------------------------------
    if active:
        remaining = get_remaining_seconds()
        return {
            "decision": "block",
            "reason": (
                f"Pomodoro 进行中，还剩 {_format_remaining(remaining)}。"
                f" /pomodoro stop 可提前结束"
            ),
        }

    if cfg.get("auto_start", False):
        app = event.get("app", "claude-code")
        auto_apps = cfg.get("auto_start_apps", ["claude-code", "codex-cli"])
        if app in auto_apps:
            duration = cfg.get("duration", 50)
            session_id = start_session(duration, app)
            _spawn_timer(duration, session_id, app)
            _eprint(f"[cc-pomodoro] 自动开始番茄钟 · {duration} 分钟")
            return {"decision": "continue"}
        # App not in auto_start_apps — let prompt through without session
        return {"decision": "continue"}

    return {"decision": "continue"}


def _handle_pomodoro_command(
    command: str,
    parsed: dict[str, Any],
    event: dict,
    cfg: dict[str, Any],
) -> dict:
    """Dispatch a parsed ``/pomodoro <command>`` to the right action."""
    # -- stop ------------------------------------------------------------
    if command == "stop":
        if is_active():
            end_session()
            _eprint("[cc-pomodoro] 番茄钟已提前结束")
        else:
            _eprint("[cc-pomodoro] 没有进行中的番茄钟")
        return {
            "decision": "block",
            "reason": "Pomodoro command processed — not forwarded to AI",
        }

    # -- status ----------------------------------------------------------
    if command == "status":
        if is_active():
            remaining = get_remaining_seconds()
            _eprint(f"[POMODORO] 剩余 {_format_remaining(remaining)}")
        else:
            _eprint("[POMODORO] 没有进行中的番茄钟")
        return {
            "decision": "block",
            "reason": "Pomodoro command processed — not forwarded to AI",
        }

    # -- stats -----------------------------------------------------------
    if command == "stats":
        _print_stats()
        return {
            "decision": "block",
            "reason": "Pomodoro command processed — not forwarded to AI",
        }

    # -- config ----------------------------------------------------------
    if command == "config":
        _handle_config_command(parsed.get("text") or "")
        return {
            "decision": "block",
            "reason": "Pomodoro command processed — not forwarded to AI",
        }

    # -- start -----------------------------------------------------------
    if command == "start":
        duration = parsed.get("duration") or cfg.get("duration", 50)
        app = event.get("app", "claude-code")

        if is_active():
            remaining = get_remaining_seconds()
            _eprint(
                f"[cc-pomodoro] 警告: 已有进行中的番茄钟"
                f"（还剩 {_format_remaining(remaining)}），将启动新周期覆盖旧会话"
            )

        session_id = start_session(duration, app)
        _spawn_timer(duration, session_id, app)
        _eprint(f"[cc-pomodoro] 番茄钟已启动 · {duration} 分钟")

        # Continue so the prompt (with /pomodoro prefix) reaches the LLM
        return {"decision": "continue"}

    # Unknown /pomodoro sub‑command — let through (no intervention)
    return {"decision": "continue"}


def _print_stats() -> None:
    """Print session statistics to stderr."""
    from cc_pomodoro.stats import get_stats, read_sessions

    sessions = read_sessions()
    if not sessions:
        _eprint("[cc-pomodoro] 暂无专注记录")
        return

    stats = get_stats()
    _eprint("=== cc-pomodoro 统计 ===")
    _eprint(f"今日专注: {stats['today_minutes']} 分钟")
    _eprint(f"本周专注: {stats['week_minutes']} 分钟")

    if stats["by_app"]:
        _eprint("按应用统计:")
        for app_name, minutes in sorted(stats["by_app"].items()):
            _eprint(f"  {app_name:<20s} {minutes} 分钟")

    if stats["recent_sessions"]:
        _eprint("最近 5 条记录:")
        for s in stats["recent_sessions"]:
            started = (s.get("started_at") or "")[:16]
            ended = (s.get("ended_at") or "")[:16]
            planned = s.get("duration_planned", "?")
            ended_by = s.get("ended_by", "?")
            app_name = s.get("app", "?")
            _eprint(
                f"  {started}  →  {ended}  "
                f"{planned}min  {ended_by:<14s}  {app_name}"
            )


def _handle_config_command(text: str) -> None:
    """Read or write configuration from a ``/pomodoro config`` invocation."""
    parts = text.split()
    if len(parts) >= 3 and parts[0] == "set":
        key = parts[1]
        raw_value = " ".join(parts[2:])
        # Parse the value into the appropriate Python type
        lower = raw_value.lower()
        if lower in ("true", "yes", "on", "1"):
            parsed_value: Any = True
        elif lower in ("false", "no", "off", "0"):
            parsed_value = False
        else:
            try:
                parsed_value = int(raw_value)
            except ValueError:
                try:
                    parsed_value = float(raw_value)
                except ValueError:
                    parsed_value = raw_value
        config.set_config(key, parsed_value)
        _eprint(f"[cc-pomodoro] 已设置 {key}={parsed_value}")
    else:
        # Print current config
        cfg = config.get_config()
        _eprint(json.dumps(cfg, indent=2, ensure_ascii=False))


def handle_pre_tool_use(event: dict) -> dict:
    """Decide whether an AI tool‑use request should be allowed.

    * During an active pomodoro: auto‑allow every tool call
      (no popup / no user prompt).
    * Otherwise: return empty dict — let the CLI apply its default policy.
    """
    if is_active():
        return {"permissionDecision": "allow"}
    return {}


def handle_stop(event: dict) -> dict:
    """Decide whether a turn completion should be shown.

    * During an active pomodoro: **block** the completion.  For Codex CLI
      this also suppresses the output (``suppressOutput: true``).
      A ``_stop_hook_blocked`` flag is written to ``state.json`` to
      prevent infinite re‑triggering within the same blocked turn.
    * Otherwise: return empty dict — let the completion go through.
    """
    if not is_active():
        # Clear any stale flag left over from a previous session
        state = get_state()
        if STOP_HOOK_KEY in state:
            state.pop(STOP_HOOK_KEY, None)
            _write_state(state)
        return {}

    state = get_state()

    # Already blocked once for this turn — let this one through to
    # avoid an infinite loop (the framework may re‑fire the hook).
    if state.get(STOP_HOOK_KEY):
        return {}

    # First block — write flag and return block
    state[STOP_HOOK_KEY] = True
    _write_state(state)

    result: dict[str, Any] = {
        "decision": "block",
        "reason": "Pomodoro active, continue working",
    }
    if _is_codex():
        result["suppressOutput"] = True
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "user_prompt_submit": handle_user_prompt_submit,
    "pre_tool_use": handle_pre_tool_use,
    "stop": handle_stop,
}


def main() -> None:
    """Entry point::

        python -m cc_pomodoro.hooks <event_name>

    Reads JSON from stdin, dispatches to the appropriate handler, and
    writes the decision JSON to stdout.
    """
    if len(sys.argv) < 2:
        _eprint("Usage: python -m cc_pomodoro.hooks <event_name>")
        _eprint(f"Available events: {', '.join(_HANDLERS)}")
        sys.exit(1)

    event_name = sys.argv[1]
    handler = _HANDLERS.get(event_name)

    if handler is None:
        _eprint(f"Unknown event: {event_name}")
        _eprint(f"Available events: {', '.join(_HANDLERS)}")
        # Return empty decision (no intervention) for unknown events
        print(json.dumps({}))
        sys.exit(0)

    raw = sys.stdin.read()
    if not raw.strip():
        _eprint("[cc-pomodoro] No input received on stdin")
        print(json.dumps({}))
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        _eprint(f"[cc-pomodoro] Invalid JSON input: {exc}")
        print(json.dumps({}))
        sys.exit(0)

    try:
        decision = handler(event)
        print(json.dumps(decision, ensure_ascii=False))
    except Exception as exc:
        _eprint(f"[cc-pomodoro] Error handling {event_name}: {exc}")
        # On error, fall back to no intervention
        print(json.dumps({}))
        sys.exit(0)


if __name__ == "__main__":
    main()

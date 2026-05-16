"""Parse /pomodoro prefixed commands from user prompts.

The parser carves user input into three buckets:
  - ``/pomodoro start [N] <text>`` — start a pomodoro session (optional duration in minutes)
  - ``/pomodoro stop | status | stats | config`` — meta-commands handled by hooks
  - plain text — no pomodoro command (passed through to the LLM)

Grammar::

    prompt        = "/pomodoro" command [args] | plain-text
    command       = "start" | "stop" | "status" | "stats" | "config"
    start-args    = [minutes] text
    minutes       = integer
"""

from __future__ import annotations

import re
from typing import Any


def parse_pomodoro_command(prompt: str) -> dict[str, Any]:
    """Inspect *prompt* for a leading ``/pomodoro`` prefix.

    Returns a dict with the following keys:

    **command**
        One of ``"start"``, ``"stop"``, ``"status"``, ``"stats"``, ``"config"``,
        or ``None`` when no ``/pomodoro`` prefix is present.
    **duration**
        ``int | None`` — parsed only for the ``start`` command when the first
        token after ``start`` is a positive integer.
    **text**
        ``str | None`` — the remainder of the prompt after stripping the command
        and optional duration.  For non-``start`` commands this is everything
        after the command token (e.g. ``"set duration 25"`` for ``/pomodoro
        config set duration 25``).

    Examples
    --------
    >>> parse_pomodoro_command("/pomodoro start 25 fix the auth bug")
    {'command': 'start', 'duration': 25, 'text': 'fix the auth bug'}

    >>> parse_pomodoro_command("/pomodoro start fix the auth bug")
    {'command': 'start', 'duration': None, 'text': 'fix the auth bug'}

    >>> parse_pomodoro_command("/pomodoro stop")
    {'command': 'stop', 'duration': None, 'text': None}

    >>> parse_pomodoro_command("/pomodoro status")
    {'command': 'status', 'duration': None, 'text': None}

    >>> parse_pomodoro_command("/pomodoro stats --json")
    {'command': 'stats', 'duration': None, 'text': '--json'}

    >>> parse_pomodoro_command("/pomodoro config set duration 25")
    {'command': 'config', 'duration': None, 'text': 'set duration 25'}

    >>> parse_pomodoro_command("fix the auth bug")
    {'command': None, 'duration': None, 'text': None}
    """
    stripped = prompt.strip()

    # Case-insensitive prefix check.
    # Must be exactly "/pomodoro" followed by space or end-of-string
    # (not e.g. "/pomodoro-helper").
    lower_stripped = stripped.lower()
    if not lower_stripped.startswith("/pomodoro"):
        return {"command": None, "duration": None, "text": None}

    after_prefix = lower_stripped[len("/pomodoro"):]
    if after_prefix and not after_prefix.startswith(" "):
        # "/pomodoro" is part of a longer token like "/pomodoro-helper"
        return {"command": None, "duration": None, "text": None}

    # Remove the "/pomodoro" prefix (case-insensitive) and strip
    rest = stripped[len("/pomodoro"):].strip()

    if not rest:
        # Bare "/pomodoro" with nothing after it — treat as no command
        return {"command": None, "duration": None, "text": None}

    parts = rest.split()
    command = parts[0].lower()

    if command == "start":
        remaining = parts[1:] if len(parts) > 1 else []
        duration: int | None = None
        text_parts: list[str] = []

        if remaining:
            # Try the first remaining token as a numeric duration
            try:
                candidate = int(remaining[0])
                if candidate > 0:
                    duration = candidate
                    text_parts = remaining[1:]
                else:
                    text_parts = remaining
            except ValueError:
                text_parts = remaining

        return {
            "command": command,
            "duration": duration,
            "text": " ".join(text_parts) if text_parts else None,
        }

    # Non-start commands: everything after the command token is text/args
    text = " ".join(parts[1:]) if len(parts) > 1 else None
    return {"command": command, "duration": None, "text": text}

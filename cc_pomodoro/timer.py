"""Background countdown timer process.

Usage:
    python -m cc_pomodoro.timer --duration 25 --session-id xxx --app claude-code

Spawns no output.  Sleeps for the given duration, then:
  - Shows an OS desktop notification
  - Ends the session in state.json
  - Appends a session record to sessions.jsonl

Handles SIGTERM / KeyboardInterrupt gracefully and detects if the session
was already ended externally (e.g. via ``/pomodoro stop``).
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any

from cc_pomodoro import config
from cc_pomodoro.notify import notify
from cc_pomodoro.state import end_session, get_state
from cc_pomodoro.stats import append_session, make_record


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cc-pomodoro-timer",
        description="Background pomodoro timer process.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Duration in minutes",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        required=True,
        help="Session UUID (matches state.json)",
    )
    parser.add_argument(
        "--app",
        type=str,
        required=True,
        help="Application name (e.g. claude-code)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    interrupted = False

    def _signal_handler(signum: int, frame: Any) -> None:
        nonlocal interrupted
        interrupted = True

    # Register SIGTERM handler (not available on all Windows Python builds)
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except (ValueError, AttributeError, OSError):
        pass

    try:
        end_time = time.monotonic() + args.duration * 60
        while time.monotonic() < end_time:
            if interrupted:
                break
            remaining = end_time - time.monotonic()
            time.sleep(min(1.0, remaining))
    except KeyboardInterrupt:
        interrupted = True

    # Snapshot state before any mutation
    state = get_state()
    started_at: str = state.get("started_at") or ""
    current_session_id: str | None = state.get("session_id")

    # Session was replaced by a different one -- our work is done
    if current_session_id != args.session_id:
        sys.exit(0)

    already_ended: bool = not state.get("active", False)

    if already_ended:
        ended_by = "user_stop"
    else:
        if interrupted:
            ended_by = "process_killed"
        else:
            ended_by = "completed"
            cfg = config.get_config()
            if cfg.get("notify_on_complete", True):
                notify("Pomodoro 完成", f"{args.duration} 分钟专注结束")
            if cfg.get("notify_sound", True):
                # Terminal bell (cross-platform audible alert)
                print("\a", end="", file=sys.stderr, flush=True)
        state = end_session()

    # Calculate actual duration from the started_at timestamp
    now = datetime.now(timezone.utc)
    duration_actual = 0
    if started_at:
        try:
            started_dt = datetime.fromisoformat(started_at)
            elapsed = (now - started_dt).total_seconds()
            duration_actual = max(0, int(elapsed / 60))
        except (ValueError, TypeError):
            duration_actual = args.duration

    record = make_record(
        session_id=args.session_id,
        started_at=started_at,
        ended_at=now.isoformat(),
        duration_planned=args.duration,
        duration_actual=duration_actual,
        ended_by=ended_by,
        app=args.app,
    )
    append_session(record)


if __name__ == "__main__":
    main()

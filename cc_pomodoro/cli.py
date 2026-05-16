"""User-facing CLI for cc-pomodoro.

Usage:
    cc-pomodoro start [--duration MINUTES] [--app NAME] [PROMPT_TEXT]
    cc-pomodoro stop
    cc-pomodoro status
    cc-pomodoro stats [--json]
    cc-pomodoro config [set KEY VALUE]
    cc-pomodoro hooks init [--app claude-code|codex-cli]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from cc_pomodoro import config, state
from cc_pomodoro.stats import get_stats, read_sessions


def _parse_config_value(value: str) -> Any:
    """Parse a CLI string value into the appropriate Python type."""
    lower = value.lower()
    if lower in ("true", "yes", "on", "1"):
        return True
    if lower in ("false", "no", "off", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _format_dt(iso_str: str) -> str:
    """Format an ISO-8601 timestamp to a compact ``MM-DD HH:MM`` string."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_str[:16]


def _spawn_timer(duration: int, session_id: str, app: str) -> None:
    """Launch timer.py as a detached background process."""
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


# -- Command implementations -------------------------------------------------

def cmd_start(args: argparse.Namespace) -> None:
    if state.is_active():
        remaining = state.get_remaining_seconds()
        m, s = divmod(remaining, 60)
        print(f"警告: 已有进行中的番茄钟（还剩 {m}:{s:02d}），将启动新周期覆盖旧会话")

    duration = args.duration if args.duration is not None else config.get("duration")
    app = args.app or "claude-code"
    session_id = state.start_session(duration, app)

    print(f"Pomodoro 已启动 · {duration} 分钟 · {app}")
    if args.prompt_text:
        print(args.prompt_text)

    _spawn_timer(duration, session_id, app)


def cmd_stop() -> None:
    if not state.is_active():
        print("没有进行中的番茄钟")
        return

    remaining = state.get_remaining_seconds()
    m, s = divmod(remaining, 60)

    try:
        answer = input(f"还剩 {m}:{s:02d}，确定结束？[y/N] ")
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer.lower() == "y":
        state.end_session()
        print("Pomodoro 已提前结束")
    else:
        print("继续专注")


def cmd_status() -> None:
    if not state.is_active():
        print("没有进行中的番茄钟")
        return

    remaining = state.get_remaining_seconds()
    s = state.get_state()
    m, sec = divmod(remaining, 60)
    duration = s.get("duration", "?")
    app = s.get("app", "?")

    print(f"\U0001f345 {m}:{sec:02d} · {app} ({duration}min)")


def cmd_stats(args: argparse.Namespace) -> None:
    sessions = read_sessions()
    if not sessions:
        print("暂无专注记录")
        return

    if args.json:
        for session in sessions:
            print(json.dumps(session, ensure_ascii=False))
        return

    stats = get_stats()

    print("=== cc-pomodoro 统计 ===")
    print(f"今日专注: {stats['today_minutes']} 分钟")
    print(f"本周专注: {stats['week_minutes']} 分钟")
    print()

    if stats["by_app"]:
        print("按应用统计:")
        for app_name, minutes in sorted(stats["by_app"].items()):
            print(f"  {app_name:<20s} {minutes} 分钟")
        print()

    if stats["recent_sessions"]:
        print("最近 5 条记录:")
        for s in stats["recent_sessions"]:
            started = _format_dt(s.get("started_at", ""))
            ended = _format_dt(s.get("ended_at", ""))
            planned = s.get("duration_planned", "?")
            ended_by = s.get("ended_by", "?")
            app_name = s.get("app", "?")
            print(
                f"  {started}  →  {ended}  "
                f"{planned}min  {ended_by:<14s}  {app_name}"
            )


def cmd_config(args: argparse.Namespace) -> None:
    if args.config_action == "set":
        if not args.key or not args.value:
            print("用法: cc-pomodoro config set <key> <value>", file=sys.stderr)
            sys.exit(1)
        value = _parse_config_value(args.value)
        config.set_config(args.key, value)
        print(json.dumps({args.key: value}, ensure_ascii=False))
    else:
        cfg = config.get_config()
        print(json.dumps(cfg, indent=2, ensure_ascii=False))


# -- Hooks init ---------------------------------------------------------------

def cmd_hooks_init(args: argparse.Namespace) -> None:
    """Print the boilerplate JSON snippet needed to wire up hook scripts.

    The user adds this snippet to their CLI config file:

    * **Claude Code**: ``~/.claude/settings.json`` → ``hooks`` section
    * **Codex CLI**: ``~/.codex/settings.json`` → ``hooks`` section

    The printed paths are absolute, pointing to the installed hook scripts.
    """
    app = args.app or "claude-code"

    # Locate the hooks directory inside the cc_pomodoro package.
    # This works for both editable installs (pip install -e .) and
    # regular site-package installs.
    package_root = Path(__file__).resolve().parent
    hooks_dir = package_root / "hooks" / app

    if not hooks_dir.is_dir():
        print(
            f"Error: no hooks directory found at {hooks_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Determine which platform's script to reference.
    sh_ext = ".bat" if sys.platform == "win32" else ".sh"

    sh_user_prompt = hooks_dir / f"user_prompt_submit{sh_ext}"
    sh_pre_tool = hooks_dir / f"pre_tool_use{sh_ext}"
    sh_stop = hooks_dir / f"stop{sh_ext}"

    for f in (sh_user_prompt, sh_pre_tool, sh_stop):
        if not f.exists():
            print(
                f"Error: hook script not found: {f}",
                file=sys.stderr,
            )
            sys.exit(1)

    if app == "claude-code":
        snippet = {
            "hooks": {
                "UserPromptSubmit": str(sh_user_prompt),
                "PreToolUse": str(sh_pre_tool),
                "Stop": str(sh_stop),
            }
        }
    elif app == "codex-cli":
        snippet = {
            "hooks": {
                "userPromptSubmit": str(sh_user_prompt),
                "preToolUse": str(sh_pre_tool),
                "stop": str(sh_stop),
            }
        }
    else:
        print(f"Error: unknown app '{app}'", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(snippet, indent=2, ensure_ascii=False))


# -- Parser factory (testable) -----------------------------------------------

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cc-pomodoro")
    subparsers = parser.add_subparsers(dest="command")

    # start
    p_start = subparsers.add_parser("start", help="Start a pomodoro session")
    p_start.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration in minutes (default: from config)",
    )
    p_start.add_argument(
        "--app",
        type=str,
        default=None,
        help="Application name (default: claude-code)",
    )
    p_start.add_argument(
        "prompt_text",
        nargs="?",
        default=None,
        help="Optional prompt text to forward to the user",
    )

    # stop
    subparsers.add_parser("stop", help="Stop the current session")

    # status
    subparsers.add_parser("status", help="Show remaining time")

    # stats
    p_stats = subparsers.add_parser("stats", help="Show session statistics")
    p_stats.add_argument("--json", action="store_true", help="Output raw JSONL")

    # config
    p_config = subparsers.add_parser("config", help="Get or set configuration")
    p_config.add_argument(
        "config_action",
        nargs="?",
        choices=["set"],
        help="Action: set a config value",
    )
    p_config.add_argument("key", nargs="?", default=None, help="Config key")
    p_config.add_argument("value", nargs="?", default=None, help="Config value")

    # hooks init
    p_hooks = subparsers.add_parser("hooks", help="Manage hook integration")
    hooks_sub = p_hooks.add_subparsers(dest="hooks_action")
    p_hooks_init = hooks_sub.add_parser(
        "init", help="Print hook config snippet for a CLI app"
    )
    p_hooks_init.add_argument(
        "--app",
        type=str,
        default=None,
        choices=["claude-code", "codex-cli"],
        help="Target application (default: claude-code)",
    )

    return parser


# -- Entry point -------------------------------------------------------------

def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "status":
        cmd_status()
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "hooks":
        if args.hooks_action == "init":
            cmd_hooks_init(args)
        else:
            parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

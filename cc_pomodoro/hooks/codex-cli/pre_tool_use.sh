#!/bin/bash
# Codex CLI PreToolUse hook.
# Auto-allows tool use during active pomodoro sessions.
export CC_POMODORO_APP=codex-cli
exec python -m cc_pomodoro.hooks pre_tool_use

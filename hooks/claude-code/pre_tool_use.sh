#!/bin/bash
# Claude Code PreToolUse hook.
# Auto-allows tool use during active pomodoro sessions.
exec python -m cc_pomodoro.hooks pre_tool_use

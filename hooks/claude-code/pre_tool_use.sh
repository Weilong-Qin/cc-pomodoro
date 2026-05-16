#!/bin/bash
# Claude Code PreToolUse hook.
# Auto-allows tool use during active pomodoro sessions.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec node "$SCRIPT_DIR/../../dist/hooks.js" pre_tool_use

#!/bin/bash
# Codex CLI PreToolUse hook.
# Auto-allows tool use during active pomodoro sessions.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export CC_POMODORO_APP=codex-cli
exec node "$SCRIPT_DIR/../../dist/hooks.js" pre_tool_use

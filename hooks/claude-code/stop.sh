#!/bin/bash
# Claude Code Stop hook.
# Blocks completion signals during active pomodoro sessions.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec node "$SCRIPT_DIR/../../dist/hooks.js" stop

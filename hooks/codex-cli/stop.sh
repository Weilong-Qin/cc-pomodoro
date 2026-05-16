#!/bin/bash
# Codex CLI Stop hook.
# Blocks completion signals during active pomodoro sessions.
# For Codex CLI, also sets suppressOutput=true to hide AI output
# until the session ends.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export CC_POMODORO_APP=codex-cli
exec node "$SCRIPT_DIR/../../dist/hooks.js" stop

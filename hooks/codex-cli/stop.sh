#!/bin/bash
# Codex CLI Stop hook.
# Blocks completion signals during active pomodoro sessions.
# For Codex CLI, also sets suppressOutput=true to hide AI output
# until the session ends.
export CC_POMODORO_APP=codex-cli
exec python -m cc_pomodoro.hooks stop

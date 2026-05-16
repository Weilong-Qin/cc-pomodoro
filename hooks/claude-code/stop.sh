#!/bin/bash
# Claude Code Stop hook.
# Blocks completion signals during active pomodoro sessions.
exec python -m cc_pomodoro.hooks stop

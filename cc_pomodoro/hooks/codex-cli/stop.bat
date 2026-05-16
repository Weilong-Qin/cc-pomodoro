@echo off
REM Codex CLI Stop hook (Windows).
REM Blocks completion signals during active pomodoro sessions.
REM For Codex CLI, also sets suppressOutput=true to hide AI output
REM until the session ends.
set CC_POMODORO_APP=codex-cli
python -m cc_pomodoro.hooks stop

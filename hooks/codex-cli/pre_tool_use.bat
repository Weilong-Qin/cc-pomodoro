@echo off
REM Codex CLI PreToolUse hook (Windows).
set CC_POMODORO_APP=codex-cli
python -m cc_pomodoro.hooks pre_tool_use

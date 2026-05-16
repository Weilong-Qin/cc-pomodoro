@echo off
REM Codex CLI PreToolUse hook (Windows).
set CC_POMODORO_APP=codex-cli
node "%~dp0..\..\dist\hooks.js" pre_tool_use

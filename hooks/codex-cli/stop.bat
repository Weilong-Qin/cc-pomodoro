@echo off
REM Codex CLI Stop hook (Windows).
set CC_POMODORO_APP=codex-cli
node "%~dp0..\..\dist\hooks.js" stop

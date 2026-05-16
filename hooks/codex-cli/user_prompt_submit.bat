@echo off
REM Codex CLI UserPromptSubmit hook (Windows).
set CC_POMODORO_APP=codex-cli
node "%~dp0..\..\dist\hooks.js" user_prompt_submit

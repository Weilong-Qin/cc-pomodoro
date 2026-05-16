@echo off
REM Codex CLI UserPromptSubmit hook (Windows).
REM Reads hook JSON on stdin, passes to the shared decision module.
set CC_POMODORO_APP=codex-cli
python -m cc_pomodoro.hooks user_prompt_submit

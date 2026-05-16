@echo off
REM Claude Code UserPromptSubmit hook (Windows).
REM Reads hook JSON on stdin, passes to the shared decision module.
python -m cc_pomodoro.hooks user_prompt_submit

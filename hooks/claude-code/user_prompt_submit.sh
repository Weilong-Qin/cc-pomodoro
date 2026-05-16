#!/bin/bash
# Claude Code UserPromptSubmit hook.
# Reads hook JSON on stdin, passes to the shared decision module,
# and prints the decision JSON on stdout.
exec python -m cc_pomodoro.hooks user_prompt_submit

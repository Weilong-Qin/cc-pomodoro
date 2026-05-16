#!/bin/bash
# Codex CLI UserPromptSubmit hook.
# Reads hook JSON on stdin, passes to the shared decision module,
# and prints the decision JSON on stdout.
export CC_POMODORO_APP=codex-cli
exec python -m cc_pomodoro.hooks user_prompt_submit

#!/bin/bash
# Claude Code UserPromptSubmit hook.
# Reads hook JSON on stdin, passes to the shared decision module,
# and prints the decision JSON on stdout.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec node "$SCRIPT_DIR/../../dist/hooks.js" user_prompt_submit

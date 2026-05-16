/**
 * Parse /pomodoro prefixed commands from user prompts.
 *
 * The parser carves user input into three buckets:
 *   - ``/pomodoro start [N] <text>`` -- start a pomodoro session (optional duration in minutes)
 *   - ``/pomodoro stop | status | stats | config`` -- meta-commands handled by hooks
 *   - plain text -- no pomodoro command (passed through to the LLM)
 *
 * Grammar::
 *
 *   prompt        = "/pomodoro" command [args] | plain-text
 *   command       = "start" | "stop" | "status" | "stats" | "config"
 *   start-args    = [minutes] text
 *   minutes       = integer
 */

export interface ParseResult {
  command: string | null;
  duration: number | null;
  text: string | null;
}

/**
 * Inspect *prompt* for a leading ``/pomodoro`` prefix.
 *
 * Returns an object with the following keys:
 *
 * **command**
 *   One of ``"start"``, ``"stop"``, ``"status"``, ``"stats"``, ``"config"``,
 *   or ``null`` when no ``/pomodoro`` prefix is present.
 * **duration**
 *   ``number | null`` -- parsed only for the ``start`` command when the first
 *   token after ``start`` is a positive integer.
 * **text**
 *   ``string | null`` -- the remainder of the prompt after stripping the command
 *   and optional duration.  For non-``start`` commands this is everything
 *   after the command token (e.g. ``"set duration 25"`` for ``/pomodoro
 *   config set duration 25``).
 */
export function parsePomodoroCommand(prompt: string): ParseResult {
  const stripped = prompt.trim();

  // Case-insensitive prefix check.
  // Must be exactly "/pomodoro" followed by space or end-of-string
  // (not e.g. "/pomodoro-helper").
  const lowerStripped = stripped.toLowerCase();
  if (!lowerStripped.startsWith('/pomodoro')) {
    return { command: null, duration: null, text: null };
  }

  const afterPrefix = lowerStripped.slice('/pomodoro'.length);
  if (afterPrefix && !afterPrefix.startsWith(' ')) {
    // "/pomodoro" is part of a longer token like "/pomodoro-helper"
    return { command: null, duration: null, text: null };
  }

  // Remove the "/pomodoro" prefix (case-insensitive) and strip
  const rest = stripped.slice('/pomodoro'.length).trim();

  if (!rest) {
    // Bare "/pomodoro" with nothing after it -- treat as no command
    return { command: null, duration: null, text: null };
  }

  const parts = rest.split(/\s+/);
  const command = parts[0].toLowerCase();

  if (command === 'start') {
    const remaining = parts.slice(1);
    let duration: number | null = null;
    let textParts: string[] = [];

    if (remaining.length > 0) {
      // Try the first remaining token as a numeric duration
      const candidate = parseInt(remaining[0], 10);
      if (!isNaN(candidate) && candidate > 0) {
        duration = candidate;
        textParts = remaining.slice(1);
      } else {
        textParts = remaining;
      }
    }

    return {
      command,
      duration,
      text: textParts.length > 0 ? textParts.join(' ') : null,
    };
  }

  // Non-start commands: everything after the command token is text/args
  const text = parts.length > 1 ? parts.slice(1).join(' ') : null;
  return { command, duration: null, text };
}

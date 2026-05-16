# Research: Claude Code Hook System Capabilities

- **Query**: What can Claude Code's hook system do to build a "Pomodoro that hides AI completion and blocks tool authorization until a timer ends"?
- **Scope**: External (official Anthropic docs at code.claude.com/docs/en/hooks.md + hooks-guide.md)
- **Date**: 2026-05-15
- **Sources consulted**:
  - https://code.claude.com/docs/en/hooks.md (hooks reference)
  - https://code.claude.com/docs/en/hooks-guide.md (hooks guide with examples)
  - https://code.claude.com/docs/en/overview.md (Claude Code overview)
  - Local `.claude/settings.json` and hook scripts in this repo (Trellis hooks)

---

## Question 1: Stop Hook -- Can it delay or suppress the final output reveal?

### Verdict: PARTIAL -- can block Claude from stopping, but CANNOT delay/suppress terminal output

### Mechanism

The Stop hook fires **after** Claude finishes responding (i.e., after the LLM has produced its output and it has been rendered to the terminal). Its purpose is to decide whether Claude should stop or continue working.

**Input received on stdin** (from official docs):
```json
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../00893aaf.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Stop",
  "stop_hook_active": true,
  "last_assistant_message": "I've completed the refactoring. Here's a summary..."
}
```

**Decision control**:
| Field      | Description                                                              |
|------------|--------------------------------------------------------------------------|
| `decision` | `"block"` prevents Claude from stopping. Omit to allow Claude to stop    |
| `reason`   | Required when `decision` is `"block"`. Tells Claude why it should continue |

**Exit code 2 behavior**: Prevents Claude from stopping, continues the conversation. (From the exit-code table: "Stop -- Yes, can block -- Prevents Claude from stopping, continues the conversation.")

**What it CAN do**:
- Return `decision: "block"` to tell Claude it should keep working (re-runs the agent loop)
- Read `last_assistant_message` to inspect what Claude produced
- Read the transcript file at `transcript_path` for full context
- Can use `async: true` to fire a background process without blocking

**What it CANNOT do**:
- Cannot intercept or modify terminal output (the output is already written to terminal by the time Stop fires -- Stop fires *after* output is produced and rendered)
- No `updatedToolOutput`-like mechanism exists for Stop (that is a PostToolUse feature, and it changes only what the model sees, not what the user sees)
- Running `sleep(N)` in a Stop hook would block the thread but would **not** undo or hide already-displayed output -- it would only delay the next processing cycle

**Important constraint**: `stop_hook_active` field is `true` when Claude Code is already continuing as a result of a Stop hook. If you return `decision: "block"` repeatedly and Claude responds again, the hook re-fires. You must check this flag to prevent infinite loops.

### Implication for cc-pomodoro

**Critical limitation**: The Stop hook cannot suppress or delay output that has already been written to the terminal. By the time the Stop hook fires, the user has already seen Claude's response. This means:

- **AC1 ("terminal no output during timer") cannot be achieved through Stop hooks alone.** The output is already displayed by the time Stop fires.
- The Stop hook's `decision: "block"` can be used to force Claude to keep working (so the turn does not "complete" and show an idle state), but it does not prevent the user from seeing the output that has already rendered.
- **A different mechanism is required for output suppression** -- see Question 4 below.

---

## Question 2: PreToolUse Hook -- Can it auto-respond to tool-use approval requests?

### Verdict: YES -- can auto-approve or deny, but has no "hold" mechanism in interactive mode

### Mechanism

The PreToolUse hook fires **before** a tool call executes. It has four permission decision values:

| Value    | Effect                                                                                                                |
|----------|-----------------------------------------------------------------------------------------------------------------------|
| `allow`  | Skips the permission prompt. Deny and ask rules from managed settings still apply.                                    |
| `deny`   | Cancels the tool call and sends the reason to Claude                                                                  |
| `ask`    | Shows the permission prompt to the user as normal                                                                     |
| `defer`  | Exits the process gracefully so the tool can be resumed later (**only in non-interactive `-p` mode**)                  |

**Auto-approval mechanism**: Return `permissionDecision: "allow"` in JSON on stdout:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Auto-approved by pomodoro hook during focus period"
  }
}
```

**Multiple hooks precedence**: `deny` > `defer` > `ask` > `allow`

**Note on `defer`**: The official docs state: "`defer` is for integrations that run `claude -p` as a subprocess ... Claude Code honors this value only in non-interactive mode with the `-p` flag. In interactive sessions it logs a warning and ignores the hook result."

**Additional capability**: `PermissionRequest` hook (fires when a permission dialog is about to appear) can also auto-allow:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": { "behavior": "allow" }
  }
}
```

**Key limitations for cc-pomodoro**:
- `allow` does NOT override deny rules from managed/enterprise policy settings
- There is **no "hold until later" mechanism** for PreToolUse in interactive mode. You must return one of the four values immediately; the hook blocks the thread until it exits
- PreToolUse does NOT prevent the LLM's response text from being displayed (that output comes from the model, not from tool calls)

### Implication for cc-pomodoro

- **PreToolUse with `allow` can auto-approve tool calls during the Pomodoro timer**, satisfying AC3 ("blocking requests are queued"). Every tool call during the timer will be silently approved.
- **No native "queue and replay" mechanism exists** in interactive mode. The `defer` mechanism only works in `-p` mode, which is not how users normally run Claude Code.
- **Design implication**: During the Pomodoro, tool calls will either be auto-approved (if we use `allow`) or blocked (if we use `deny`). If we need to queue them for user review, we must implement this ourselves by:
  1. Logging tool calls to a file in the PreToolUse hook
  2. Auto-approving them
  3. At the end of the timer, presenting a summary of what was auto-approved

---

## Question 3: UserPromptSubmit Hook -- Does it fire when the user sends a prompt?

### Verdict: YES -- fires on every user prompt submission, before Claude processes it

### Mechanism

**UserPromptSubmit fires**: "When you submit a prompt, before Claude processes it." No matcher support (always fires on every prompt).

**Input received**:
```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Write a function to calculate the factorial of a number"
}
```

**Decision control**:
| Field               | Description                                                                                 |
|---------------------|---------------------------------------------------------------------------------------------|
| `decision`          | `"block"` prevents prompt processing and erases it from context. Omit to allow.             |
| `reason`            | Shown to the user when `decision` is `"block"`                                              |
| `additionalContext` | String added to Claude's context alongside the submitted prompt                             |
| `sessionTitle`      | Sets the session title                                                                      |

**Timeout**: Default **30 seconds** for command hooks (shorter than the usual 600s default). Can be increased with `timeout` field. The docs note: "Because this hook runs before every prompt and blocks model processing until it completes, a stuck hook stalls the session."

**Plain text stdout** on exit code 0 is added as context for Claude.

### Implication for cc-pomodoro

- **UserPromptSubmit is the correct trigger for starting the Pomodoro timer** (fulfilling R1's "user sends prompt -> auto-start"). The hook fires immediately when the user submits text.
- The `prompt` field provides the user's input, which can be inspected to decide whether to start a timer or not.
- **Important: 30-second default timeout** -- the hook script must be fast (writing a state file and spawning a background process is well within this limit).
- During an active Pomodoro, if the user submits a new prompt, the hook can:
  - Block it with `decision: "block"` and show `reason: "Pomodoro active, X:XX remaining"`
  - Or allow it and reset the timer (policy decision)
- **Cannot use this to "not reveal" output** -- the hook fires before processing, not after.

---

## Question 4: Output Buffering / Hiding -- Is there any hook-level way to suppress terminal output?

### Verdict: NO -- hooks CANNOT suppress the terminal rendering of Claude's output. This is a fundamental architectural limitation.

### Mechanism analysis

**The fundamental architectural limitation**: Claude Code's hooks operate at the lifecycle/decision level, not at the terminal I/O level. Here is the event sequence for a typical turn:

1. User submits prompt (`UserPromptSubmit` fires -- before processing)
2. Claude processes the prompt (LLM call)
3. LLM response begins streaming to the terminal
4. Tool calls are made (`PreToolUse` fires -- before each tool)
5. Tool output is rendered to the terminal
6. Tool call completes (`PostToolUse` fires -- after tool output is rendered)
7. LLM response completes rendering
8. Turn ends (`Stop` fires -- after everything is displayed)

**Every relevant event fires AFTER content has been displayed**:
- PreToolUse fires before a tool runs, but the LLM's *text response* is already streaming by then
- PostToolUse fires after tool output is shown
- Stop fires after the complete response is displayed

**No hook has access to the terminal display layer**:
- There is no "PreOutputDisplay" or "BeforeRender" hook
- There is no hook field for suppressing/capturing stdout
- Hooks are designed for *lifecycle control and context injection*, not terminal output manipulation

**PostToolUse's `updatedToolOutput` does not help**: The docs explicitly warn: "updatedToolOutput only changes what Claude sees. The tool has already run by the time the hook fires, so any files written, commands executed, or network requests sent have already taken effect." It does not affect what the user sees on their terminal.

### Implication for cc-pomodoro

**This is the single most consequential finding for the entire project.** To suppress Claude's output during a Pomodoro timer, we cannot rely on hooks alone. We need a mechanism at the terminal/display level.

**Possible approaches**:

| Approach | Description | Viability |
|----------|-------------|-----------|
| **A. Accept the gap (recommended for MVP)** | Do not actively suppress output. Kill notifications/bells via Stop hook + Notification hook. Rely on user physically switching away from the terminal. | Simplest. Does not fully meet AC1 but tests core hypothesis cheaply. |
| **B. Output style minimization** | Define a minimal Claude Code output style that shows only essential info. Combine with visual training (user looks away). | Lowers visibility but does not eliminate it. |
| **C. Terminal alternate screen buffer** | Use ANSI escape sequences to switch between the main screen (countdown) and alternate screen (Claude output). Timer daemon controls which is visible. | Cross-platform challenges. Claude Code may fight for screen control. |
| **D. PTY / CLI wrapper** | Launch Claude Code within a pseudo-terminal, capture all output, display only what the timer allows. | Complex, ruled out by PRD (grill Q9). |
| **E. Terminal multiplexer** | Run Claude Code in one tmux/zellij pane, timer in another. Hide the Claude pane during timer. | Requires tmux/zellij. Not universal. |

**Recommendation**: Start with Approach A for MVP. The core insight from grilling is that the user's reflex is triggered by *notifications/bells + the ability to instantly check*. If we eliminate the notification and the user deliberately switches away from the terminal, the output being present may not matter. Validate this before investing in complex suppression.

---

## Question 5: Persistent TUI Overlay / Countdown Timer

### Verdict: PARTIAL -- hooks cannot natively display a persistent TUI, but can spawn background processes that manage one in a separate context

### Mechanism

**What hooks CAN do**:
- The `async: true` field on a command hook runs the hook command in the background without blocking Claude Code's main thread
- The `asyncRewake: true` field (implies `async`) additionally wakes Claude up if the background process exits with code 2. The hook's stderr is shown to Claude as a system reminder
- A background process spawned as an async hook can write to files, display system notifications, or manage a separate terminal/pane

**What hooks CANNOT do**:
- Display a persistent TUI overlay within Claude Code's terminal window
- Draw over or modify Claude Code's rendered output
- Register keybindings for hotkeys (like Ctrl+E for early stop)
- Prevent Claude Code's own terminal output from overwriting a TUI region
- Provide a "status bar" or "footer" area that survives Claude Code's output

**The fundamental constraint**: Claude Code owns the terminal. A hook script that prints to stdout has its output captured into the hook system, not rendered as a UI element.

### Implication for cc-pomodoro

- **A separate terminal/display mechanism is required** for the countdown timer (as the PRD assumes -- "CLI 只显示倒计时")
- Options for displaying the countdown:
  1. **Separate terminal window**: The background daemon spawns a new terminal/PowerShell window showing only the countdown
  2. **Terminal multiplexer pane**: Use tmux (macOS/Linux) or Windows Terminal panes to show Claude Code in one pane and the countdown in another
  3. **System notification updates**: Use OS-level notifications for time updates at intervals
  4. **Overlay window**: A separate GUI window (Tkinter, Electron, etc.) showing the countdown and handling early-stop
- **Hotkey handling** (Ctrl+E for early stop) needs OS-level global hotkey listening, since hooks do not provide keybinding registration within Claude Code
- The `async: true` field is viable for spawning the timer daemon, but the daemon must communicate with the timer-display process

---

## Question 6: Hook Lifecycle and Async Behavior

### Verdict: YES -- hooks can spawn async background processes and persist state via files, with documented constraints

### Mechanism details

**Async hooks**:
| Field         | Description                                                                                                                             |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `async`       | If `true`, runs in the background without blocking. No decision control is possible (the hook runs and forgets, no exit code is read).  |
| `asyncRewake` | If `true`, runs in the background and wakes Claude on exit code 2. Implies `async`. Stderr is shown to Claude as a system reminder.     |

**State persistence**:
- Hooks are arbitrary shell commands or scripts -- they can read/write files freely
- State can be persisted to disk (e.g., `/tmp/cc-pomodoro-state.json`, project-local files, or user home directory)
- A background daemon process can maintain state and communicate with hook scripts via files or IPC
- `CLAUDE_PROJECT_DIR` environment variable is available to locate project-relative paths

**When hooks fire for cc-pomodoro-relevant events**:
| Event               | Cadence       | Matcher support | Use for cc-pomodoro                                  |
|---------------------|---------------|-----------------|------------------------------------------------------|
| UserPromptSubmit    | Every turn    | No              | TRIGGER: Start Pomodoro timer                        |
| PreToolUse          | Every tool    | Yes (tool name) | CONTROL: Auto-approve tool calls during timer        |
| PostToolUse         | Every tool    | Yes (tool name) | MONITOR: Track tool use during timer                 |
| Stop                | Every turn    | No              | CONTROL: Prevent Claude from stopping (keep working) |
| Notification        | Per event     | Yes (type)      | ALERT: Notify when timer expires as idle_prompt      |
| SessionEnd          | Session end   | Yes (reason)    | CLEANUP: Kill pomodoro daemon                        |

**State communication patterns**:
1. **File-based** (simplest): Hook writes/reads JSON from a well-known file path
2. **Socket-based**: Background daemon listens on a Unix/TCP socket; hooks send requests
3. **Process signaling**: Background daemon identified by PID file; hooks send signals

**Timeout defaults**:
- Most events: 600 seconds
- UserPromptSubmit: 30 seconds
- Prompt hooks: 30 seconds
- Agent hooks: 60 seconds

### Implication for cc-pomodoro

- **Async hooks are viable for spawning a timer daemon** that runs during the Pomodoro session
- **File-based state is the simplest and most reliable approach** for hook-to-hook communication:
  - `UserPromptSubmit` hook writes `{"started_at": <ts>, "duration": <min>, "state": "running"}` to a state file
  - `PreToolUse` hook checks the state file to decide whether to auto-approve
  - `Stop` hook checks the state file to decide whether to block Claude from stopping
  - `SessionEnd` hook cleans up state
- **Parallel execution consideration**: If multiple hooks need to coordinate (e.g., PreToolUse and Stop both checking the same state file), ensure atomic writes (write to temp file, rename to target)
- **Timeout consideration**: UserPromptSubmit's 30s default timeout is tight but sufficient for writing a state file and spawning a process. If the hook needs more time, the `timeout` field can increase it.

---

## Design Implications Summary

The 5 most consequential findings for cc-pomodoro's technical approach, in priority order:

### 1. [CRITICAL -- ARCHITECTURE BREAKING] Hooks cannot suppress terminal output

No hook mechanism exists to buffer, delay, or hide Claude Code's terminal output. The Stop hook fires *after* output is already displayed. PreToolUse fires before tool execution but the LLM's response text is already streaming. This means the project's core mechanism (**R2: "no output in CLI during timer"**) **cannot be achieved through hooks alone**.

**Immediate decision needed**: Re-scope R2 for MVP to mean "no notification + minimal visual disruption" rather than "no output at all." Add PTY-based output capture as a P1 feature if initial user testing shows the gap is fatal.

### 2. [ACHIEVABLE] PreToolUse can auto-approve tool calls during the timer

PreToolUse with `permissionDecision: "allow"` is a well-documented working mechanism. However, there is no "hold and replay" mechanism in interactive mode -- the `defer` feature only works in `-p` mode. Tool calls during the timer must be either auto-approved or auto-denied; they cannot be queued for delayed user review without custom logging.

**Design resolution**: Auto-approve all tool calls during the timer. Log details for post-session review display. The PRD says "AI idling is acceptable" but auto-approving is better since it lets Claude complete the work.

### 3. [ACHIEVABLE] UserPromptSubmit is the correct trigger

UserPromptSubmit fires on every user prompt with a 30s default timeout. It can start the Pomodoro timer and optionally block follow-up prompts during an active session. File-based state is sufficient for detecting whether a timer is already running.

### 4. [PARTIAL] Stop hook can keep Claude working but not hide output

Stop hook with `decision: "block"` prevents Claude from stopping, which prevents the "idle, waiting for input" state. But the user has already seen the output. The `stop_hook_active` flag must be checked to prevent infinite loops.

### 5. [PARTIAL] No native persistent TUI or hotkey support; separate process required

Hooks cannot display a persistent countdown timer within Claude Code's terminal or register hotkeys. A separate background process is required for the countdown display and early-stop hotkey. The `async: true` field enables spawning this daemon.

### Architectural Architecture

```
                    ┌─────────────────────────────────────┐
                    │        Claude Code Process           │
                    │                                      │
  User sends ───────┤ UserPromptSubmit hook ──────┬───────┤
  prompt             │  (starts timer, writes      │       │
                     │   state file, optionally    │       │
                     │   spawns countdown display) │       │
                     │                              │       │
  Tool call ────────┤ PreToolUse hook ────────────┤       │
                     │  (reads state file,         │       │
                     │   auto-approves if timer    │       │
                     │   is running)               │       │
                     │                              │       │
  Turn end ─────────┤ Stop hook ──────────────────┤       │
                     │  (reads state file,         │       │
                     │   blocks stop if timer      │       │
                     │   is running)               │       │
                     │                              │       │
  Session end ──────┤ SessionEnd hook ────────────┘       │
                     │  (cleans up state)                  │
                     └─────────────┬───────────────────────┘
                                   │ file-based state
                                   │ (JSON on disk)
                                   │
                          ┌────────┴────────┐
                          │ Timer Daemon    │
                          │ (async spawned) │
                          │ - Updates state │
                          │ - Sends notifs  │
                          └─────────────────┘
```

### Priority Order for What to Build

1. **UserPromptSubmit hook** to start the timer and write state
2. **PreToolUse hook** to auto-approve tool calls during timer (reads state file)
3. **Stop hook** to keep Claude working during timer (reads state file, blocks stop)
4. **Timer state machine** (state file with start time, duration, status)
5. **Countdown display** (separate process, initial simplest form)
6. **Early-stop mechanism** (signal file or hotkey)
7. **SessionEnd hook** for cleanup

### What the official docs do NOT document (gaps to experiment with)

- Whether multiple hooks across different events can reliably read/write the same file concurrently
- Whether there is any undocumented escape hatch for terminal output manipulation
- The exact behavior when a hook script hangs (beyond the timeout) and whether it crashes Claude Code
- Whether `asyncRewake` works reliably across platforms (especially Windows)
- The exact terminal behavior when Claude Code's stdout is piped to a file (interactive features may break)

---

## Files Referenced

| File | Description |
|------|-------------|
| `.claude/settings.json` | Current hook configuration for Trellis (SessionStart, PreToolUse, UserPromptSubmit) |
| `.claude/hooks/inject-subagent-context.py` | Example of PreToolUse hook script |
| `.claude/hooks/inject-workflow-state.py` | Example of UserPromptSubmit hook script |
| `.claude/hooks/session-start.py` | Example of SessionStart hook script |

## External References

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks.md) -- full event schemas, JSON input/output formats, exit codes, async hooks
- [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide.md) -- common use cases with examples
- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference.md) -- command-line flags and options
- [Claude Code Overview](https://code.claude.com/docs/en/overview.md) -- general architecture

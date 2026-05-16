# Research: CLI Countdown Display

- **Query**: How to display a persistent in-terminal countdown timer during a Pomodoro session while suppressing all other AI output
- **Scope**: Mixed (internal patterns research + external tool analysis)
- **Date**: 2026-05-15

## Findings

### Question 1: How do existing CLI Pomodoros render a persistent timer?

#### Pattern A: Full-screen TUI (terminal takeover)

**Tools using this pattern:**

1. **pomo** (Go, 1.2k+ stars) -- Uses `termui` v3 TUI library. Calls `ui.Init()` which switches to the alternate screen buffer (`\033[?1049h`), then renders a centered `widgets.Paragraph` widget with a 250ms tick loop. Keyboard events polled via `ui.PollEvents()`. On quit, calls `ui.Close()` which restores the main screen buffer.
   - Source: `pkg/internal/ui.go` -- `StartUI()` function
   - Key calls: `ui.Init()`, `ui.PollEvents()`, `ui.Render(par)`, `ui.Clear()`, `ui.Close()`
   - Key ANSI: internal to termui, likely uses alternate screen buffer

2. **mytimer** (Python, 146 stars) -- Simple `clear_screen()` + `tprint()` loop. Calls `os.system('cls')` on Windows or `os.system('clear')` on Unix, then re-renders the full timer using ASCII art via the `art` library every second with `time.sleep(max(0, 1 - elapsed))`.
   - Source: `mytimer/functions.py` -- `countdown_timer()` function
   - Pattern: brute-force clear + reprint. No cursor save/restore, no alternate screen.
   - Cross-platform: uses `sys.platform == "win32"` check for `cls` vs `clear`

3. **timomt/pomodoro** (C++, minimal) -- Raw ANSI escape codes. Uses `\033[2J\033[1;1H` to clear screen and reposition cursor to (1,1), then re-renders entire display including ASCII art and progress bar every second. Uses `std::flush` for immediate output.
   - Source: `timer.cpp` -- `clear_screen()`, `move_to()`, `show_progress_bar()`
   - Key ANSI: `\033[2J` (clear entire screen), `\033[1;1H` (cursor home), `\033[Y;XH` (cursor positioning), `\033[1G` (cursor to column 1)

| Aspect | pomo (Go) | mytimer (Python) | timomt/pomodoro (C++) |
|--------|-----------|-------------------|----------------------|
| Library | termui v3 | art + colorama | Raw ANSI |
| Screen | Alternate buffer | Clear + reprint | Clear + reprint |
| Refresh | 250ms ticker | 1s sleep | 1s sleep |
| Standalone | Yes (takes over) | Yes (takes over) | Yes (takes over) |
| Overlay capability | None | None | None |

**Assessment**: All three are **standalone** tools that take over the full terminal. None of them solve the "overlay while another foreground process runs" problem. This is a critical gap.

---

#### Pattern B: tmux/zellij status line integration

**Tools:**

1. **alexanderjeurissen/tmux-pomodoro** -- Bash-based tmux plugin. Adds a pomodoro timer section to the tmux status line via `#(pomodoro_script)` syntax in `.tmux.conf`. The script checks a state file and outputs the formatted timer. Tmux handles rendering it in the status bar (which is persistent regardless of pane content).

2. **swaroopch/tmux-pomodoro** -- Similar approach: tmux plugin that writes the countdown to `tmux display-message` or the status bar.

**Pattern**: The timer runs as a **background process** that updates a state file. The **multiplexer status bar** polls and renders it. This is truly persistent -- the status bar is outside the scrollable pane area.

| Aspect | tmux-pomodoro |
|--------|--------------|
| Persistence | High (status bar always visible) |
| Overlay capability | Requires tmux (not a generic solution) |
| Cross-platform | Linux/macOS only (tmux not native on Windows) |
| Hotkey support | Via tmux keybindings |

---

#### Pattern C: Terminal scroll region (DECSTBM)

**Technique description**: Use `\033[<top>;<bottom>r` to define a scroll region that excludes the bottom N lines. Normal output scrolls within the restricted region. A persistent status line is written to the excluded area and never scrolls away.

- ESC sequence: `\033[1;24r` (set scroll region to lines 1-24, line 25 is fixed)
- Reset: `\033[r` (reset to full screen)
- Key detail: After setting scroll region, you must move cursor to the restricted area before sending output that should scroll
- Write the status line to line 25 using `\033[25;1H`

**Real-world use**: This is how `less`, `vi`, and `screen` implement status lines. The `less` pager uses `\033[7m` (reverse video) on the last line for its status bar.

**VERDICT**: This is the most promising pattern for our use case because:
- No multiplexer dependency
- Works in any terminal that supports ANSI (VT100+)
- Genuinely persistent -- the status line cannot be scrolled away
- Compatible with another foreground process outputting above it

**Caveat**: Not all terminals support DECSTBM correctly. Windows Terminal does. Classic cmd.exe may not. WSL/Terminal on Windows 10+ does.

---

#### Pattern D: Cursor save/restore (DECSC/DECRC + `tput sc`/`tput rc`)

**Technique description**: Before the foreground process outputs, save cursor with `\033[s` or `\0337` (DECSC). After output, restore cursor with `\033[u` or `\0338` (DECRC), move to bottom line, print timer.

- Save: `\0337` (VT100) or `\033 s` (also common)
- Restore: `\0338`
- Or use terminfo: `tput sc` / `tput rc`

**Problem**: This only works if you control when the other process writes. If the other process outputs between save and restore, the position is lost. Also, previous output scrolls the timer away. **Not suitable** for our case where Claude Code outputs unpredictably.

---

### Question 2: Overlay while Claude Code is running and printing output

This is the hardest technical problem. Four approaches evaluated:

#### Overlay-A: DECSTBM scroll region + separate FD output

**How it works:**
1. Before starting Claude Code, set scroll region to exclude the bottom 1-2 lines
2. Write the countdown timer to the bottom fixed line(s)
3. Run Claude Code normally -- its output scrolls within the restricted region
4. Every second, the pomodoro hook re-writes the timer on the fixed line

**Key ANSI workflow:**
```
\033[1;$((LINES-1))r   # set scroll region (excluding last line)
\033[${LINES};1H        # move cursor to last line
\033[K                  # clear that line
Timer: 14:32 - focus mode
\033[1;1H               # return cursor to top
```

**Pros:**
- Works with any foreground process
- No multiplexer dependency
- Standard ANSI (VT100+)
- The timer line truly cannot be overwritten by scrolling

**Cons:**
- Requires the hook to wrap/inject Claude Code's terminal setup
- Claude Code itself may set its own scroll region (unlikely but possible)
- Terminal resize breaks the scroll region (need SIGWINCH handler)
- Windows compatibility is limited for advanced ANSI

#### Overlay-B: OSC escape codes (terminal title/tab)

**How it works:** Use OSC 0 or OSC 2 to set the terminal window title. Show the countdown as the tab title.
```
\033]0;Pomodoro 14:32 - focus mode\007
```

**Pros:**
- Zero interference with terminal content
- Works on all modern terminals (including Windows Terminal)
- Very simple to implement
- Claude Code's output is fully visible (or can be independently suppressed)

**Cons:**
- The timer is in the tab/title bar, not the terminal body
- Easy to miss if user has many tabs
- Not "persistent in-terminal" as required by R4
- Some terminals have title update rate limits

#### Overlay-C: tmux/zellij split-pane integration

**How it works:** The user is advised to run in tmux. The pomodoro tool detects tmux and creates a split pane or uses the status bar for the timer.

**Pros:**
- Battle-tested pattern (existing tmux-pomodoro plugins)
- Genuinely separate rendering surface
- Hotkey handling via tmux keybindings

**Cons:**
- **Requires tmux** -- adds a mandatory tool dependency
- tmux is not native on Windows (WSL not everyone has)
- Users who don't use tmux need to adapt their workflow
- Contradicts PRD requirement R4 (CLI-native, no multiplexer dependency per grill Q9)

#### Overlay-D: Separate terminal window / Notification

**How it works:** Open a second terminal window (e.g., `cmd /c start` on Windows, `osascript -e 'tell app "Terminal"'` on macOS) that shows only the countdown. Or use OS notifications.

**Pros:**
- Trivially separate rendering
- Works regardless of what the main CLI does

**Cons:**
- Requires window manager / GUI
- Not CLI-native
- PRD explicitly excludes "lock terminal / full-screen overlay" (grill Q4)
- Notification defeats the purpose (user sees notification and gets distracted)

---

### Question 3: Output buffering / hiding pattern

During the focus window, the AI's output must not reach the user. This is the "R2 shield completion signal" requirement. Three approaches are evaluated:

#### Buffer-A: stdout pipe-through (tee to buffer file)

**How it works:** Claude Code's stdout is redirected through a pipe. The pomodoro hook:
1. Captures all stdout/stderr to a memory buffer + optional file log
2. Suppresses all output to terminal during focus
3. Displays only the countdown timer on a fixed terminal line
4. On timer end, replays the buffered output at normal speed (or instantly)

**Implementation sketch:**
```python
# Launch Claude Code with piped output
proc = subprocess.Popen(
    ["node", "claude-code", ...],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)
buffer = []
while pomodoro_active:
    # Read output in chunks (non-blocking)
    output = proc.stdout.read1()
    buffer.append(output)
    # Render countdown timer on fixed line
    render_timer(remaining)
# Timer ended -- replay buffer
sys.stdout.write(b''.join(buffer))
```

**Pros:**
- Works at the process level, independent of Claude Code internals
- Proven technique (like `script(1)` command)
- Can also capture stderr

**Cons:**
- The pomodoro process needs to **own** the Claude Code process (parent process)
- Breaks when Claude Code writes directly to `/dev/tty` (bypassing stdout)
- Claude Code may detect piped output and change behavior (color disable, etc.)
- The "pipe wrapper" approach was **explicitly rejected** in grill Q9 (D方案 not wrapper path)

#### Buffer-B: PTY wrapper (pseudoterminal)

**How it works:** Instead of a pipe, use a PTY (pseudoterminal). Claude Code thinks it's writing to a real terminal. The PTY master captures all output, suppresses it during focus, and replays on timer end.

**Tools that use this pattern:** `script(1)`, `expect`, `tmux`, `asciinema`, `cat(1)` with PTY

**Implementation approach:** Use Python's `ptyprocess` or Rust's `portable-pty` (from `zellij` project).

**Pros:**
- Claude Code cannot detect it's not a real terminal (preserves colors, interactive features)
- Can inject input (for auto-responding to tool use prompts)
- Full control over output timing

**Cons:**
- Significantly more complex than pipe
- Cross-platform: PTY is Unix-only. Windows requires named pipes/signals with ConPTY
- Still a "wrapper" pattern which grill Q9 rejected
- The tool manages the Claude Code lifecycle, not the user

#### Buffer-C: Hook-based output suppression (Claude Code hooks)

**How it works:** Claude Code hooks may provide a way to suppress or redirect output. Based on touch-grass analysis, the available hooks are:

Known hooks from `.claude-plugin/plugin.json`:
- `SessionStart`: Runs a command at session start. Can inject `additionalContext`. **Cannot suppress output.**
- Possible hooks we haven't confirmed: `Stop`, `PreToolUse`, `PostToolUse`, `Message`

The `SessionStart` hook returns JSON to stdout:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "optional text"
  }
}
```

**Key finding:** Claude Code hooks (as demonstrated by touch-grass) are **context injectors, not output interceptors**. They run and communicate via stdout JSON. They cannot suppress or redirect Claude Code's own rendering.

**This research finding invalidates the PRD assumption** that "Claude Code's Stop hook + PreToolUse hook can block completion + delay authorization." The actual hook system is more limited -- it allows adding context before a session or before tool use, but does not allow:
- Suppressing terminal output
- Blocking/delaying a turn completion
- Intercepting authorization requests

**This means the "hook-only" approach cannot satisfy R2 and R3. A non-hook mechanism (pipe/PTY wrapper) is required.**

#### Buffer-D: Alternate screen buffer swap

**How it works:**
1. Before focus: save current screen state, switch to alternate screen (`\033[?1049h`)
2. During focus: the alt buffer shows only the countdown
3. Claude Code writes to the primary buffer (hidden from view)
4. On timer end: restore primary buffer (`\033[?1049l`), revealing all output

**Problem:** The alternate screen buffer is per-terminal. If Claude Code also uses it (which most TUIs including cursor-based CLIs do), the two will conflict. Additionally, Claude Code's output goes to stdout which also gets written to whichever buffer is active.

---

### Question 4: Hotkey detection while in focus mode

#### Hotkey-A: Slash command via hook

**Pattern:** The user types `/pomodoro stop` into the Claude Code prompt. Claude Code processes it as a regular prompt, the pomodoro hook intercepts it at the `PreToolUse` or `SessionStart` level.

**Pros:**
- No special keyboard handling needed
- Works within Claude Code's existing input cycle
- Does not steal stdin focus from Claude Code

**Cons:**
- Not a "hotkey" -- user has to stop typing and type a command
- Adds latency (Claude Code processes the command as a turn)
- Contradicts R5's "hotkey" requirement (Ctrl+E)

#### Hotkey-B: Raw stdin monitoring (separate thread/process)

**Pattern:** A background thread monitors stdin for the hotkey sequence (Ctrl+E = `\x05`). When detected, it signals the main pomodoro loop.

**Key challenge:** If Claude Code is also reading stdin, who gets the keypress? On Unix, only one process can read from the terminal's stdin at a time. On Windows, the console input is similarly exclusive.

**Solution options:**
1. The pomodoro wrapper process owns the PTY master -- it can read stdin AND inject into the PTY slave
2. Use a separate terminal input source (e.g., a signal file that the pomodoro process polls)

#### Hotkey-C: Terminal signal/window change detection

**Pattern:** Use a different mechanism that does not compete with stdin:
- Terminal focus events (`\033[I` / `\033[O`) -- not widely supported
- SIGUSR1/SIGUSR2 -- Unix only
- A file that a keybind daemon writes to (e.g., via a desktop-wide hotkey tool)

#### Hotkey-D: Two-phase approach (hotkey + confirmation text)

**Pattern:** 
1. A small key listener runs in a separate thread that only reads stdin when Claude Code is NOT actively reading it
2. On Ctrl+E, it sets a flag
3. At the next Claude Code prompt (when Claude Code yields control back to the user), the hook detects the flag and shows the Y/N confirmation

**This is probably the most realistic approach** since it doesn't compete with Claude Code for stdin ownership.

**Summary:**

| Approach | Reliability | Complexity | Cross-platform | R5 compliance |
|----------|-------------|------------|----------------|--------------|
| Slash command | High | Low | Yes | Partial (not instant hotkey) |
| Raw stdin monitor | Medium | High | Unix-only | Yes |
| Two-phase flag | Medium | Medium | Depends | Yes |
| Desktop hotkey daemon | Medium | High | Varies | Yes |

---

### Question 5: Cross-platform constraints

#### ANSI escape support table

| Feature | Linux/macOS terminal | Windows Terminal | cmd.exe | PowerShell |
|---------|---------------------|------------------|---------|------------|
| `\033[2J` clear screen | Yes | Yes | No* | Yes |
| `\033[Y;XH` cursor pos | Yes | Yes | No* | Yes |
| `\033[s` / `\033[u` save/restore | Yes | Yes | No | Yes |
| `\033[<t>;<b>r` scroll region | Yes | Yes | No | Yes |
| `\033[?1049h` alt screen | Yes | Yes | No | No** |
| `\033]0;...\007` title/OSC | Yes | Yes | Yes | Yes |
| `\033[K` clear line | Yes | Yes | No* | Yes |
| `\07` bell | Yes | Yes | Yes | Yes |

*\* cmd.exe on Windows 10 1607+ with ENABLE_VIRTUAL_TERMINAL_PROCESSING flag enables ANSI support. Many users don't have this enabled by default.*
*\*\* PowerShell on Windows 10+ supports alternate screen via `$Host.UI.RawUI` but not raw ESC sequences*

#### Key cross-platform findings:

1. **Windows Terminal (the modern one)** -- excellent ANSI support including DECSTBM, alt screen, OSC, colors. Comparable to xterm.

2. **cmd.exe** -- historically the worst. Win10 1607+ can support ANSI but it's opt-in via `ENABLE_VIRTUAL_TERMINAL_PROCESSING` in the console API. Many enterprise environments have it disabled.

3. **PowerShell** -- better than cmd.exe. Supports most VT sequences. The console host (`conhost.exe`) on Win10+ has good VT support.

4. **tmux** -- not natively available on Windows. WSL users can install it but that's a big ask.

5. **`os.system('cls')`** -- always works on Windows (any shell). `\033[2J` is not guaranteed on cmd.exe.

6. **The safest universal pattern** for Windows is:
   - On Windows: use Windows Console API (`SetConsoleMode` with `ENABLE_VIRTUAL_TERMINAL_PROCESSING`) to enable ANSI, then use ANSI sequences. Or fall back to `cls`.
   - On Unix: use standard ANSI escapes
   - Libraries like Python's `colorama` or Rust's `crossterm` handle this automatically

#### Tools/libraries that handle cross-platform terminal:

| Library | Language | Handles ANSI | Windows support | Notes |
|---------|----------|-------------|-----------------|-------|
| `crossterm` | Rust | Yes | Yes (via Win API) | Best for Rust |
| `termion` | Rust | Yes | No (Unix only) | |
| `ratatui` | Rust | Yes | Yes (via crossterm) | TUI framework |
| `colorama` | Python | Yes | Yes (wraps Win API) | Colors only |
| `rich` | Python | Yes | Yes | Full terminal markup |
| `bubblewrap` | Python | Yes | Yes | TUI framework |
| `termui` | Go | Yes | Partial | No longer maintained |
| `bubbletea` | Go | Yes | Yes | Popular TUI framework |

---

### Related Specs

- `.trellis/spec/guides/` (default boilerplate, needs to be populated with actual project specs)
- PRD: `.trellis/tasks/05-15-ai-cli-cc-pomodoro/prd.md` (defines R1-R8 requirements)

### External References

- **pomo (Go)**: https://github.com/kevinschoon/pomo -- Full-screen TUI using termui. Source read: `pkg/internal/ui.go`, `pkg/internal/runner.go`, `pkg/cmd/cmd.go`.
- **mytimer (Python)**: https://github.com/sepandhaghighi/mytimer -- Clear-screen + ASCII art timer. Source read: `mytimer/functions.py`.
- **timomt/pomodoro (C++)**: https://github.com/timomt/pomodoro -- Raw ANSI escape code timer. Source read: `timer.cpp`, `timer.h`, `main.cpp`.
- **tmux-pomodoro**: https://github.com/alexanderjeurissen/tmux-pomodoro -- Tmux status bar integration.
- **touch-grass (Claude Code plugin)**: https://github.com/nalediym/touch-grass -- Reference for Claude Code hook system. Source read: `plugin/hooks/session-start.mjs`, `plugin/.claude-plugin/plugin.json`.
- **ANSI escape code reference**: https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797 -- Complete table of ANSI escape codes.
- **Windows Terminal ANSI support**: https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences -- Official docs on VT sequence support in Windows Console.
- **scroll-region technique**: https://terminalguide.namepad.de/seq/csi_sr/ -- DECSTBM documentation.

## Caveats / Not Found

- **Claude Code "Stop" and "PreToolUse" hooks were NOT confirmed to exist or support output suppression.** The touch-grass plugin demonstrated `SessionStart` only as a context-injecting hook. The full hook API surface of Claude Code is not documented publicly; the research here is based on reverse-engineering from the only known published plugin (touch-grass). If `Stop`/`PreToolUse` hooks exist and support output manipulation, this finding is incomplete.

- **Codex CLI hook system was NOT researched in this pass** -- it is listed as Open Question 1 in the PRD.

- **PTY-based output suppression** is known to work but was only described conceptually; no existing hook-based or PTY-based Pomodoro-for-AI-CLI tool was found to reference.

- **No existing tool** that combines "Pomodoro timer" + "AI CLI output suppression" + "delayed output reveal" was found. This appears to be a novel combination. The closest precedents are standalone CLI timers (Pattern A) and tmux status bar timers (Pattern B), neither of which handle output buffering.

- **The pipe/PTY wrapper approach** (which is the most realistic for R2+R3 fulfillment) was explicitly rejected in grill Q9. This creates a tension: our analysis suggests that hook-only approaches cannot suppress AI output (R2) or block authorization (R3). The architecture decision may need to be re-opened.

## Recommendation

### Primary pattern: Pipe wrapper + ANSI status line (DECSTBM scroll region)

Given the research findings, **the only viable approach that satisfies all requirements** without tmux dependency and with cross-platform reach is:

1. **Architecture**: A **thin CLI wrapper** that launches Claude Code/Codex CLI as a child process. This is essentially the "D" path from grill Q9 combined with the pipe approach.
   - The wrapper owns the terminal connection
   - Claude Code's stdout/stderr are captured via PTY (Unix) or ConPTY (Windows)
   - Output is buffered, not displayed, during focus

2. **Rendering**: After starting Claude Code, the wrapper:
   - Sets a **DECSTBM scroll region** excluding the bottom 1-2 lines
   - Writes the countdown timer to the fixed bottom line(s) every second
   - Claude Code's output scrolls in the main region (but is rendered invisible by not forwarding it to terminal)

3. **Output reveal** on timer end or early stop:
   - Reset scroll region to full screen
   - Flush the buffered Claude Code output to terminal
   - Send a bell (`\07`) notification

4. **Hotkey**: Read stdin directly (the wrapper owns the terminal). Ctrl+E detection via `\x05`. On detection, show Y/N prompt on the status line.

5. **Cross-platform**: Use `crossterm` (Rust) for PTY management and ANSI handling, or `colorama` + `pywin32` (Python). The DECSTBM sequence is supported on Windows Terminal and modern PowerShell; fall back to cursor-save-restore `tput sc`/`tput rc` on classic cmd.

### Fallback pattern: Hook-based + OSC title timer

If the wrapper architecture is absolutely rejected (per grill Q9), the fallback is:
1. Use Claude Code's `SessionStart` hook to record start time
2. Use an MCP server running alongside Claude Code that:
   - Displays countdown via OSC title escape (`\033]0;Pomodoro 14:32\007`) in the terminal tab
   - Writes the timer to stderr (which Claude Code doesn't suppress) on each tick
   - Logs output to a file for later review (no true R2/R3 suppression)
3. The slash command `/pomodoro stop` triggers early end

**This fallback CANNOT satisfy R2 (suppress output), R3 (block authorization), or R4 (timer-only display).** It is only recommended if the wrapper path is definitively blocked by project constraints.

### Critical decision needed

The research makes clear that **the PRD's R2 and R3 requirements (output suppression + authorization blocking) are fundamentally incompatible with a hook-only architecture**. A process-level wrapper (pipe or PTY) is required. The grill Q9 "D" path either needs re-interpretation to allow a thin wrapper, or the PRD requirements need adjustment. This should be raised as a blocking clarification before implementation begins.

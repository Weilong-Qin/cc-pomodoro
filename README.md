# cc-pomodoro

> CLI-native Pomodoro for AI agent workflows. Focus on your deep work -- let the AI wait.

---

## Philosophy

AI coding assistants close the loop between thought and execution faster than any tool before them. But that speed comes with a new kind of cognitive tax: the moment the AI finishes a turn, a notification fires, dopamine hooks, and you tab back to the terminal -- mid-sentence in the paper you were reading, mid-thought in the design document you were writing. The context you were holding evaporates. This is the **reactive reflex arc**: AI finishes -> notification -> switch context -> lost flow. cc-pomodoro exists to sever that single arc, and nothing more.

The design centers on one principle: **protect the human's focus above all else.** The AI idling during a Pomodoro session is an acceptable cost. The tool does not lock your keyboard, hide your terminal, or shame you for reaching for the mouse. It trusts you to manage your own attention. It only silences the AI's side of the trigger -- the bells, the output floods, the tool-approval popups that yank you out of deep work.

A Pomodoro session is a **commitment device you opt into**, not an automatic prison. That is why `auto_start` defaults to off. You decide when to focus. The tool simply makes it easier to follow through on that decision by removing the strongest external interruption: the AI itself.

Statistics are a welcome byproduct, not the core value. The value is the **CLI-native interaction integration** -- dispatch-triggered sessions, completion shielding, auto-authorization, and soft early-exit. These are the mechanisms that no general-purpose Pomodoro app can provide because they require hooking into the AI CLI's own lifecycle. That is the reason this tool exists.

---

## Features

- **Dispatch-triggered**: Start a Pomodoro simply by sending a prompt. No separate timer app. No context switch.
- **Completion shielding**: No bell, no notification, no flood of output until the timer ends. The AI finishes silently in the background.
- **Auto-authorization**: Tool-approval requests (shell commands, file reads) are automatically allowed during a session. No popups, no interruptions.
- **Cross-platform**: Supports both Claude Code and Codex CLI on macOS, Linux, and Windows.
- **Soft early-exit**: "14 min remaining, confirm? [y/N]" -- respects your judgment without impulsive friction.
- **Focus analytics**: Per-app daily and weekly session summaries via `/pomodoro stats`.

---

## Quick Start

### Prerequisites

- **Node.js 18 or later** installed on your system.
- **npm** (ships with Node.js).

### Installation

```bash
npm install -g cc-pomodoro
```

Or install from source:

```bash
git clone https://github.com/VLooong/cc-pomodoro.git
cd cc-pomodoro
npm install
npm run build
npm link
```

### 1. Initialize hooks

```bash
cc-pomodoro hooks init --app claude-code
```

Copy the printed JSON object into your `.claude/settings.json` `hooks` section. Full step-by-step instructions are in [docs/INSTALL.md](docs/INSTALL.md).

### 2. Start focusing

In Claude Code or Codex CLI:

```
/pomodoro start 25 Refactor authentication module
```

Then switch to your deep work. Read a paper. Write a design doc. Come back when the timer ends.

### 3. Check your stats

```
/pomodoro stats
```

---

## Configuration

Configuration is read from `~/.config/cc-pomodoro/config.json`. You can also read and change settings from within the CLI using `/pomodoro config`.

| Key                 | Type    | Default        | Description                                          |
|---------------------|---------|----------------|------------------------------------------------------|
| `duration`          | integer | 50             | Default session length in minutes                    |
| `auto_start`        | boolean | false          | Auto-start a Pomodoro on every prompt                |
| `auto_start_apps`   | array   | ["claude-code", "codex-cli"] | Which CLIs auto-start applies to       |
| `notify_on_complete`| boolean | true           | Show OS desktop notification when timer ends         |
| `notify_sound`      | boolean | true           | Play an audible alert on completion                  |

Full reference: [docs/CONFIG.md](docs/CONFIG.md).

---

## Commands

All commands use the `/pomodoro` prefix and work inside Claude Code or Codex CLI.

| Command                                | Description                                | Passed to LLM |
|----------------------------------------|--------------------------------------------|---------------|
| `/pomodoro start [minutes] <prompt>`   | Start a session and send the prompt        | Yes           |
| `/pomodoro stop`                       | End the current session early              | No            |
| `/pomodoro status`                     | Show remaining time                        | No            |
| `/pomodoro stats [filter]`             | View focus analytics                       | No            |
| `/pomodoro config [set key value]`     | Read or change settings                    | No            |

For `/pomodoro start`, the prefix is passed through to the LLM along with the prompt text. The LLM sees and handles the full line.

---

## How It Works

```
  User types "/pomodoro start 25 Refactor auth"
         │
         ▼
  ┌──────────────────────────────────┐
  │  Hook Scripts (shell / .bat)     │
  │  ┌─ UserPromptSubmit: writes     │
  │  │  state.json, launches timer   │
  │  ├─ PreToolUse: auto-allows      │
  │  │  tool requests                │
  │  └─ Stop: blocks completion      │
  │       during session             │
  └──────────┬───────────────────────┘
             │ file I/O
             ▼
  ┌──────────────────────────────────┐
  │  TypeScript Core                 │
  │  ┌─ timer.ts  countdown + notify │
  │  ├─ state.ts  read/write state   │
  │  ├─ stats.ts  append/query       │
  │  ├─ config.ts manage config      │
  │  ├─ notify.ts OS alerts          │
  │  └─ cli.ts   user commands       │
  └──────────┬───────────────────────┘
             │ file state
             ▼
  ┌──────────────────────────────────┐
  │  File State (~/.config/cc-pomodoro)│
  │  ├─ state.json     active session │
  │  ├─ sessions.jsonl history        │
  │  └─ config.json    settings       │
  └──────────────────────────────────┘
```

**Three layers, file-backed, no HTTP daemon.** Hook scripts are thin wrappers that read and write JSON files. The TypeScript core runs only when needed -- a lightweight timer process during a session, and stateless CLI commands otherwise. All state lives in `~/.config/cc-pomodoro/` as plain JSON and JSONL files.

---

## Design Decisions

**Why file-backed state instead of an HTTP daemon?**

Simplicity and reliability. A background daemon means a port to reserve, a process to monitor, a crash to handle. File I/O is atomic on all three platforms, trivially debuggable (`cat state.json`), and survives reboots without orchestration. The timer process is a single `sleep` + write -- no event loop, no socket, no lock file.

**Why asymmetry between Claude Code and Codex CLI?**

Codex CLI provides a native `suppressOutput` flag in its hook system, making it straightforward to hide AI output during a session. Claude Code's hook system does not expose equivalent output suppression -- the `Stop` hook fires after rendering is complete. On Claude Code, the tool suppresses notifications and auto-allows tool requests, but the terminal output itself is hidden by the user looking away. This is an accepted asymmetry documented in the project's architecture decisions.

**Why does `auto_start` default to off?**

A Pomodoro is a commitment you make consciously. Autostarting on every prompt would turn the tool into an intrusive gatekeeper rather than a deliberate focus aid. The default respects that you should choose when to focus. If you find yourself starting sessions every time anyway, flip the setting on.

**Why no input-locking or full-screen overlay?**

The tool's philosophy is to protect focus, not enforce it. Locking the keyboard or covering the terminal would make the tool feel like a prison rather than a partner. You are trusted to manage your own attention. The tool removes the AI's ability to interrupt you -- the rest is up to you.

---

## Contributing

Issues and feature requests are welcome. For significant changes, please open a discussion first to align on design and scope.

---

## License

MIT. See [LICENSE](LICENSE).

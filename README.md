# cc-pomodoro

> CLI-native Pomodoro for AI agent workflows. Focus on your deep work — let the AI wait.

---

## What It Looks Like

```
You send a prompt                  You focus on real work         Timer ends, you come back
┌────────────────────┐             ┌────────────────────┐        ┌────────────────────┐
│                    │             │                    │        │                    │
│ > /pomodoro start  │             │   📄 reading       │        │ 🔔 Pomodoro 完成   │
│   25 Refactor auth │             │   a paper          │        │                    │
│                    │  ───────►   │                    │  ───►  │ ── AI Output ────  │
│ 🍅 25min · started │             │   (terminal quiet, │        │ I've refactored    │
│   Switch to deep   │             │    no bell, no     │        │ the auth module... │
│   work.            │             │    popups)         │        │                    │
└────────────────────┘             └────────────────────┘        └────────────────────┘
```

The AI finishes its work silently in the background. Tool approvals pass through automatically. You see nothing until the timer ends — or until you choose to check in.

```
> /pomodoro status         > /pomodoro stop                > /pomodoro stats
                           还剩 14:32，确定结束？[y/N] y     今日专注: 2h 15min
🍅 14:32 · claude-code     Pomodoro 已提前结束               Claude Code  ████████ 1h 50min
(25min)                                                   Codex CLI    ██ 25min
```

---

## Quick Start

```bash
npm install -g cc-pomodoro
cc-pomodoro hooks init --app claude-code    # paste output into .claude/settings.json
```

Then, inside Claude Code or Codex CLI:

```
/pomodoro start 25 Refactor authentication module
```

Full install guide: [docs/INSTALL.md](docs/INSTALL.md).

---

## Features

- **Dispatch-triggered**: Pomodoro starts when you send a prompt. No separate app.
- **Completion shielding**: No bell, no output flood, no notification until the timer ends.
- **Auto-authorization**: Tool-approval requests pass through silently during a session.
- **Soft early-exit**: *"14 min remaining, confirm? [y/N]"* — respects your judgment.
- **Focus analytics**: Per-app daily and weekly summaries via `/pomodoro stats`.
- **Cross-platform**: Claude Code + Codex CLI. macOS, Linux, Windows.

---

## Philosophy

The AI finishes a turn, a notification fires, dopamine hooks, and you tab back — mid-sentence in the paper you were reading. This is the **reactive reflex arc**: AI finishes → notification → switch context → lost flow. cc-pomodoro severs that single arc by silencing the AI's side of the trigger. It does not lock your keyboard or hide your terminal — it trusts you to manage your own attention. It simply removes the strongest external interruption: the AI itself. A Pomodoro session is a **commitment device you opt into**, not an automatic prison.

---

## Commands

| Command                              | Description                        |
|--------------------------------------|------------------------------------|
| `/pomodoro start [min] <prompt>`     | Start session + send prompt        |
| `/pomodoro stop`                     | End session early (with confirm)   |
| `/pomodoro status`                   | Show remaining time                |
| `/pomodoro stats [--json]`           | View focus analytics               |
| `/pomodoro config [set key val]`     | Read or change settings            |

---

## Configuration

`~/.config/cc-pomodoro/config.json` (also editable via `/pomodoro config`):

| Key                  | Type    | Default | Description                        |
|----------------------|---------|---------|------------------------------------|
| `duration`           | int     | 50      | Default session length (minutes)   |
| `auto_start`         | bool    | false   | Auto-start on every prompt         |
| `notify_on_complete` | bool    | true    | OS desktop notification on end     |
| `notify_sound`       | bool    | true    | Audible alert on completion        |

Full reference: [docs/CONFIG.md](docs/CONFIG.md).

---

## How It Works

```
  /pomodoro start 25 Refactor auth
         │
         ▼
  ┌──────────────────────────────────┐
  │  Hook Scripts                    │
  │  UserPromptSubmit → start timer  │
  │  PreToolUse       → auto-allow   │
  │  Stop             → block output │
  └──────────┬───────────────────────┘
             │ file I/O
             ▼
  ┌──────────────────────────────────┐
  │  TypeScript Core                 │
  │  timer · state · stats · config  │
  │  notify · parser · hooks · cli   │
  └──────────┬───────────────────────┘
             │
             ▼
  ~/.config/cc-pomodoro/
  ├── state.json      active session
  ├── sessions.jsonl  history
  └── config.json     settings
```

**File-backed state, zero production dependencies, no HTTP daemon.** Hook scripts are 2-line shells. Core runs only when needed. All state in JSON files.

---

## Design Decisions

**File-backed, not daemon.** No port, no process monitor, no crash recovery. File I/O is atomic, debuggable with `cat`, and survives reboots.

**Asymmetric R2 (output suppression).** Codex CLI has a native `suppressOutput` flag. Claude Code's `Stop` hook fires after terminal rendering. On Claude Code, suppression relies on blocking notifications and trusting the user to look away. Full context in [the PRD](.trellis/tasks/05-15-ai-cli-cc-pomodoro/prd.md).

**`auto_start` off by default.** A Pomodoro is a commitment you make consciously — not a gatekeeper that triggers on every prompt.

---

## Contributing

Issues and PRs welcome. For significant changes, please open a discussion first.

---

## License

MIT. See [LICENSE](LICENSE).

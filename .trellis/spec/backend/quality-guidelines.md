# Quality Guidelines — cc-pomodoro

> Code quality standards for the cc-pomodoro Python project.

---

## Design Decisions

### DD1: File-backed state over HTTP daemon

**Context**: Needed state sharing between stateless hook scripts and background timer process. Initial proposal was an HTTP daemon (localhost:9242).

**Options considered**:
1. HTTP daemon (Flask/aiohttp) — persistent process, port management, Windows firewall popups
2. File-backed state (JSON files) — read/write from disk, no daemon

**Decision**: File-backed state. `state.json` is the single source of truth.

**Why**:
- Zero dependencies (only stdlib `json` + `pathlib`)
- No port conflicts or Windows firewall interference
- Single-user tool — no concurrent-write contention in practice
- Hook scripts are already stateless process invocations

**Consequence**: If the timer process is SIGKILL'd, `state.json` retains `active: true` until `end_at` passes naturally. No recovery for orphaned state — acceptable for single-user tool.

### DD2: Hook scripts as thin shells

**Context**: Hook scripts fire on every UserPromptSubmit / PreToolUse / Stop event. Logic must be testable and cross-platform.

**Decision**: Hook scripts are 2-3 line shells (`.sh` / `.bat`). All logic lives in `cc_pomodoro/hooks.py`.

```
# Hook script (user_prompt_submit.sh):
#!/bin/bash
python -m cc_pomodoro.hooks user_prompt_submit
```

**Why**:
- Python logic is unit-testable (mock state/config)
- Shell scripts can't be easily tested across platforms
- Single implementation for both Claude Code and Codex CLI

### DD3: auto_start defaults to `false`

**Context**: PRD R1 says "auto-start on dispatch", R9 says "don't auto-restart after completion".

**Decision**: `auto_start` defaults to `false`. Users explicitly opt in.

**Why**: The Pomodoro is a commitment device, not an automatic prison. User decides when to focus — the tool doesn't decide for them.

### DD4: Claude Code / Codex CLI R2 asymmetry is accepted

**Context**: Codex CLI has native `suppressOutput` flag in Stop hooks. Claude Code Stop hook fires after output is already rendered — cannot suppress terminal output.

**Decision**: Accept the gap. Codex gets full R2; Claude Code relies on "no bell + no notification + user looks away."

**Why**: Adding a PTY wrapper or stdout redirect contradicts the "zero deps, no wrapper" architecture. Validate whether the gap actually matters in practice (AC8) before adding complexity.

---

## Required Patterns

### P1: Atomic file writes

All state/config/session writes MUST use write-to-tmp-then-rename:

```python
def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)  # atomic on POSIX, near-atomic on Windows
```

**Why**: Prevents partial writes if the process crashes mid-write. The `.tmp` file is harmless if orphaned.

### P2: Zero external dependencies

All production code MUST use only Python stdlib. `pytest` is the only dev dependency.

**Why**: The tool is installed as hook scripts inside Claude Code / Codex CLI config directories. `pip install` with external deps adds failure points.

### P3: Config keys must be defined → implemented → documented

Adding a config key requires three changes in one commit:
1. `DEFAULT_CONFIG` dict in `config.py`
2. Code that reads the key (e.g., `cfg.get("new_key", default)`)
3. Documentation in `docs/CONFIG.md`

**Why**: Config defined but never read is dead weight. Config read but undocumented is invisible to users. The check agent found `notify_on_complete`, `notify_sound`, and `auto_start_apps` all had this gap at PR2.

### P4: Codex CLI hook scripts MUST set `CC_POMODORO_APP=codex-cli`

```bash
#!/bin/bash
export CC_POMODORO_APP=codex-cli
python -m cc_pomodoro.hooks user_prompt_submit
```

The Python hook logic uses this env var to enable `suppressOutput` and other Codex-specific behavior. Claude Code scripts do NOT set this var.

---

## Forbidden Patterns

### Don't: HTTP daemon or persistent server process

The project does NOT need a long-running server. File state + short-lived timer process is sufficient. Adding a server introduces port management, firewall, and lifecycle complexity with no benefit for a single-user tool.

### Don't: Logic in shell scripts

Hook scripts MUST be 2-3 lines. Any decision logic in `.sh`/`.bat` is untestable and duplicates across platforms. Put it in `hooks.py`.

### Don't: Config fallback values that differ from DEFAULT_CONFIG

```python
# WRONG — drift between config.py default and code fallback
cfg.get("auto_start", True)   # config.py says False

# CORRECT
cfg.get("auto_start", False)  # matches DEFAULT_CONFIG
```

**Why**: If DEFAULT_CONFIG changes but fallback values in `dict.get()` calls don't, silent bugs occur. Always use the same value in both places, or import `DEFAULT_CONFIG` and reference `DEFAULT_CONFIG["auto_start"]`.

---

## Testing Requirements

- All `hooks.py` handler functions must be tested with mocked `state` and `config`
- All CLI command functions must be tested via `argparse` parser
- Timer lifecycle tests must cover all three `ended_by` cases (completed, user_stop, process_killed)
- Notify tests must cover all three platform dispatch paths
- Cross-platform: tests must pass on Windows, macOS, and Linux

---

## Code Review Checklist

- [ ] New config key? → Added to DEFAULT_CONFIG + read in code + documented in CONFIG.md
- [ ] New hook script? → Both `.sh` and `.bat` versions exist
- [ ] Codex-specific behavior? → Gated behind `CC_POMODORO_APP=codex-cli` env var check
- [ ] Config fallback values match DEFAULT_CONFIG?
- [ ] Zero new external dependencies?
- [ ] Atomic write used for all file writes?

# Error Handling — cc-pomodoro

> Error handling conventions for the cc-pomodoro Python package.

---

## Design Philosophy

**Fail gracefully, never crash a hook.** If a hook script crashes (exit code ≠ 0), Claude Code/Codex CLI may behave unpredictably — the user's prompt could be silently blocked, or permissions could fail. All hook handler functions MUST catch exceptions and return safe defaults.

---

## Error Handling Patterns

### P1: Hook handlers return safe defaults on failure

```python
def handle_user_prompt_submit(event: dict) -> dict:
    try:
        # ... decision logic ...
        return {"continue": True, ...}
    except Exception:
        # On any failure, let the prompt through (don't block the user)
        return {"continue": True}
```

**Why**: A bug in the Pomodoro tool should never prevent the user from using Claude Code/Codex CLI. The safe default is to pass through.

### P2: Timer process records failure mode

```python
def main():
    try:
        # ... sleep and notify ...
        record = make_record(..., ended_by="completed")
    except KeyboardInterrupt:
        record = make_record(..., ended_by="process_killed")
    except Exception:
        record = make_record(..., ended_by="process_killed")
    finally:
        end_session()
        append_session(record)
```

**Why**: The `ended_by` field distinguishes natural completion from interruption — critical for accurate stats.

### P3: Notification failures are silent

```python
def notify(title: str, message: str) -> None:
    try:
        # ... platform-specific notification ...
    except Exception:
        # Notification is best-effort. Never crash for it.
        pass
```

**Why**: If `notify-send`/`osascript`/PowerShell toast isn't available, the timer still works — just without the desktop ping.

---

## Common Mistakes

### CM1: Config drift — fallback ≠ DEFAULT_CONFIG

**Symptom**: Changing `DEFAULT_CONFIG` doesn't change behavior.

**Cause**: `dict.get()` fallback values in hooks.py / timer.py differ from DEFAULT_CONFIG.

**Fix**: Always import and reference `DEFAULT_CONFIG`, or use `get_config()`:

```python
# WRONG
auto_start = cfg.get("auto_start", True)   # hardcoded fallback

# RIGHT
from cc_pomodoro.config import DEFAULT_CONFIG
auto_start = cfg.get("auto_start", DEFAULT_CONFIG["auto_start"])
```

### CM2: Config key defined but never read

**Symptom**: `notify_sound` in config file has no effect.

**Cause**: Key added to `DEFAULT_CONFIG` + docs, but no code reads it.

**Prevention**: When adding a config key, grep the codebase for all reads:
```bash
grep -r "notify_sound" cc_pomodoro/
```

### CM3: Missing Windows .bat hook script

**Symptom**: Hooks work on macOS/Linux, silently fail on Windows.

**Cause**: `.sh` hook script created but no `.bat` equivalent.

**Prevention**: For every `hooks/**/*.sh`, create a matching `.bat`. The `hooks init` command auto-detects platform and selects the right extension.

### CM4: State file read without empty string guard

**Symptom**: `json.loads("")` raises `JSONDecodeError`.

**Cause**: State/config file exists but is empty (touched but not written).

**Fix**:
```python
raw = path.read_text(encoding="utf-8")
if not raw.strip():
    return {}  # or defaults
return json.loads(raw)
```

---

## Edge Case Matrix

| Scenario | Behavior |
|----------|----------|
| Hook crashes | Return safe default (pass-through), don't block user |
| Timer SIGKILL'd | `state.json` retains `active: true` until `end_at` passes |
| Timer SIGTERM'd | `ended_by="process_killed"`, session recorded |
| Session already ended (double end) | `end_session()` is idempotent, timer skips double-record |
| New session starts during old timer | Old timer detects `session_id` mismatch, exits silently |
| Notification binary missing | `notify()` catches exception, timer continues |
| Config file corrupted | `JSONDecodeError` raised (fail fast, user fixes file) |
| State file empty | Treated as "no active session" |

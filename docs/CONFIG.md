# Configuration Reference

## Config File Location

cc-pomodoro reads configuration from `~/.config/cc-pomodoro/config.json`.

- **macOS / Linux:** `~/.config/cc-pomodoro/config.json`
- **Windows:** `%USERPROFILE%\.config\cc-pomodoro\config.json`

The file and directory are created automatically on first run if they do not exist.

---

## All Configuration Keys

| Key                 | Type    | Default                              | Description                                                   |
|---------------------|---------|--------------------------------------|---------------------------------------------------------------|
| `duration`          | integer | 50                                   | Default session length in minutes. Used when no duration is specified in `/pomodoro start`. |
| `auto_start`        | boolean | false                                | If true, a Pomodoro session starts automatically on every prompt. Set to false by design -- opt in consciously. |
| `auto_start_apps`   | array   | `["claude-code", "codex-cli"]`       | Which CLI applications respect the `auto_start` setting. Add or remove app identifiers to control where auto-start applies. |
| `notify_on_complete`| boolean | true                                 | Show an OS-level desktop notification when the timer reaches zero. |
| `notify_sound`      | boolean | true                                 | Play an audible alert when the timer ends. On macOS this uses the system alert sound; on Linux it uses the terminal bell or `paplay`; on Windows it uses the default system notification sound. |

### Example config.json

```json
{
  "duration": 50,
  "auto_start": false,
  "auto_start_apps": ["claude-code", "codex-cli"],
  "notify_on_complete": true,
  "notify_sound": true
}
```

### Example: short sessions, no notifications

```json
{
  "duration": 15,
  "auto_start": true,
  "auto_start_apps": ["claude-code"],
  "notify_on_complete": false,
  "notify_sound": false
}
```

---

## Using the CLI

You can read and modify configuration directly from within Claude Code or Codex CLI using the `/pomodoro config` command.

### Read current config

```
/pomodoro config
```

Prints the full configuration as formatted JSON.

### Set a value

```
/pomodoro config set duration 25
/pomodoro config set auto_start true
/pomodoro config set notify_sound false
```

Boolean values accept `true` / `false` (lowercase). Array values are set as JSON:

```
/pomodoro config set auto_start_apps '["claude-code"]'
```

### Using the standalone CLI

Outside of Claude Code or Codex CLI, use the `cc-pomodoro config` command:

```bash
cc-pomodoro config          # view current config
cc-pomodoro config set duration 25
```

---

## Per-App Configuration Overrides

The `auto_start_apps` key controls which CLIs are affected by the `auto_start` flag. This provides a basic form of per-app configuration:

- If you want auto-start only in Claude Code but not Codex CLI, set `"auto_start_apps": ["claude-code"]`.
- If you want auto-start in both, set `"auto_start_apps": ["claude-code", "codex-cli"]`.
- To disable auto-start everywhere, set `"auto_start": false` (the default).

Future versions may support full per-app config overrides (different durations per CLI). For now, the single global configuration applies to all apps listed in `auto_start_apps`.

---

## Configuration Precedence

Settings are resolved in the following order (later overrides earlier):

1. **Config file** (`~/.config/cc-pomodoro/config.json`) -- base values.
2. **Explicit command argument** -- `/pomodoro start 25` overrides `duration` for that session only.
3. **Config CLI** (`/pomodoro config set`) -- writes to the config file immediately.

---

## Default Behaviour Summary

With the default configuration, cc-pomodoro:

- Does **not** auto-start on prompts (you must type `/pomodoro start`).
- Uses **50-minute** sessions.
- Notifies you with both a **desktop notification and a sound** when the timer ends.
- Applies auto-start rules to **both Claude Code and Codex CLI** (though auto-start is off by default).

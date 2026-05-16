# Installation Guide

## Prerequisites

- **Node.js 18 or later** installed on your system.
- **npm** (ships with Node.js).
- **Claude Code** and/or **Codex CLI** installed and configured.

Verify your Node.js version:

```bash
node --version
# Should print v18.x.x or higher
```

---

## Install cc-pomodoro

### Via npm (recommended)

```bash
npm install -g cc-pomodoro
```

### From source

```bash
git clone https://github.com/VLooong/cc-pomodoro.git
cd cc-pomodoro
npm install
npm run build
npm link
```

Verify the installation:

```bash
cc-pomodoro --help
```

---

## Configure Hooks

cc-pomodoro uses CLI hook systems to intercept prompts and tool requests during a Pomodoro session. You need to install hook scripts for each CLI you use.

### Claude Code

#### 1. Find your hooks config

Claude Code reads hook configuration from `.claude/settings.json` in your home directory.

- **macOS / Linux:** `~/.claude/settings.json`
- **Windows:** `%USERPROFILE%\.claude\settings.json`

If the file does not exist, create it. If it exists and already has a `hooks` object, merge the new entries into it.

#### 2. Generate the hook configuration

```bash
cc-pomodoro hooks init --app claude-code
```

This prints a JSON configuration block to stdout. The output contains absolute paths to the shell scripts shipped with the package. Example output:

```json
{
  "hooks": {
    "UserPromptSubmit": "/path/to/node_modules/cc-pomodoro/hooks/claude-code/user_prompt_submit.sh",
    "PreToolUse": "/path/to/node_modules/cc-pomodoro/hooks/claude-code/pre_tool_use.sh",
    "Stop": "/path/to/node_modules/cc-pomodoro/hooks/claude-code/stop.sh"
  }
}
```

#### 3. Apply the configuration

Open `~/.claude/settings.json` and add the hooks object. The file should look like this:

```json
{
  "hooks": {
    "UserPromptSubmit": "/path/to/node_modules/cc-pomodoro/hooks/claude-code/user_prompt_submit.sh",
    "PreToolUse": "/path/to/node_modules/cc-pomodoro/hooks/claude-code/pre_tool_use.sh",
    "Stop": "/path/to/node_modules/cc-pomodoro/hooks/claude-code/stop.sh"
  }
}
```

If you already have other hooks, merge the `UserPromptSubmit`, `PreToolUse`, and `Stop` entries into the existing `hooks` object.

#### 4. Verify

1. Start Claude Code.
2. Send a prompt: `/pomodoro status`
3. You should see the current timer status (or "No active session").

---

### Codex CLI

#### 1. Find your hooks config

Codex CLI reads hook configuration from a JSON file in its config directory.

- **macOS / Linux:** `~/.config/codex-cli/hooks.json`
- **Windows:** `%USERPROFILE%\.config\codex-cli\hooks.json`

If the file does not exist, create it.

#### 2. Generate the hook configuration

```bash
cc-pomodoro hooks init --app codex-cli
```

This prints a JSON configuration block to stdout using Codex CLI's hook schema.

#### 3. Apply the configuration

Write the JSON output into your Codex CLI hooks file. The exact format will be printed by the `hooks init` command.

#### 4. Verify

1. Start Codex CLI.
2. Send a prompt: `/pomodoro status`
3. You should see the current timer status.

---

## Platform Notes

### macOS

- Desktop notifications use `osascript` (native macOS notification center).
- All hook scripts are POSIX shell (`.sh`).

### Linux

- Desktop notifications use `notify-send` (requires `libnotify`).
- All hook scripts are POSIX shell (`.sh`).

### Windows

- Desktop notifications use PowerShell Toast notifications.
- Hook scripts are available as `.bat` wrappers (in addition to the POSIX shell scripts).
- If you are using Git Bash or WSL, the POSIX shell scripts also work.
- File paths use forward slashes or escaped backslashes in the settings JSON.

---

## Next Steps

- Read the [Configuration Guide](CONFIG.md) for all available settings.
- Start a session: `/pomodoro start 25 Your prompt here`
- Check your stats: `/pomodoro stats`

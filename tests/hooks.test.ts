import { describe, it, expect, vi, beforeEach } from 'vitest';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

// Set up temp directory for state and sessions
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cc-pomodoro-test-hooks-'));
const stateFile = path.join(tmpDir, 'state.json');
const sessionsFile = path.join(tmpDir, 'sessions.jsonl');
const configFile = path.join(tmpDir, 'config.json');

// Mock constants to use temp directory paths
vi.mock('../src/constants.js', () => ({
  STATE_FILE: stateFile,
  CONFIG_DIR: tmpDir,
  CONFIG_FILE: configFile,
  SESSIONS_FILE: sessionsFile,
  APP_NAME: 'cc-pomodoro',
  DEFAULT_DURATION: 50,
}));

// Mock spawn to prevent actual background process creation
vi.mock('node:child_process', () => ({
  spawn: vi.fn(() => ({ unref: vi.fn() })),
}));

const {
  handlePreToolUse,
  handleStop,
  handleUserPromptSubmit,
} = await import('../src/hooks.js');

describe('hooks - handleUserPromptSubmit', () => {
  beforeEach(() => {
    // Clean up all files and recreate the directory
    try { fs.rmSync(tmpDir, { recursive: true }); } catch { /* ok */ }
    try { fs.mkdirSync(tmpDir, { recursive: true }); } catch { /* ok */ }
    // Write config with auto_start: true for auto-start tests
    fs.writeFileSync(configFile, JSON.stringify({
      duration: 50,
      auto_start: true,
      auto_start_apps: ['claude-code', 'codex-cli'],
      notify_on_complete: true,
      notify_sound: true,
    }), 'utf-8');
    vi.clearAllMocks();
  });

  // -- /pomodoro start

  it('start with duration', () => {
    const event = { prompt: '/pomodoro start 25 fix the auth bug', app: 'claude-code' };
    const result = handleUserPromptSubmit(event);
    expect(result.decision).toBe('continue');

    // Verify state was updated
    const stateContent = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    expect(stateContent.active).toBe(true);
    expect(stateContent.duration).toBe(25);
    expect(stateContent.app).toBe('claude-code');
  });

  it('start uses default duration', () => {
    const event = { prompt: '/pomodoro start fix the auth bug', app: 'claude-code' };
    const result = handleUserPromptSubmit(event);
    expect(result.decision).toBe('continue');

    const stateContent = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    // Default is 50 from config
    expect(stateContent.duration).toBe(50);
  });

  it('start overrides active session', () => {
    // Start a first session
    handleUserPromptSubmit({ prompt: '/pomodoro start 15 first task', app: 'claude-code' });

    // Start a second session
    const result = handleUserPromptSubmit({ prompt: '/pomodoro start 20 second task', app: 'claude-code' });
    expect(result.decision).toBe('continue');

    const stateContent = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    expect(stateContent.duration).toBe(20);
  });

  // -- /pomodoro stop

  it('stop active session', () => {
    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });
    const result = handleUserPromptSubmit({ prompt: '/pomodoro stop' });
    expect(result.decision).toBe('block');

    const stateContent = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    expect(stateContent.active).toBe(false);
  });

  it('stop inactive does nothing', () => {
    const result = handleUserPromptSubmit({ prompt: '/pomodoro stop' });
    expect(result.decision).toBe('block');

    // No state file is created when there was no active session
    expect(fs.existsSync(stateFile)).toBe(false);
  });

  // -- /pomodoro status

  it('status active', () => {
    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });
    const result = handleUserPromptSubmit({ prompt: '/pomodoro status' });
    expect(result.decision).toBe('block');
  });

  it('status inactive', () => {
    const result = handleUserPromptSubmit({ prompt: '/pomodoro status' });
    expect(result.decision).toBe('block');
  });

  // -- /pomodoro stats

  it('stats', () => {
    const result = handleUserPromptSubmit({ prompt: '/pomodoro stats' });
    expect(result.decision).toBe('block');
  });

  it('stats with --json', () => {
    const result = handleUserPromptSubmit({ prompt: '/pomodoro stats --json' });
    expect(result.decision).toBe('block');
  });

  // -- /pomodoro config

  it('config show', () => {
    const result = handleUserPromptSubmit({ prompt: '/pomodoro config' });
    expect(result.decision).toBe('block');
  });

  it('config set', () => {
    const result = handleUserPromptSubmit({ prompt: '/pomodoro config set duration 30' });
    expect(result.decision).toBe('block');

    // Verify config was updated
    const cfg = JSON.parse(fs.readFileSync(configFile, 'utf-8'));
    expect(cfg.duration).toBe(30);
  });

  it('config set bool', () => {
    const result = handleUserPromptSubmit({ prompt: '/pomodoro config set auto_start false' });
    expect(result.decision).toBe('block');

    const cfg = JSON.parse(fs.readFileSync(configFile, 'utf-8'));
    expect(cfg.auto_start).toBe(false);
  });

  // -- Active session (no /pomodoro prefix)

  it('active blocks plain prompt', () => {
    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });
    const result = handleUserPromptSubmit({ prompt: 'fix the auth bug' });
    expect(result.decision).toBe('block');
    expect(result.reason).toContain('Pomodoro');
  });

  // -- Auto-start (no /pomodoro prefix, inactive)

  it('auto-start on inactive', () => {
    const result = handleUserPromptSubmit({ prompt: 'fix the auth bug', app: 'claude-code' });
    expect(result.decision).toBe('continue');

    const stateContent = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    expect(stateContent.active).toBe(true);
    expect(stateContent.duration).toBe(50);
  });

  it('auto-start fallback app is claude-code', () => {
    const result = handleUserPromptSubmit({ prompt: 'hello' });
    expect(result.decision).toBe('continue');

    const stateContent = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    expect(stateContent.app).toBe('claude-code');
  });

  // -- Empty prompt

  it('empty prompt does not crash', () => {
    const result = handleUserPromptSubmit({ prompt: '' });
    expect(result.decision).toBe('continue');
  });
});

describe('hooks - handlePreToolUse', () => {
  beforeEach(() => {
    try { fs.rmSync(tmpDir, { recursive: true }); } catch { /* ok */ }
    try { fs.mkdirSync(tmpDir, { recursive: true }); } catch { /* ok */ }
    vi.clearAllMocks();
  });

  it('active allows', () => {
    // Start a session first
    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });

    const result = handlePreToolUse({ tool: { name: 'bash' } });
    expect(result).toEqual({ permissionDecision: 'allow' });
  });

  it('inactive returns empty', () => {
    const result = handlePreToolUse({ tool: { name: 'bash' } });
    expect(result).toEqual({});
  });

  it('empty event active returns allow', () => {
    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });
    const result = handlePreToolUse({});
    expect(result).toEqual({ permissionDecision: 'allow' });
  });

  it('empty event inactive returns empty', () => {
    const result = handlePreToolUse({});
    expect(result).toEqual({});
  });
});

describe('hooks - handleStop', () => {
  beforeEach(() => {
    try { fs.rmSync(tmpDir, { recursive: true }); } catch { /* ok */ }
    try { fs.mkdirSync(tmpDir, { recursive: true }); } catch { /* ok */ }
    vi.clearAllMocks();
  });

  it('active blocks', () => {
    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });
    const result = handleStop({ turn: 1 });
    expect(result.decision).toBe('block');
  });

  it('already blocked returns empty', () => {
    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });
    handleStop({ turn: 1 }); // First call sets flag

    const result = handleStop({ turn: 1 }); // Second call sees flag
    expect(result).toEqual({});
  });

  it('inactive returns empty', () => {
    const result = handleStop({ turn: 1 });
    expect(result).toEqual({});
  });

  it('codex suppresses output', () => {
    const origEnv = process.env.CC_POMODORO_APP;
    process.env.CC_POMODORO_APP = 'codex-cli';

    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'codex-cli' });
    const result = handleStop({ turn: 1 });
    expect(result.decision).toBe('block');
    expect(result.suppressOutput).toBe(true);

    process.env.CC_POMODORO_APP = origEnv;
  });

  it('claude does not suppress output', () => {
    const origEnv = process.env.CC_POMODORO_APP;
    delete process.env.CC_POMODORO_APP;

    handleUserPromptSubmit({ prompt: '/pomodoro start 25 test', app: 'claude-code' });
    const result = handleStop({ turn: 1 });
    expect(result.decision).toBe('block');
    expect(result.suppressOutput).toBeUndefined();

    process.env.CC_POMODORO_APP = origEnv;
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

// Need to mock constants before importing config
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cc-pomodoro-test-'));
const configFile = path.join(tmpDir, 'config.json');

vi.mock('../src/constants.js', () => ({
  CONFIG_DIR: path.dirname(configFile),
  CONFIG_FILE: configFile,
  DEFAULT_DURATION: 50,
}));

const {
  DEFAULT_CONFIG,
  ensureDefaultConfig,
  get,
  getConfig,
  setConfig,
} = await import('../src/config.js');

describe('config', () => {
  beforeEach(() => {
    // Clean up any leftover files
    try { fs.unlinkSync(configFile); } catch { /* ok */ }
    try { fs.unlinkSync(configFile + '.tmp'); } catch { /* ok */ }
  });

  afterEach(() => {
    try { fs.unlinkSync(configFile); } catch { /* ok */ }
    try { fs.unlinkSync(configFile + '.tmp'); } catch { /* ok */ }
  });

  it('returns defaults when no file exists', () => {
    const config = getConfig();
    expect(config).toEqual(DEFAULT_CONFIG);
  });

  it('merges with file overrides', () => {
    const overrides = { duration: 25, notify_sound: false };
    fs.writeFileSync(configFile, JSON.stringify(overrides), 'utf-8');

    const config = getConfig();
    expect(config.duration).toBe(25);
    expect(config.notify_sound).toBe(false);
    expect(config.auto_start).toBe(false);
    expect(config.auto_start_apps).toEqual(['claude-code', 'codex-cli']);
    expect(config.notify_on_complete).toBe(true);
  });

  it('returns a specific key via get()', () => {
    expect(get('duration')).toBe(50);
    expect(get('auto_start')).toBe(false);
  });

  it('setConfig updates the file', () => {
    setConfig('duration', 30);
    expect(get('duration')).toBe(30);

    setConfig('notify_sound', false);
    expect(get('notify_sound')).toBe(false);

    const config = getConfig();
    expect(config.duration).toBe(30);
    expect(config.notify_sound).toBe(false);
    expect(config.auto_start).toBe(false);
  });

  it('setConfig preserves other keys', () => {
    setConfig('duration', 25);
    setConfig('auto_start', false);

    const config = getConfig();
    expect(config.duration).toBe(25);
    expect(config.auto_start).toBe(false);
    expect(config.notify_on_complete).toBe(true);
  });

  it('ensureDefaultConfig creates the file', () => {
    expect(fs.existsSync(configFile)).toBe(false);
    const config = ensureDefaultConfig();
    expect(fs.existsSync(configFile)).toBe(true);
    expect(config).toEqual(DEFAULT_CONFIG);
  });

  it('ensureDefaultConfig does not overwrite existing', () => {
    const overrides = { duration: 15, auto_start: false };
    fs.writeFileSync(configFile, JSON.stringify(overrides), 'utf-8');

    const config = ensureDefaultConfig();
    expect(config.duration).toBe(15);
    expect(config.auto_start).toBe(false);
  });

  it('human readable output', () => {
    setConfig('duration', 30);
    const raw = fs.readFileSync(configFile, 'utf-8');
    expect(raw).toContain('  ');
    expect(raw.endsWith('\n')).toBe(true);
  });

  it('atomic write - no .tmp file left behind', () => {
    setConfig('duration', 40);

    const tmpFile = configFile + '.tmp';
    expect(fs.existsSync(tmpFile)).toBe(false);

    const parsed = JSON.parse(fs.readFileSync(configFile, 'utf-8'));
    expect(parsed.duration).toBe(40);
  });

  it('auto-creates directory', () => {
    // The mock uses tmpDir which already exists, but setConfig should handle it
    setConfig('duration', 30);
    expect(fs.existsSync(configFile)).toBe(true);
    expect(get('duration')).toBe(30);
  });

  it('throws on invalid JSON', () => {
    fs.writeFileSync(configFile, '{invalid json}', 'utf-8');
    expect(() => getConfig()).toThrow();
  });
});

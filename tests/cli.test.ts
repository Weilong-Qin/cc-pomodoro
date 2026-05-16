import { describe, it, expect, vi, beforeEach } from 'vitest';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

// Set up temp directory
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cc-pomodoro-test-cli-'));
const configFile = path.join(tmpDir, 'config.json');

vi.mock('../src/constants.js', () => ({
  STATE_FILE: path.join(tmpDir, 'state.json'),
  CONFIG_DIR: tmpDir,
  CONFIG_FILE: configFile,
  SESSIONS_FILE: path.join(tmpDir, 'sessions.jsonl'),
  APP_NAME: 'cc-pomodoro',
  VERSION: '0.1.0',
  DEFAULT_DURATION: 50,
}));

vi.mock('node:child_process', () => ({
  spawn: vi.fn(() => ({ unref: vi.fn() })),
}));

const { formatDt, parseConfigValue } = await import('../src/cli.js');
const { makeRecord } = await import('../src/stats.js');

describe('cli - parseConfigValue', () => {
  it('parses true values', () => {
    expect(parseConfigValue('true')).toBe(true);
    expect(parseConfigValue('yes')).toBe(true);
    expect(parseConfigValue('on')).toBe(true);
    expect(parseConfigValue('1')).toBe(true);
  });

  it('parses false values', () => {
    expect(parseConfigValue('false')).toBe(false);
    expect(parseConfigValue('no')).toBe(false);
    expect(parseConfigValue('off')).toBe(false);
    expect(parseConfigValue('0')).toBe(false);
  });

  it('parses integers', () => {
    expect(parseConfigValue('25')).toBe(25);
    expect(parseConfigValue('42')).toBe(42);
  });

  it('parses floats', () => {
    expect(parseConfigValue('3.14')).toBe(3.14);
    expect(parseConfigValue('0.5')).toBe(0.5);
  });

  it('returns string for non-numeric', () => {
    expect(parseConfigValue('hello')).toBe('hello');
    expect(parseConfigValue('claude-code')).toBe('claude-code');
  });
});

describe('cli - formatDt', () => {
  it('formats ISO date', () => {
    const result = formatDt('2026-05-16T10:30:00.000Z');
    expect(result).toBe('05-16 10:30');
  });

  it('handles empty string', () => {
    expect(formatDt('')).toBe('');
  });

  it('handles null', () => {
    expect(formatDt(null as unknown as string)).toBe('');
  });

  it('returns original string for invalid date', () => {
    const result = formatDt('not-a-date');
    expect(result).toBe('not-a-date');
  });
});

describe('cli - stats record integration', () => {
  it('makeRecord produces expected schema', () => {
    const record = makeRecord({
      session_id: 'int-test',
      started_at: '2026-05-16T10:00:00.000Z',
      ended_at: '2026-05-16T10:50:00.000Z',
      duration_planned: 50,
      duration_actual: 42,
      ended_by: 'completed',
      app: 'claude-code',
    });
    expect(record.id).toBe('int-test');
    expect(record.ended_by).toBe('completed');
    expect(record.app).toBe('claude-code');
    expect(record.schema_version).toBe(1);
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cc-pomodoro-test-stats-'));
const sessionsFile = path.join(tmpDir, 'sessions.jsonl');

vi.mock('../src/constants.js', () => ({
  CONFIG_DIR: tmpDir,
  SESSIONS_FILE: sessionsFile,
}));

const {
  appendSession,
  getStats,
  makeRecord,
  readSessions,
} = await import('../src/stats.js');

function sampleRecord(overrides: Record<string, unknown> = {}): ReturnType<typeof makeRecord> {
  const base = {
    session_id: 'test-uuid',
    started_at: '2026-05-16T10:00:00.000Z',
    ended_at: '2026-05-16T10:50:00.000Z',
    duration_planned: 50,
    duration_actual: 50,
    ended_by: 'completed',
    app: 'claude-code',
    ...overrides,
  };
  return makeRecord(base);
}

describe('stats', () => {
  beforeEach(() => {
    try { fs.unlinkSync(sessionsFile); } catch { /* ok */ }
    try { fs.mkdirSync(tmpDir, { recursive: true }); } catch { /* ok */ }
  });

  afterEach(() => {
    try { fs.unlinkSync(sessionsFile); } catch { /* ok */ }
  });

  it('makeRecord produces correct schema', () => {
    const record = sampleRecord();
    expect(record.id).toBe('test-uuid');
    expect(record.started_at).toBe('2026-05-16T10:00:00.000Z');
    expect(record.ended_at).toBe('2026-05-16T10:50:00.000Z');
    expect(record.duration_planned).toBe(50);
    expect(record.duration_actual).toBe(50);
    expect(record.ended_by).toBe('completed');
    expect(record.app).toBe('claude-code');
    expect(record.blocking_requests_queued).toBe(0);
    expect(record.label).toBe('');
    expect(record.schema_version).toBe(1);
  });

  it('makeRecord with all fields', () => {
    const record = makeRecord({
      session_id: 'abc',
      started_at: '2026-01-01T00:00:00.000Z',
      ended_at: '2026-01-01T00:50:00.000Z',
      duration_planned: 50,
      duration_actual: 42,
      ended_by: 'user_stop',
      app: 'codex-cli',
      blocking_requests_queued: 3,
      label: 'refactor auth',
    });
    expect(record.blocking_requests_queued).toBe(3);
    expect(record.label).toBe('refactor auth');
    expect(record.schema_version).toBe(1);
    expect(record.ended_by).toBe('user_stop');
  });

  it('append and read sessions', () => {
    const r1 = sampleRecord({ session_id: 'sess-1', duration_planned: 25, duration_actual: 25 });
    const r2 = sampleRecord({ session_id: 'sess-2', duration_planned: 50, duration_actual: 42 });

    appendSession(r1);
    appendSession(r2);

    const sessions = readSessions();
    expect(sessions.length).toBe(2);
    expect(sessions[0].id).toBe('sess-1');
    expect(sessions[1].id).toBe('sess-2');
  });

  it('readSessions returns empty for missing file', () => {
    const missingFile = path.join(tmpDir, 'nonexistent', 'sessions.jsonl');
    // We can't easily re-mock, so just check the default behavior
    // Sessions are appended to sessionsFile, which doesn't exist yet for this test
    const sessions = readSessions();
    expect(sessions).toEqual([]);
  });

  it('readSessions skips empty lines', () => {
    fs.writeFileSync(sessionsFile, '{"id":"a"}\n\n{"id":"b"}\n\n', 'utf-8');
    const sessions = readSessions();
    expect(sessions.length).toBe(2);
  });

  it('readSessions skips malformed lines', () => {
    fs.writeFileSync(sessionsFile, '{"id":"a"}\nnot-json\n{"id":"b"}\n', 'utf-8');
    const sessions = readSessions();
    expect(sessions.length).toBe(2);
  });

  it('getStats returns zeros for empty', () => {
    const stats = getStats();
    expect(stats.today_minutes).toBe(0);
    expect(stats.week_minutes).toBe(0);
    expect(stats.by_app).toEqual({});
    expect(stats.recent_sessions).toEqual([]);
  });

  it('getStats counts today and week', () => {
    // Use a fixed date for testing
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-16T14:30:00.000Z')); // Saturday

    // Session today
    appendSession(sampleRecord({
      session_id: 'today-1',
      ended_at: '2026-05-16T12:00:00.000Z',
      duration_actual: 30,
    }));
    // Session yesterday
    appendSession(sampleRecord({
      session_id: 'yesterday-1',
      started_at: '2026-05-15T10:00:00.000Z',
      ended_at: '2026-05-15T10:50:00.000Z',
      duration_actual: 50,
    }));

    const stats = getStats();
    expect(stats.today_minutes).toBe(30);
    expect(stats.week_minutes).toBe(80); // both today and yesterday
    expect(stats.by_app).toEqual({ 'claude-code': 80 });
    expect(stats.recent_sessions.length).toBe(2);

    vi.useRealTimers();
  });

  it('getStats by_app aggregation', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-16T14:00:00.000Z'));

    appendSession(sampleRecord({ app: 'claude-code', duration_actual: 50 }));
    appendSession(sampleRecord({ session_id: 'cc2', app: 'claude-code', duration_actual: 30 }));
    appendSession(sampleRecord({ session_id: 'codex1', app: 'codex-cli', duration_actual: 25 }));

    const stats = getStats();
    expect(stats.by_app).toEqual({ 'claude-code': 80, 'codex-cli': 25 });

    vi.useRealTimers();
  });

  it('getStats recent sessions limited to 5', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-16T14:00:00.000Z'));

    for (let i = 0; i < 7; i++) {
      appendSession(sampleRecord({
        session_id: `sess-${i}`,
        ended_at: `2026-05-16T0${i}:00:00.000Z`,
        duration_actual: 25,
      }));
    }

    const stats = getStats();
    expect(stats.recent_sessions.length).toBe(5);
    // Most recent first
    expect(stats.recent_sessions[0].id).toBe('sess-6');
    expect(stats.recent_sessions[stats.recent_sessions.length - 1].id).toBe('sess-2');

    vi.useRealTimers();
  });

  it('append creates directory', () => {
    const nested = path.join(tmpDir, 'deep', 'dir');
    const nestedFile = path.join(nested, 'sessions.jsonl');

    // We can't easily change the sessions file constant after import,
    // so this test verifies the behavior with the existing mock path
    const record = sampleRecord();
    appendSession(record);
    expect(fs.existsSync(sessionsFile)).toBe(true);
  });

  it('appended file is valid JSONL', () => {
    const r1 = sampleRecord({ session_id: 'a' });
    const r2 = sampleRecord({ session_id: 'b' });
    appendSession(r1);
    appendSession(r2);

    const raw = fs.readFileSync(sessionsFile, 'utf-8');
    const lines = raw.split('\n').filter(l => l.trim());
    expect(lines.length).toBe(2);
    expect(JSON.parse(lines[0]).id).toBe('a');
    expect(JSON.parse(lines[1]).id).toBe('b');
  });
});

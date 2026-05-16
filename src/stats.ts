import fs from 'node:fs';
import { CONFIG_DIR, SESSIONS_FILE } from './constants.js';

export interface SessionRecord {
  id: string;
  started_at: string;
  ended_at: string;
  duration_planned: number;
  duration_actual: number;
  ended_by: string;
  app: string;
  blocking_requests_queued: number;
  label: string;
  schema_version: number;
}

export interface MakeRecordParams {
  session_id: string;
  started_at: string;
  ended_at: string;
  duration_planned: number;
  duration_actual: number;
  ended_by: string;
  app: string;
  blocking_requests_queued?: number;
  label?: string;
}

export interface StatsResult {
  today_minutes: number;
  week_minutes: number;
  by_app: Record<string, number>;
  recent_sessions: SessionRecord[];
}

/**
 * Create a session record dict following the stats schema.
 *
 * Schema version 1 fields:
 *   - id: unique session identifier (uuid)
 *   - started_at: ISO-8601 timestamp when the session began
 *   - ended_at: ISO-8601 timestamp when the session ended
 *   - duration_planned: planned duration in minutes
 *   - duration_actual: actual elapsed minutes
 *   - ended_by: "completed" | "user_stop" | "process_killed"
 *   - app: application name (e.g. "claude-code", "codex-cli")
 *   - blocking_requests_queued: number of blocked tool requests
 *   - label: optional user label
 *   - schema_version: 1
 */
export function makeRecord(params: MakeRecordParams): SessionRecord {
  return {
    id: params.session_id,
    started_at: params.started_at,
    ended_at: params.ended_at,
    duration_planned: params.duration_planned,
    duration_actual: params.duration_actual,
    ended_by: params.ended_by,
    app: params.app,
    blocking_requests_queued: params.blocking_requests_queued ?? 0,
    label: params.label ?? '',
    schema_version: 1,
  };
}

/**
 * Append one JSON line to sessions.jsonl.
 * Creates the config directory and file if they do not exist.
 */
export function appendSession(record: SessionRecord): void {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
  const line = JSON.stringify(record) + '\n';
  fs.appendFileSync(SESSIONS_FILE, line, 'utf-8');
}

/**
 * Read all session records from sessions.jsonl.
 * Returns an empty list if the file does not exist or is empty.
 * Silently skips empty or malformed lines.
 */
export function readSessions(): SessionRecord[] {
  if (!fs.existsSync(SESSIONS_FILE)) {
    return [];
  }

  const sessions: SessionRecord[] = [];
  const raw = fs.readFileSync(SESSIONS_FILE, 'utf-8');
  for (const line of raw.split('\n')) {
    const stripped = line.trim();
    if (!stripped) continue;
    try {
      sessions.push(JSON.parse(stripped) as SessionRecord);
    } catch {
      // Skip malformed lines silently
    }
  }
  return sessions;
}

/**
 * Aggregate statistics from all recorded sessions.
 *
 * Returns an object with:
 *   - today_minutes: total actual minutes spent today (UTC)
 *   - week_minutes: total actual minutes this week (UTC, Mon-Sun)
 *   - by_app: {app_name: total_minutes}
 *   - recent_sessions: last 5 sessions sorted by ended_at descending
 */
export function getStats(): StatsResult {
  const sessions = readSessions();
  if (sessions.length === 0) {
    return {
      today_minutes: 0,
      week_minutes: 0,
      by_app: {},
      recent_sessions: [],
    };
  }

  const now = new Date();
  const todayStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 0, 0, 0, 0));
  const daysSinceMonday = todayStart.getUTCDay() === 0 ? 6 : todayStart.getUTCDay() - 1;
  const weekStart = new Date(todayStart.getTime() - daysSinceMonday * 86400000);

  let todayMinutes = 0;
  let weekMinutes = 0;
  const byApp: Record<string, number> = {};

  for (const s of sessions) {
    const endedAtStr = s.ended_at;
    if (!endedAtStr) continue;
    let endedAt: Date;
    try {
      endedAt = new Date(endedAtStr);
      if (isNaN(endedAt.getTime())) continue;
    } catch {
      continue;
    }

    const durationActual = s.duration_actual || 0;
    const appName = s.app || 'unknown';

    if (endedAt >= todayStart) {
      todayMinutes += durationActual;
    }
    if (endedAt >= weekStart) {
      weekMinutes += durationActual;
    }

    byApp[appName] = (byApp[appName] || 0) + durationActual;
  }

  // Last 5 sessions sorted by ended_at descending
  const sortedSessions = [...sessions]
    .sort((a, b) => {
      const aEnd = a.ended_at || '';
      const bEnd = b.ended_at || '';
      return bEnd.localeCompare(aEnd);
    })
    .slice(0, 5);

  return {
    today_minutes: todayMinutes,
    week_minutes: weekMinutes,
    by_app: byApp,
    recent_sessions: sortedSessions,
  };
}

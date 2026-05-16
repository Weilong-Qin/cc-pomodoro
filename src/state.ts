import crypto from 'node:crypto';
import fs from 'node:fs';
import { STATE_FILE } from './constants.js';
import { atomicWrite, ensureConfigDir } from './config.js';

export interface State {
  active: boolean;
  session_id: string | null;
  started_at: string | null;
  end_at: string | null;
  duration: number;
  app: string | null;
  [key: string]: unknown;
}

function defaultState(): State {
  return {
    active: false,
    session_id: null,
    started_at: null,
    end_at: null,
    duration: 0,
    app: null,
  };
}

/**
 * Read the current state from disk.
 */
export function getState(): State {
  if (fs.existsSync(STATE_FILE)) {
    const raw = fs.readFileSync(STATE_FILE, 'utf-8').trim();
    if (raw) {
      return JSON.parse(raw) as State;
    }
  }
  return defaultState();
}

/**
 * Return true if a session is active and has not expired.
 */
export function isActive(): boolean {
  const state = getState();
  if (!state.active) return false;
  const remaining = getRemainingSeconds();
  return remaining > 0;
}

/**
 * Return remaining seconds for the active session (0 if no active session).
 */
export function getRemainingSeconds(): number {
  const state = getState();
  if (!state.active || !state.end_at) return 0;
  try {
    const endAt = new Date(state.end_at).getTime();
    const now = Date.now();
    return Math.max(0, Math.floor((endAt - now) / 1000));
  } catch {
    return 0;
  }
}

/**
 * Get the current session ID, or null if no session.
 */
export function getSessionId(): string | null {
  return getState().session_id;
}

/**
 * Start a new session, writing state to disk.
 * Returns the generated session UUID.
 */
export function startSession(durationMin: number, app: string): string {
  const sessionId = crypto.randomUUID();
  const now = new Date();
  const startedAt = now.toISOString();
  const endAt = new Date(now.getTime() + durationMin * 60 * 1000).toISOString();
  const state: State = {
    active: true,
    session_id: sessionId,
    started_at: startedAt,
    end_at: endAt,
    duration: durationMin,
    app,
  };
  ensureConfigDir();
  atomicWrite(STATE_FILE, JSON.stringify(state, null, 2) + '\n');
  return sessionId;
}

/**
 * End the current session (mark active=false).
 */
export function endSession(): State {
  const state = getState();
  state.active = false;
  ensureConfigDir();
  atomicWrite(STATE_FILE, JSON.stringify(state, null, 2) + '\n');
  return state;
}

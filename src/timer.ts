/**
 * Background countdown timer process.
 *
 * Usage:
 *   node dist/timer.mjs --duration 25 --session-id xxx --app claude-code
 *
 * Spawns no output.  Waits for the given duration, then:
 *   - Shows an OS desktop notification
 *   - Ends the session in state.json
 *   - Appends a session record to sessions.jsonl
 *
 * Handles SIGTERM / SIGINT gracefully and detects if the session
 * was already ended externally (e.g. via ``/pomodoro stop``).
 */

import process from 'node:process';
import { getConfig } from './config.js';
import { notify } from './notify.js';
import { endSession, getState } from './state.js';
import { appendSession, makeRecord } from './stats.js';

interface TimerArgs {
  duration: number;
  sessionId: string;
  app: string;
}

function parseArgs(argv: string[]): TimerArgs {
  const args: Record<string, string> = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const value = argv[++i];
      if (value === undefined) {
        console.error(`Missing value for --${key}`);
        process.exit(1);
      }
      args[key] = value;
    }
  }

  const duration = parseInt(args.duration, 10);
  if (isNaN(duration)) {
    console.error('Missing or invalid --duration');
    process.exit(1);
  }
  if (!args['session-id']) {
    console.error('Missing --session-id');
    process.exit(1);
  }
  if (!args.app) {
    console.error('Missing --app');
    process.exit(1);
  }

  return {
    duration,
    sessionId: args['session-id'],
    app: args.app,
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function main(): Promise<void> {
  const args = parseArgs(process.argv);
  let interrupted = false;

  const onSignal = (): void => {
    interrupted = true;
  };

  process.on('SIGTERM', onSignal);
  process.on('SIGINT', onSignal);

  try {
    const endTime = Date.now() + args.duration * 60 * 1000;
    while (Date.now() < endTime) {
      if (interrupted) break;
      const remaining = endTime - Date.now();
      await sleep(Math.min(1000, remaining));
    }
  } catch {
    interrupted = true;
  }

  // Snapshot state before any mutation
  const state = getState();
  const startedAt: string = state.started_at ?? '';
  const currentSessionId: string | null = state.session_id ?? null;

  // Session was replaced by a different one -- our work is done
  if (currentSessionId !== args.sessionId) {
    process.exit(0);
  }

  const alreadyEnded: boolean = !state.active;

  let endedBy: string;
  if (alreadyEnded) {
    endedBy = 'user_stop';
  } else {
    if (interrupted) {
      endedBy = 'process_killed';
    } else {
      endedBy = 'completed';
      const cfg = getConfig();
      if (cfg.notify_on_complete) {
        notify('Pomodoro 完成', `${args.duration} 分钟专注结束`);
      }
      if (cfg.notify_sound) {
        // Terminal bell (cross-platform audible alert)
        process.stderr.write('\x07');
      }
    }
    endSession();
  }

  // Calculate actual duration from the started_at timestamp
  const now = new Date();
  let durationActual = 0;
  if (startedAt) {
    try {
      const startedDt = new Date(startedAt);
      const elapsed = (now.getTime() - startedDt.getTime()) / 1000;
      durationActual = Math.max(0, Math.floor(elapsed / 60));
    } catch {
      durationActual = args.duration;
    }
  }

  const record = makeRecord({
    session_id: args.sessionId,
    started_at: startedAt,
    ended_at: now.toISOString(),
    duration_planned: args.duration,
    duration_actual: durationActual,
    ended_by: endedBy,
    app: args.app,
  });
  appendSession(record);
}

// Allow running directly
if (process.argv[1] && (process.argv[1].endsWith('timer.js') || process.argv[1].endsWith('timer.ts'))) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

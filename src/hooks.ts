/**
 * Hook decision logic for Claude Code and Codex CLI hook events.
 *
 * This module provides one function per hook event type.  Each function
 * receives the event object (parsed from the JSON the CLI sends on stdin)
 * and returns a decision object that the CLI interprets.
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import * as config from './config.js';
import { STATE_FILE } from './constants.js';
import { parsePomodoroCommand } from './parser.js';
import {
  endSession,
  getRemainingSeconds,
  getState,
  isActive,
  startSession,
} from './state.js';
import { getStats, readSessions } from './stats.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STOP_HOOK_KEY = '_stop_hook_blocked';

function _isCodex(): boolean {
  return (process.env.CC_POMODORO_APP ?? '').toLowerCase() === 'codex-cli';
}

function _writeState(state: Record<string, unknown>): void {
  config.ensureConfigDir();
  config.atomicWrite(STATE_FILE, JSON.stringify(state, null, 2) + '\n');
}

function _spawnTimer(duration: number, sessionId: string, app: string): void {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const timerPath = path.resolve(__dirname, 'timer.js');

  const child = spawn(
    process.execPath,
    [timerPath, '--duration', String(duration), '--session-id', sessionId, '--app', app],
    {
      stdio: 'ignore',
      detached: true,
      windowsHide: true,
    },
  );
  child.unref();
}

function _formatRemaining(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function _eprint(...args: unknown[]): void {
  console.error(...args);
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

/**
 * Handle the UserPromptSubmit event, returning a decision object.
 */
export function handleUserPromptSubmit(event: Record<string, unknown>): Record<string, unknown> {
  const prompt = String(event.prompt ?? '').trim();
  const parsed = parsePomodoroCommand(prompt);
  const command = parsed.command;

  const active = isActive();
  const cfg = config.getConfig();

  // -- /pomodoro meta-commands
  if (command !== null) {
    return _handlePomodoroCommand(command, parsed, event, cfg);
  }

  // -- Plain prompt (no /pomodoro prefix)
  if (active) {
    const remaining = getRemainingSeconds();
    return {
      decision: 'block',
      reason:
        `Pomodoro 进行中，还剩 ${_formatRemaining(remaining)}。` +
        ` /pomodoro stop 可提前结束`,
    };
  }

  if (cfg.auto_start) {
    const app = String(event.app ?? 'claude-code');
    const autoApps = cfg.auto_start_apps ?? ['claude-code', 'codex-cli'];
    if (autoApps.includes(app)) {
      const duration = cfg.duration ?? 50;
      const sessionId = startSession(duration, app);
      _spawnTimer(duration, sessionId, app);
      _eprint(`[cc-pomodoro] 自动开始番茄钟 · ${duration} 分钟`);
      return { decision: 'continue' };
    }
    // App not in auto_start_apps -- let prompt through without session
    return { decision: 'continue' };
  }

  return { decision: 'continue' };
}

function _handlePomodoroCommand(
  command: string,
  parsed: ReturnType<typeof parsePomodoroCommand>,
  event: Record<string, unknown>,
  cfg: config.Config,
): Record<string, unknown> {
  const blockReason = 'Pomodoro command processed — not forwarded to AI';

  // -- stop
  if (command === 'stop') {
    if (isActive()) {
      endSession();
      _eprint('[cc-pomodoro] 番茄钟已提前结束');
    } else {
      _eprint('[cc-pomodoro] 没有进行中的番茄钟');
    }
    return { decision: 'block', reason: blockReason };
  }

  // -- status
  if (command === 'status') {
    if (isActive()) {
      const remaining = getRemainingSeconds();
      _eprint(`[POMODORO] 剩余 ${_formatRemaining(remaining)}`);
    } else {
      _eprint('[POMODORO] 没有进行中的番茄钟');
    }
    return { decision: 'block', reason: blockReason };
  }

  // -- stats
  if (command === 'stats') {
    _printStats();
    return { decision: 'block', reason: blockReason };
  }

  // -- config
  if (command === 'config') {
    _handleConfigCommand(parsed.text ?? '');
    return { decision: 'block', reason: blockReason };
  }

  // -- start
  if (command === 'start') {
    const duration = parsed.duration ?? cfg.duration ?? 50;
    const app = String(event.app ?? 'claude-code');

    if (isActive()) {
      const remaining = getRemainingSeconds();
      _eprint(
        `[cc-pomodoro] 警告: 已有进行中的番茄钟` +
        `（还剩 ${_formatRemaining(remaining)}），将启动新周期覆盖旧会话`,
      );
    }

    const sessionId = startSession(duration, app);
    _spawnTimer(duration, sessionId, app);
    _eprint(`[cc-pomodoro] 番茄钟已启动 · ${duration} 分钟`);

    // Continue so the prompt (with /pomodoro prefix) reaches the LLM
    return { decision: 'continue' };
  }

  // Unknown /pomodoro sub-command -- let through (no intervention)
  return { decision: 'continue' };
}

function _printStats(): void {
  const sessions = readSessions();
  if (sessions.length === 0) {
    _eprint('[cc-pomodoro] 暂无专注记录');
    return;
  }

  const stats = getStats();
  _eprint('=== cc-pomodoro 统计 ===');
  _eprint(`今日专注: ${stats.today_minutes} 分钟`);
  _eprint(`本周专注: ${stats.week_minutes} 分钟`);

  if (Object.keys(stats.by_app).length > 0) {
    _eprint('按应用统计:');
    for (const [appName, minutes] of Object.entries(stats.by_app).sort()) {
      _eprint(`  ${appName.padEnd(20)} ${minutes} 分钟`);
    }
  }

  if (stats.recent_sessions.length > 0) {
    _eprint('最近 5 条记录:');
    for (const s of stats.recent_sessions) {
      const started = (s.started_at ?? '').slice(0, 16);
      const ended = (s.ended_at ?? '').slice(0, 16);
      const planned = s.duration_planned ?? '?';
      const endedBy = s.ended_by ?? '?';
      const appName = s.app ?? '?';
      _eprint(
        `  ${started}  →  ${ended}  ` +
        `${planned}min  ${String(endedBy).padEnd(14)}  ${appName}`,
      );
    }
  }
}

function _handleConfigCommand(text: string): void {
  const parts = text.split(/\s+/);
  if (parts.length >= 3 && parts[0] === 'set') {
    const key = parts[1];
    const rawValue = parts.slice(2).join(' ');
    const parsedValue = _parseConfigValue(rawValue);
    config.setConfig(key, parsedValue);
    _eprint(`[cc-pomodoro] 已设置 ${key}=${JSON.stringify(parsedValue)}`);
  } else {
    // Print current config
    const cfg = config.getConfig();
    _eprint(JSON.stringify(cfg, null, 2));
  }
}

function _parseConfigValue(value: string): unknown {
  const lower = value.toLowerCase();
  if (['true', 'yes', 'on', '1'].includes(lower)) return true;
  if (['false', 'no', 'off', '0'].includes(lower)) return false;
  const intVal = parseInt(value, 10);
  if (!isNaN(intVal) && String(intVal) === value) return intVal;
  const floatVal = parseFloat(value);
  if (!isNaN(floatVal) && String(floatVal) === value) return floatVal;
  return value;
}

/**
 * Handle the PreToolUse event, returning a decision object.
 *
 * * During an active pomodoro: auto-allow every tool call.
 * * Otherwise: return empty object -- let the CLI apply its default policy.
 */
export function handlePreToolUse(_event: Record<string, unknown>): Record<string, unknown> {
  if (isActive()) {
    return { permissionDecision: 'allow' };
  }
  return {};
}

/**
 * Handle the Stop event, returning a decision object.
 *
 * * During an active pomodoro: block the completion. For Codex CLI
 *   this also suppresses the output (suppressOutput: true).
 *   A _stop_hook_blocked flag is written to state.json to
 *   prevent infinite re-triggering within the same blocked turn.
 * * Otherwise: return empty object -- let the completion go through.
 */
export function handleStop(_event: Record<string, unknown>): Record<string, unknown> {
  if (!isActive()) {
    // Clear any stale flag left over from a previous session
    const state = getState();
    if (STOP_HOOK_KEY in state) {
      delete state[STOP_HOOK_KEY];
      _writeState(state as Record<string, unknown>);
    }
    return {};
  }

  const state = getState();

  // Already blocked once for this turn -- let this one through to
  // avoid an infinite loop (the framework may re-fire the hook).
  if (state[STOP_HOOK_KEY]) {
    return {};
  }

  // First block -- write flag and return block
  state[STOP_HOOK_KEY] = true;
  _writeState(state as Record<string, unknown>);

  const result: Record<string, unknown> = {
    decision: 'block',
    reason: 'Pomodoro active, continue working',
  };
  if (_isCodex()) {
    result.suppressOutput = true;
  }
  return result;
}

// ---------------------------------------------------------------------------
// Handlers registry
// ---------------------------------------------------------------------------

const HANDLERS: Record<string, (event: Record<string, unknown>) => Record<string, unknown>> = {
  user_prompt_submit: handleUserPromptSubmit,
  pre_tool_use: handlePreToolUse,
  stop: handleStop,
};

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

export function main(): void {
  const argv = process.argv;
  if (argv.length < 3) {
    _eprint(`Usage: hooks.js <event_name>`);
    _eprint(`Available events: ${Object.keys(HANDLERS).join(', ')}`);
    process.exit(1);
  }

  const eventName = argv[2];
  const handler = HANDLERS[eventName];

  if (!handler) {
    _eprint(`Unknown event: ${eventName}`);
    _eprint(`Available events: ${Object.keys(HANDLERS).join(', ')}`);
    // Return empty decision (no intervention) for unknown events
    process.stdout.write(JSON.stringify({}) + '\n');
    process.exit(0);
  }

  let raw = '';
  try {
    raw = fsReadStdin();
  } catch {
    _eprint('[cc-pomodoro] Error reading stdin');
    process.stdout.write(JSON.stringify({}) + '\n');
    process.exit(0);
  }

  if (!raw.trim()) {
    _eprint('[cc-pomodoro] No input received on stdin');
    process.stdout.write(JSON.stringify({}) + '\n');
    process.exit(0);
  }

  let event: Record<string, unknown> = {};
  try {
    event = JSON.parse(raw) as Record<string, unknown>;
  } catch (exc) {
    _eprint(`[cc-pomodoro] Invalid JSON input: ${exc}`);
    process.stdout.write(JSON.stringify({}) + '\n');
    process.exit(0);
  }

  try {
    const decision = handler(event);
    process.stdout.write(JSON.stringify(decision) + '\n');
  } catch (exc) {
    _eprint(`[cc-pomodoro] Error handling ${eventName}: ${exc}`);
    // On error, fall back to no intervention
    process.stdout.write(JSON.stringify({}) + '\n');
    process.exit(0);
  }
}

function fsReadStdin(): string {
  // Synchronous read of all stdin data using the file descriptor
  const fd = process.stdin.fd;
  const chunks: Buffer[] = [];
  const buf = Buffer.alloc(4096);

  let bytesRead: number;
  while (true) {
    try {
      bytesRead = fs.readSync(fd, buf, 0, buf.length, null);
    } catch {
      break;
    }
    if (bytesRead <= 0) break;
    chunks.push(Buffer.from(buf.subarray(0, bytesRead)));
  }

  return Buffer.concat(chunks).toString('utf-8');
}

// Run main when executed directly
if (process.argv[1] && (process.argv[1].endsWith('hooks.js') || process.argv[1].endsWith('hooks.ts'))) {
  main();
}

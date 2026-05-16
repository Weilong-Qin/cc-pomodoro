/**
 * User-facing CLI for cc-pomodoro.
 *
 * Usage:
 *   cc-pomodoro start [--duration MINUTES] [--app NAME] [PROMPT_TEXT]
 *   cc-pomodoro stop
 *   cc-pomodoro status
 *   cc-pomodoro stats [--json]
 *   cc-pomodoro config [set KEY VALUE]
 *   cc-pomodoro hooks init [--app claude-code|codex-cli]
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import * as config from './config.js';
import { VERSION } from './constants.js';
import * as state from './state.js';
import { getStats, readSessions, makeRecord } from './stats.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function parseConfigValue(value: string): unknown {
  const lower = value.toLowerCase();
  if (['true', 'yes', 'on', '1'].includes(lower)) return true;
  if (['false', 'no', 'off', '0'].includes(lower)) return false;
  const intVal = parseInt(value, 10);
  if (!isNaN(intVal) && String(intVal) === value) return intVal;
  const floatVal = parseFloat(value);
  if (!isNaN(floatVal) && String(floatVal) === value) return floatVal;
  return value;
}

export function formatDt(isoStr: string): string {
  if (!isoStr) return '';
  try {
    const dt = new Date(isoStr);
    if (isNaN(dt.getTime())) return isoStr.slice(0, 16);
    const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(dt.getUTCDate()).padStart(2, '0');
    const hh = String(dt.getUTCHours()).padStart(2, '0');
    const min = String(dt.getUTCMinutes()).padStart(2, '0');
    return `${mm}-${dd} ${hh}:${min}`;
  } catch {
    return isoStr.slice(0, 16);
  }
}

function spawnTimer(duration: number, sessionId: string, app: string): void {
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

// ---------------------------------------------------------------------------
// Command implementations
// ---------------------------------------------------------------------------

function cmdStart(args: Record<string, unknown>): void {
  if (state.isActive()) {
    const remaining = state.getRemainingSeconds();
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    console.log(`警告: 已有进行中的番茄钟（还剩 ${m}:${String(s).padStart(2, '0')}），将启动新周期覆盖旧会话`);
  }

  const duration = (args.duration as number | undefined) ?? (config.get('duration') as number);
  const app = (args.app as string | undefined) ?? 'claude-code';
  const sessionId = state.startSession(duration, app);

  console.log(`Pomodoro 已启动 · ${duration} 分钟 · ${app}`);
  if (args.promptText) {
    console.log(args.promptText);
  }

  spawnTimer(duration, sessionId, app);
}

function cmdStop(): void {
  if (!state.isActive()) {
    console.log('没有进行中的番茄钟');
    return;
  }

  const remaining = state.getRemainingSeconds();
  const m = Math.floor(remaining / 60);
  const s = remaining % 60;

  // In an interactive terminal, prompt the user
  try {
    // We need to read from stdin directly for the prompt
    console.log(`还剩 ${m}:${String(s).padStart(2, '0')}，确定结束？[y/N] `);
    // Read a single line from stdin
    let answer = '';
    const buf = Buffer.alloc(1);
    const fd = process.stdin.fd;
    const data: number[] = [];
    let byte: number;
    try {
      while ((byte = fs.readSync(fd, buf, 0, 1, null)) > 0) {
        const ch = buf[0];
        if (ch === 0x0a || ch === 0x0d) break; // newline
        data.push(ch);
      }
    } catch {
      // Non-interactive or error
    }
    answer = Buffer.from(data).toString('utf-8').trim().toLowerCase();

    if (answer === 'y') {
      state.endSession();
      console.log('Pomodoro 已提前结束');
    } else {
      console.log('继续专注');
    }
  } catch {
    console.log('继续专注');
  }
}

function cmdStatus(): void {
  if (!state.isActive()) {
    console.log('没有进行中的番茄钟');
    return;
  }

  const remaining = state.getRemainingSeconds();
  const s = state.getState();
  const m = Math.floor(remaining / 60);
  const sec = remaining % 60;
  const duration = s.duration ?? '?';
  const app = s.app ?? '?';

  console.log(`\u{1f345} ${m}:${String(sec).padStart(2, '0')} · ${app} (${duration}min)`);
}

function cmdStats(args: Record<string, unknown>): void {
  const sessions = readSessions();
  if (sessions.length === 0) {
    console.log('暂无专注记录');
    return;
  }

  if (args.json) {
    for (const session of sessions) {
      console.log(JSON.stringify(session));
    }
    return;
  }

  const stats = getStats();

  console.log('=== cc-pomodoro 统计 ===');
  console.log(`今日专注: ${stats.today_minutes} 分钟`);
  console.log(`本周专注: ${stats.week_minutes} 分钟`);
  console.log();

  if (Object.keys(stats.by_app).length > 0) {
    console.log('按应用统计:');
    for (const [appName, minutes] of Object.entries(stats.by_app).sort()) {
      console.log(`  ${appName.padEnd(20)} ${minutes} 分钟`);
    }
    console.log();
  }

  if (stats.recent_sessions.length > 0) {
    console.log('最近 5 条记录:');
    for (const s of stats.recent_sessions) {
      const started = formatDt(s.started_at ?? '');
      const ended = formatDt(s.ended_at ?? '');
      const planned = s.duration_planned ?? '?';
      const endedBy = s.ended_by ?? '?';
      const appName = s.app ?? '?';
      console.log(
        `  ${started}  →  ${ended}  ` +
        `${planned}min  ${String(endedBy).padEnd(14)}  ${appName}`,
      );
    }
  }
}

function cmdConfig(args: Record<string, unknown>): void {
  if (args.configAction === 'set') {
    if (!args.key || !args.value) {
      console.error('Usage: cc-pomodoro config set <key> <value>');
      process.exit(1);
    }
    const value = parseConfigValue(args.value as string);
    config.setConfig(args.key as string, value);
    console.log(JSON.stringify({ [args.key as string]: value }));
  } else {
    const cfg = config.getConfig();
    console.log(JSON.stringify(cfg, null, 2));
  }
}

function cmdHooksInit(args: Record<string, unknown>): void {
  const app = (args.app as string | undefined) ?? 'claude-code';

  // Derive the hooks directory path from the CLI module location
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  // cli.js is in dist/, package root is ../
  const packageRoot = path.resolve(__dirname, '..');
  const hooksDir = path.join(packageRoot, 'hooks', app);

  if (!fs.existsSync(hooksDir)) {
    console.error(`Error: no hooks directory found at ${hooksDir}`);
    process.exit(1);
  }

  // Determine which platform's script to reference
  const shExt = process.platform === 'win32' ? '.bat' : '.sh';

  const shUserPrompt = path.join(hooksDir, `user_prompt_submit${shExt}`);
  const shPreTool = path.join(hooksDir, `pre_tool_use${shExt}`);
  const shStop = path.join(hooksDir, `stop${shExt}`);

  for (const f of [shUserPrompt, shPreTool, shStop]) {
    if (!fs.existsSync(f)) {
      console.error(`Error: hook script not found: ${f}`);
      process.exit(1);
    }
  }

  let snippet: Record<string, unknown> = {};
  if (app === 'claude-code') {
    snippet = {
      hooks: {
        UserPromptSubmit: shUserPrompt,
        PreToolUse: shPreTool,
        Stop: shStop,
      },
    };
  } else if (app === 'codex-cli') {
    snippet = {
      hooks: {
        userPromptSubmit: shUserPrompt,
        preToolUse: shPreTool,
        stop: shStop,
      },
    };
  } else {
    console.error(`Error: unknown app '${app}'`);
    process.exit(1);
  }

  console.log(JSON.stringify(snippet, null, 2));
}

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

interface ParsedArgs {
  command: string;
  [key: string]: unknown;
}

function parseArgs(argv: string[]): ParsedArgs {
  const cmd = argv[2];
  if (!cmd) {
    printHelp();
    process.exit(0);
  }

  const args: ParsedArgs = { command: cmd };
  const rest = argv.slice(3);

  switch (cmd) {
    case 'start': {
      for (let i = 0; i < rest.length; i++) {
        if (rest[i] === '--duration' && i + 1 < rest.length) {
          args.duration = parseInt(rest[++i], 10);
        } else if (rest[i] === '--app' && i + 1 < rest.length) {
          args.app = rest[++i];
        } else {
          // Everything else is prompt text
          args.promptText = rest.slice(i).join(' ');
          break;
        }
      }
      break;
    }
    case 'stats': {
      args.json = rest.includes('--json');
      break;
    }
    case 'config': {
      args.configAction = rest[0] ?? null;
      args.key = rest[1] ?? null;
      args.value = rest[2] ?? null;
      break;
    }
    case 'hooks': {
      // hooks init [--app NAME]
      if (rest[0] === 'init') {
        args.hooksAction = 'init';
        if (rest[1] === '--app' && rest[2]) {
          args.app = rest[2];
        }
      }
      break;
    }
    case 'stop':
    case 'status':
      break;
    default:
      console.error(`Unknown command: ${cmd}`);
      printHelp();
      process.exit(1);
  }

  return args;
}

function printHelp(): void {
  console.log(`cc-pomodoro v${VERSION}`);
  console.log();
  console.log('Usage:');
  console.log('  cc-pomodoro start [--duration MINUTES] [--app NAME] [PROMPT_TEXT]');
  console.log('  cc-pomodoro stop');
  console.log('  cc-pomodoro status');
  console.log('  cc-pomodoro stats [--json]');
  console.log('  cc-pomodoro config [set KEY VALUE]');
  console.log('  cc-pomodoro hooks init [--app claude-code|codex-cli]');
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export function main(): void {
  // --version or --help
  if (process.argv[2] === '--version') {
    console.log(VERSION);
    process.exit(0);
  }
  if (process.argv[2] === '--help' || process.argv[2] === '-h') {
    printHelp();
    process.exit(0);
  }

  const args = parseArgs(process.argv);

  switch (args.command) {
    case 'start':
      cmdStart(args);
      break;
    case 'stop':
      cmdStop();
      break;
    case 'status':
      cmdStatus();
      break;
    case 'stats':
      cmdStats(args);
      break;
    case 'config':
      cmdConfig(args);
      break;
    case 'hooks':
      if (args.hooksAction === 'init') {
        cmdHooksInit(args);
      } else {
        printHelp();
      }
      break;
    default:
      printHelp();
      break;
  }
}

if (process.argv[1] && (process.argv[1].endsWith('cli.js') || process.argv[1].endsWith('cli.ts'))) {
  main();
}

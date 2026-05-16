import path from 'node:path';
import os from 'node:os';

export const APP_NAME = 'cc-pomodoro';
export const VERSION = '0.1.0';

export const CONFIG_DIR = path.join(os.homedir(), '.config', 'cc-pomodoro');
export const STATE_FILE = path.join(CONFIG_DIR, 'state.json');
export const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');
export const SESSIONS_FILE = path.join(CONFIG_DIR, 'sessions.jsonl');

export const DEFAULT_DURATION = 50;

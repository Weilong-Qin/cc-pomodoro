import fs from 'node:fs';
import { CONFIG_DIR, CONFIG_FILE, DEFAULT_DURATION } from './constants.js';

export interface Config {
  duration: number;
  auto_start: boolean;
  auto_start_apps: string[];
  notify_on_complete: boolean;
  notify_sound: boolean;
  [key: string]: unknown;
}

export const DEFAULT_CONFIG: Config = {
  duration: DEFAULT_DURATION,
  auto_start: false,
  auto_start_apps: ['claude-code', 'codex-cli'],
  notify_on_complete: true,
  notify_sound: true,
};

/**
 * Write data atomically: write to .tmp then rename.
 */
export function atomicWrite(filePath: string, data: string): void {
  const tmpPath = filePath + '.tmp';
  fs.writeFileSync(tmpPath, data, 'utf-8');
  fs.renameSync(tmpPath, filePath);
}

/**
 * Ensure the config directory exists.
 */
export function ensureConfigDir(): void {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
}

/**
 * Read config, merging stored values over defaults.
 */
export function getConfig(): Config {
  const config: Config = { ...DEFAULT_CONFIG };
  if (fs.existsSync(CONFIG_FILE)) {
    const raw = fs.readFileSync(CONFIG_FILE, 'utf-8').trim();
    if (raw) {
      const stored: Record<string, unknown> = JSON.parse(raw);
      for (const key of Object.keys(stored)) {
        (config as Record<string, unknown>)[key] = stored[key];
      }
    }
  }
  return config;
}

/**
 * Get a single config value by key.
 */
export function get(key: string): unknown {
  return (getConfig() as Record<string, unknown>)[key];
}

/**
 * Set a config value and persist to disk.
 */
export function setConfig(key: string, value: unknown): void {
  const config = getConfig() as Record<string, unknown>;
  config[key] = value;
  ensureConfigDir();
  atomicWrite(CONFIG_FILE, JSON.stringify(config, null, 2) + '\n');
}

/**
 * Ensure the default config file exists, then return config.
 */
export function ensureDefaultConfig(): Config {
  ensureConfigDir();
  if (!fs.existsSync(CONFIG_FILE)) {
    atomicWrite(CONFIG_FILE, JSON.stringify(DEFAULT_CONFIG, null, 2) + '\n');
  }
  return getConfig();
}

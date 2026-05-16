import { describe, it, expect } from 'vitest';
import { parsePomodoroCommand } from '../src/parser.js';

describe('parser - no prefix', () => {
  it('plain text returns command=null', () => {
    const result = parsePomodoroCommand('fix the auth bug');
    expect(result).toEqual({ command: null, duration: null, text: null });
  });

  it('text with leading whitespace', () => {
    const result = parsePomodoroCommand('  hello world');
    expect(result).toEqual({ command: null, duration: null, text: null });
  });

  it('empty string', () => {
    const result = parsePomodoroCommand('');
    expect(result).toEqual({ command: null, duration: null, text: null });
  });

  it('whitespace only', () => {
    const result = parsePomodoroCommand('   ');
    expect(result).toEqual({ command: null, duration: null, text: null });
  });
});

describe('parser - bare /pomodoro', () => {
  it('just /pomodoro returns command=null', () => {
    const result = parsePomodoroCommand('/pomodoro');
    expect(result).toEqual({ command: null, duration: null, text: null });
  });

  it('/pomodoro with trailing spaces', () => {
    const result = parsePomodoroCommand('/pomodoro   ');
    expect(result).toEqual({ command: null, duration: null, text: null });
  });
});

describe('parser - /pomodoro start', () => {
  it('with duration and text', () => {
    const result = parsePomodoroCommand('/pomodoro start 25 fix the auth bug');
    expect(result.command).toBe('start');
    expect(result.duration).toBe(25);
    expect(result.text).toBe('fix the auth bug');
  });

  it('without duration', () => {
    const result = parsePomodoroCommand('/pomodoro start fix the auth bug');
    expect(result.command).toBe('start');
    expect(result.duration).toBeNull();
    expect(result.text).toBe('fix the auth bug');
  });

  it('no text', () => {
    const result = parsePomodoroCommand('/pomodoro start');
    expect(result.command).toBe('start');
    expect(result.duration).toBeNull();
    expect(result.text).toBeNull();
  });

  it('only duration, no text', () => {
    const result = parsePomodoroCommand('/pomodoro start 25');
    expect(result.command).toBe('start');
    expect(result.duration).toBe(25);
    expect(result.text).toBeNull();
  });

  it('zero duration is treated as text', () => {
    const result = parsePomodoroCommand('/pomodoro start 0 hello');
    expect(result.command).toBe('start');
    expect(result.duration).toBeNull();
    expect(result.text).toBe('0 hello');
  });

  it('negative number is text', () => {
    const result = parsePomodoroCommand('/pomodoro start -5 hello');
    expect(result.command).toBe('start');
    expect(result.duration).toBeNull();
    expect(result.text).toBe('-5 hello');
  });

  it('with leading whitespace', () => {
    const result = parsePomodoroCommand('  /pomodoro start 30  test message  ');
    expect(result.command).toBe('start');
    expect(result.duration).toBe(30);
    expect(result.text).toBe('test message');
  });

  it('case insensitive command', () => {
    const result = parsePomodoroCommand('/Pomodoro Start 15 my task');
    expect(result.command).toBe('start');
    expect(result.duration).toBe(15);
    expect(result.text).toBe('my task');
  });
});

describe('parser - /pomodoro stop', () => {
  it('basic stop', () => {
    const result = parsePomodoroCommand('/pomodoro stop');
    expect(result.command).toBe('stop');
    expect(result.duration).toBeNull();
    expect(result.text).toBeNull();
  });

  it('stop with extra args', () => {
    const result = parsePomodoroCommand('/pomodoro stop now');
    expect(result.command).toBe('stop');
    expect(result.text).toBe('now');
  });
});

describe('parser - /pomodoro status', () => {
  it('basic status', () => {
    const result = parsePomodoroCommand('/pomodoro status');
    expect(result.command).toBe('status');
    expect(result.duration).toBeNull();
    expect(result.text).toBeNull();
  });

  it('status with args', () => {
    const result = parsePomodoroCommand('/pomodoro status verbose');
    expect(result.command).toBe('status');
    expect(result.text).toBe('verbose');
  });
});

describe('parser - /pomodoro stats', () => {
  it('basic stats', () => {
    const result = parsePomodoroCommand('/pomodoro stats');
    expect(result.command).toBe('stats');
    expect(result.text).toBeNull();
  });

  it('stats with --json flag', () => {
    const result = parsePomodoroCommand('/pomodoro stats --json');
    expect(result.command).toBe('stats');
    expect(result.text).toBe('--json');
  });
});

describe('parser - /pomodoro config', () => {
  it('config set', () => {
    const result = parsePomodoroCommand('/pomodoro config set duration 25');
    expect(result.command).toBe('config');
    expect(result.text).toBe('set duration 25');
  });

  it('config show', () => {
    const result = parsePomodoroCommand('/pomodoro config');
    expect(result.command).toBe('config');
    expect(result.text).toBeNull();
  });

  it('config set bool', () => {
    const result = parsePomodoroCommand('/pomodoro config set auto_start false');
    expect(result.command).toBe('config');
    expect(result.text).toBe('set auto_start false');
  });
});

describe('parser - edge cases', () => {
  it('similar prefixes not matched', () => {
    const result = parsePomodoroCommand('/pomodoro-helper start');
    expect(result.command).toBeNull();
  });

  it('newlines treated as whitespace', () => {
    const result = parsePomodoroCommand('/pomodoro start\n25\ntask');
    expect(result.command).toBe('start');
    expect(result.duration).toBe(25);
    expect(result.text).toBe('task');
  });
});

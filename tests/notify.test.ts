import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock spawn to avoid actual subprocess calls
const mockUnref = vi.fn();
const mockSpawn = vi.fn(() => ({ unref: mockUnref }));

vi.mock('node:child_process', () => ({
  spawn: mockSpawn,
}));

const { notify } = await import('../src/notify.js');

describe('notify', () => {
  let originalPlatform: string;

  beforeEach(() => {
    vi.clearAllMocks();
    originalPlatform = process.platform;
  });

  function setPlatform(platform: string) {
    Object.defineProperty(process, 'platform', { value: platform });
  }

  function restorePlatform() {
    Object.defineProperty(process, 'platform', { value: originalPlatform });
  }

  describe('platform dispatch', () => {
    it('linux calls notify-send', () => {
      setPlatform('linux');
      notify('title', 'msg');
      expect(mockSpawn).toHaveBeenCalledWith('notify-send', ['title', 'msg'], { stdio: 'ignore' });
      restorePlatform();
    });

    it('macOS tries terminal-notifier then osascript', () => {
      setPlatform('darwin');
      notify('title', 'msg');
      expect(mockSpawn).toHaveBeenCalled();
      // First call should be terminal-notifier
      const firstCall = mockSpawn.mock.calls[0];
      expect(firstCall[0]).toBe('terminal-notifier');
      restorePlatform();
    });

    it('Windows calls powershell', () => {
      setPlatform('win32');
      notify('title', 'msg');
      expect(mockSpawn).toHaveBeenCalled();
      const firstCall = mockSpawn.mock.calls[0];
      expect(firstCall[0]).toBe('powershell');
      restorePlatform();
    });
  });

  describe('fallback behavior', () => {
    it('unknown platform falls back to stderr', () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      setPlatform('unknown');
      notify('title', 'msg');
      expect(spy).toHaveBeenCalled();
      spy.mockRestore();
      restorePlatform();
    });

    it('handler exception falls back to stderr', () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      // Make spawn throw for all platforms to exercise the fallback
      mockSpawn.mockImplementation(() => { throw new Error('spawn failed'); });
      setPlatform('linux');
      notify('title', 'msg');
      expect(spy).toHaveBeenCalled();
      expect(spy.mock.calls[0][0]).toContain('[cc-pomodoro]');
      spy.mockRestore();
      restorePlatform();
    });
  });
});

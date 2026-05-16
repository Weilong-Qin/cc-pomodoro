import { spawn } from 'node:child_process';
import process from 'node:process';

/**
 * Show an OS desktop notification.
 *
 * Platform-specific dispatch:
 *   - Linux: notify-send
 *   - macOS: osascript (display notification) or terminal-notifier
 *   - Windows: PowerShell toast notification
 *
 * Falls back to printing to stderr if no notification command is available.
 * Uses spawn (non-blocking) and catches all exceptions so it
 * never crashes the caller.
 */
export function notify(title: string, message: string): void {
  const platform = process.platform;
  try {
    if (platform === 'linux') {
      _notifyLinux(title, message);
      return;
    } else if (platform === 'darwin') {
      _notifyMacOS(title, message);
      return;
    } else if (platform === 'win32') {
      _notifyWindows(title, message);
      return;
    }
  } catch {
    // Fall through to stderr fallback
  }

  // Final fallback: print to stderr for debugging
  console.error(`[cc-pomodoro] ${title}: ${message}`);
}

function _notifyLinux(title: string, message: string): void {
  try {
    spawn('notify-send', [title, message], {
      stdio: 'ignore',
    }).unref();
  } catch {
    throw new Error('notify-send not found');
  }
}

function _notifyMacOS(title: string, message: string): void {
  const safeTitle = title.replace(/"/g, '\\"');
  const safeMessage = message.replace(/"/g, '\\"');

  try {
    spawn('terminal-notifier', ['-title', title, '-message', message], {
      stdio: 'ignore',
    }).unref();
    return;
  } catch {
    // Fall back to osascript
  }

  try {
    const script = `display notification "${safeMessage}" with title "${safeTitle}"`;
    spawn('osascript', ['-e', script], {
      stdio: 'ignore',
    }).unref();
    return;
  } catch {
    throw new Error('No notification command found on macOS');
  }
}

function _notifyWindows(title: string, message: string): void {
  const safeTitle = title.replace(/"/g, '`"').replace(/\$/g, '`$');
  const safeMessage = message.replace(/"/g, '`"').replace(/\$/g, '`$');

  // Method 1: PowerShell WinRT toast
  const winrtScript = [
    `[Windows.UI.Notifications.ToastNotificationManager,`,
    ` Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;`,
    ` $template = [Windows.UI.Notifications.ToastNotificationManager]::`,
    `GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::`,
    `ToastText02);`,
    ` $textNodes = $template.GetElementsByTagName("text");`,
    ` $textNodes.Item(0).AppendChild(`,
    `$template.CreateTextNode("${safeTitle}")) > $null;`,
    ` $textNodes.Item(1).AppendChild(`,
    `$template.CreateTextNode("${safeMessage}")) > $null;`,
    ` $toast = [Windows.UI.Notifications.ToastNotification]::new($template);`,
    ` [Windows.UI.Notifications.ToastNotificationManager]::`,
    `CreateToastNotifier().Show($toast)`,
  ].join('');

  // Method 2: msg.exe
  const msgScript = `${title}: ${message}`;

  // Method 3: COM Popup via PowerShell
  const popupScript =
    `(New-Object -ComObject WScript.Shell).Popup(` +
    `"${safeMessage}", 5, "${safeTitle}", 0x40)`;

  // Try methods in order
  _tryWindowsMethods([winrtScript, msgScript, popupScript], safeTitle, safeMessage);
}

function _tryWindowsMethods(
  methods: string[],
  title: string,
  message: string,
): void {
  const [first, ...rest] = methods;

  if (!first) {
    throw new Error('All Windows notification methods failed');
  }

  try {
    if (methods.length === 3) {
      // WinRT toast
      spawn(
        'powershell',
        ['-NoProfile', '-NonInteractive', '-Command', first],
        {
          stdio: 'ignore',
          windowsHide: true,
        },
      ).unref();
    } else if (methods.length === 2) {
      // msg.exe
      spawn('msg', ['*', `${title}: ${message}`], {
        stdio: 'ignore',
        windowsHide: true,
      }).unref();
    } else {
      // COM Popup
      const popupScript =
        `(New-Object -ComObject WScript.Shell).Popup(` +
        `"${message}", 5, "${title}", 0x40)`;
      spawn(
        'powershell',
        ['-NoProfile', '-NonInteractive', '-Command', popupScript],
        {
          stdio: 'ignore',
          windowsHide: true,
        },
      ).unref();
    }
    return;
  } catch {
    if (rest.length > 0) {
      _tryWindowsMethods(rest, title, message);
    } else {
      throw new Error('All Windows notification methods failed');
    }
  }
}

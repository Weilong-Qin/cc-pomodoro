from __future__ import annotations

import shutil
import subprocess
import sys


def notify(title: str, message: str) -> None:
    """Show an OS desktop notification.

    Platform-specific dispatch:
      - Linux: notify-send
      - macOS: osascript (display notification) or terminal-notifier
      - Windows: PowerShell toast notification

    Falls back to printing to stderr if no notification command is available.
    Uses subprocess.Popen (non-blocking) and catches all exceptions so it
    never crashes the caller.
    """
    platform = sys.platform
    try:
        if platform in ("linux", "linux2"):
            _notify_linux(title, message)
            return
        elif platform == "darwin":
            _notify_macos(title, message)
            return
        elif platform == "win32":
            _notify_windows(title, message)
            return
    except Exception:
        pass

    # Final fallback: print to stderr for debugging
    print(f"[cc-pomodoro] {title}: {message}", file=sys.stderr)


def _notify_linux(title: str, message: str) -> None:
    if shutil.which("notify-send"):
        subprocess.Popen(
            ["notify-send", title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    raise FileNotFoundError("notify-send not found")


def _notify_macos(title: str, message: str) -> None:
    # terminal-notifier provides richer notifications
    if shutil.which("terminal-notifier"):
        subprocess.Popen(
            ["terminal-notifier", "-title", title, "-message", message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    # Fallback to osascript native notification
    if shutil.which("osascript"):
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    raise FileNotFoundError("No notification command found on macOS")


def _notify_windows(title: str, message: str) -> None:
    # Escape special PowerShell characters in double-quoted strings
    safe_title = title.replace('"', '`"').replace('$', '`$')
    safe_message = message.replace('"', '`"').replace('$', '`$')

    # Method 1: PowerShell WinRT toast (requires AppUserModelID; may silently fail)
    winrt_script = (
        f'[Windows.UI.Notifications.ToastNotificationManager,'
        f' Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; '
        f'$template = [Windows.UI.Notifications.ToastNotificationManager]::'
        f'GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::'
        f'ToastText02); '
        f'$textNodes = $template.GetElementsByTagName("text"); '
        f'$textNodes.Item(0).AppendChild('
        f'$template.CreateTextNode("{safe_title}")) > $null; '
        f'$textNodes.Item(1).AppendChild('
        f'$template.CreateTextNode("{safe_message}")) > $null; '
        f'$toast = [Windows.UI.Notifications.ToastNotification]::new($template); '
        f'[Windows.UI.Notifications.ToastNotificationManager]::'
        f'CreateToastNotifier().Show($toast)'
    )

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE

    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", winrt_script],
            startupinfo=startupinfo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    except Exception:
        pass

    # Method 2: Fallback to msg.exe (available on all Windows editions)
    try:
        subprocess.Popen(
            ["msg", "*", f"{title}: {message}"],
            startupinfo=startupinfo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    except Exception:
        pass

    # Method 3: COM Popup via PowerShell (always works)
    try:
        popup_script = (
            f'(New-Object -ComObject WScript.Shell).Popup('
            f'"{safe_message}", 5, "{safe_title}", 0x40)'
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", popup_script],
            startupinfo=startupinfo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    except Exception:
        pass

    raise RuntimeError("All Windows notification methods failed")

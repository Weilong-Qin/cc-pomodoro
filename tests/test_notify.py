"""Tests for cc_pomodoro.notify — platform dispatch and fallback logic.

These tests validate platform detection, command invocation, and
fallback behavior for desktop notifications.
"""

from __future__ import annotations

import subprocess
import sys
from unittest import mock

import pytest

from cc_pomodoro.notify import (
    _notify_linux,
    _notify_macos,
    _notify_windows,
    notify,
)


# -- notify() platform dispatch -----------------------------------------------

class TestNotifyDispatch:
    def test_linux_dispatch(self) -> None:
        with mock.patch("cc_pomodoro.notify.sys.platform", "linux"):
            with mock.patch("cc_pomodoro.notify._notify_linux") as mock_fn:
                notify("title", "msg")
                mock_fn.assert_called_once_with("title", "msg")

    def test_macos_dispatch(self) -> None:
        with mock.patch("cc_pomodoro.notify.sys.platform", "darwin"):
            with mock.patch("cc_pomodoro.notify._notify_macos") as mock_fn:
                notify("title", "msg")
                mock_fn.assert_called_once_with("title", "msg")

    def test_windows_dispatch(self) -> None:
        with mock.patch("cc_pomodoro.notify.sys.platform", "win32"):
            with mock.patch("cc_pomodoro.notify._notify_windows") as mock_fn:
                notify("title", "msg")
                mock_fn.assert_called_once_with("title", "msg")

    def test_unknown_platform_falls_back(self) -> None:
        with mock.patch("cc_pomodoro.notify.sys.platform", "unknown"):
            with mock.patch("cc_pomodoro.notify.print") as mock_print:
                notify("title", "msg")
                mock_print.assert_called_once_with(
                    "[cc-pomodoro] title: msg", file=sys.stderr
                )

    def test_exception_in_platform_handler(self) -> None:
        """If the platform handler raises, notify should fall back to stderr."""
        with mock.patch("cc_pomodoro.notify.sys.platform", "linux"):
            with mock.patch(
                "cc_pomodoro.notify._notify_linux",
                side_effect=RuntimeError("boom"),
            ):
                with mock.patch("cc_pomodoro.notify.print") as mock_print:
                    notify("title", "msg")
                    mock_print.assert_called_once_with(
                        "[cc-pomodoro] title: msg", file=sys.stderr
                    )


# -- _notify_linux ------------------------------------------------------------

class TestNotifyLinux:
    def test_notify_send_found(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/notify-send"):
            with mock.patch("subprocess.Popen") as mock_popen:
                _notify_linux("title", "msg")
                mock_popen.assert_called_once_with(
                    ["notify-send", "title", "msg"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

    def test_notify_send_not_found(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="notify-send not found"):
                _notify_linux("title", "msg")


# -- _notify_macos ------------------------------------------------------------

class TestNotifyMacOS:
    def test_terminal_notifier(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/local/bin/terminal-notifier"):
            with mock.patch("subprocess.Popen") as mock_popen:
                _notify_macos("title", "msg")
                mock_popen.assert_called_once_with(
                    ["terminal-notifier", "-title", "title", "-message", "msg"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

    def test_osascript_with_quote_escaping(self) -> None:
        def _which_side_effect(x: str) -> str | None:
            return "/usr/bin/osascript" if x == "osascript" else None

        with mock.patch("shutil.which", side_effect=_which_side_effect):
            with mock.patch("subprocess.Popen") as mock_popen:
                _notify_macos("title", 'msg with "quotes"')
                mock_popen.assert_called_once()
                args = mock_popen.call_args[0][0]
                assert args[:2] == ["osascript", "-e"]
                assert 'display notification' in args[2]
                assert 'msg with \\"quotes\\"' in args[2]

    def test_none_found(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="No notification command found on macOS"):
                _notify_macos("title", "msg")


# -- _notify_windows ----------------------------------------------------------

class TestNotifyWindows:
    def test_winrt_toast(self) -> None:
        with mock.patch("subprocess.Popen") as mock_popen:
            _notify_windows("title", "msg")
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[:4] == ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
            assert "ToastNotificationManager" in args[4]

    def test_winrt_falls_back_to_msg(self) -> None:
        """If WinRT toast fails, try msg.exe."""
        with (
            mock.patch(
                "subprocess.Popen",
                side_effect=[FileNotFoundError, mock.MagicMock()],
            ) as mock_popen,
        ):
            _notify_windows("title", "msg")
            assert mock_popen.call_count == 2
            second_call = mock_popen.call_args_list[1]
            assert second_call[0][0][0] == "msg"

    def test_all_methods_fail(self) -> None:
        with mock.patch("subprocess.Popen", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="All Windows notification methods failed"):
                _notify_windows("title", "msg")

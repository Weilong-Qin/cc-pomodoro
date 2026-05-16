from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from cc_pomodoro.config import (
    DEFAULT_CONFIG,
    ensure_default_config,
    get,
    get_config,
    set_config,
)


def test_get_config_returns_defaults_when_no_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    with mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file):
        config = get_config()
        assert config == DEFAULT_CONFIG


def test_get_config_merges_with_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    overrides = {"duration": 25, "notify_sound": False}
    config_file.write_text(json.dumps(overrides), encoding="utf-8")

    with mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file):
        config = get_config()
        assert config["duration"] == 25
        assert config["notify_sound"] is False
        assert config["auto_start"] is False
        assert config["auto_start_apps"] == ["claude-code", "codex-cli"]
        assert config["notify_on_complete"] is True


def test_get_returns_specific_key(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    with mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file):
        assert get("duration") == 50
        assert get("auto_start") is False


def test_set_config_updates_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    with (
        mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", tmp_path),
    ):
        set_config("duration", 30)
        assert get("duration") == 30

        set_config("notify_sound", False)
        assert get("notify_sound") is False

        config = get_config()
        assert config["duration"] == 30
        assert config["notify_sound"] is False
        assert config["auto_start"] is False


def test_set_config_preserves_other_keys(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    with (
        mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", tmp_path),
    ):
        set_config("duration", 25)
        set_config("auto_start", False)

        config = get_config()
        assert config["duration"] == 25
        assert config["auto_start"] is False
        assert config["notify_on_complete"] is True


def test_ensure_default_config_creates_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    with (
        mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", tmp_path),
    ):
        assert not config_file.exists()
        config = ensure_default_config()
        assert config_file.exists()
        assert config == DEFAULT_CONFIG


def test_ensure_default_config_does_not_overwrite(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    overrides = {"duration": 15, "auto_start": False}
    config_file.write_text(json.dumps(overrides), encoding="utf-8")

    with (
        mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", tmp_path),
    ):
        config = ensure_default_config()
        assert config["duration"] == 15
        assert config["auto_start"] is False


def test_config_file_human_readable(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    with (
        mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", tmp_path),
    ):
        set_config("duration", 30)
        raw = config_file.read_text(encoding="utf-8")
        assert "  " in raw
        assert raw.endswith("\n")


def test_config_file_atomic_write(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    with (
        mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", tmp_path),
    ):
        set_config("duration", 40)

        tmp_file = config_file.with_suffix(".tmp")
        assert not tmp_file.exists()

        parsed = json.loads(config_file.read_text(encoding="utf-8"))
        assert parsed["duration"] == 40


def test_directory_auto_creation(tmp_path: Path) -> None:
    nested_dir = tmp_path / "nonexistent" / "deep"
    config_file = nested_dir / "config.json"

    with (
        mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file),
        mock.patch("cc_pomodoro.config.CONFIG_DIR", nested_dir),
    ):
        set_config("duration", 30)
        assert config_file.exists()
        assert get("duration") == 30


def test_invalid_json_raises_decode_error(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text("{invalid json}", encoding="utf-8")

    with mock.patch("cc_pomodoro.config.CONFIG_FILE", config_file):
        with pytest.raises(json.JSONDecodeError):
            get_config()

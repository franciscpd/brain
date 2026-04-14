"""Tests for brain_mcp.paths — environment-driven path resolution."""

from pathlib import Path

import pytest

from brain_mcp import paths


def test_brain_home_defaults_to_dot_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_HOME", raising=False)
    home = paths.brain_home()
    assert home == Path.home() / ".brain"


def test_brain_home_honors_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom_brain"
    monkeypatch.setenv("BRAIN_HOME", str(custom))
    assert paths.brain_home() == custom


def test_db_path_defaults_under_brain_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    monkeypatch.delenv("BRAIN_DB_PATH", raising=False)
    assert paths.db_path() == tmp_path / "brain.db"


def test_db_path_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    override = tmp_path / "elsewhere.db"
    monkeypatch.setenv("BRAIN_DB_PATH", str(override))
    assert paths.db_path() == override


def test_model_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    assert paths.model_cache_dir() == tmp_path / "models"


def test_device_id_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    assert paths.device_id_path() == tmp_path / "device_id"

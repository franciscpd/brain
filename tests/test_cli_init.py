"""Tests for `brain init` via typer's CliRunner.

Uses a fake embedder via monkey-patching so the test does not download the
real fastembed model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from brain_mcp.cli import app
from brain_mcp.embedding.models import DEFAULT_MODEL


class _FakeFastEmbedEmbedder:
    def __init__(self, spec: Any, cache_dir: Path) -> None:
        self._spec = spec
        self._cache_dir = cache_dir

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.001 * (i + 1) for i in range(768)] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.001 * (i + 1) for i in range(768)]

    @property
    def model_id(self) -> str:
        return self._spec.fastembed_id

    @property
    def dimension(self) -> int:
        return 768


def test_brain_init_creates_full_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "brain_home"
    monkeypatch.setenv("BRAIN_HOME", str(home))
    monkeypatch.setenv("BRAIN_DB_PATH", str(home / "brain.db"))
    monkeypatch.setattr("brain_mcp.cli.init.FastEmbedEmbedder", _FakeFastEmbedEmbedder)

    runner = CliRunner()
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout

    assert home.is_dir()
    assert (home / "brain.db").exists()
    assert (home / "models").is_dir()
    assert (home / "device_id").exists()
    device_id = (home / "device_id").read_text().strip()
    assert len(device_id) == 32

    assert DEFAULT_MODEL.fastembed_id in result.stdout
    assert "brain is ready." in result.stdout


def test_brain_init_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "brain_home"
    monkeypatch.setenv("BRAIN_HOME", str(home))
    monkeypatch.setenv("BRAIN_DB_PATH", str(home / "brain.db"))
    monkeypatch.setattr("brain_mcp.cli.init.FastEmbedEmbedder", _FakeFastEmbedEmbedder)

    runner = CliRunner()
    runner.invoke(app, ["init"])
    first_device_id = (home / "device_id").read_text().strip()

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    second_device_id = (home / "device_id").read_text().strip()

    assert first_device_id == second_device_id
    assert "brain is ready." in result.stdout


def test_brain_init_force_regenerates_device_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "brain_home"
    monkeypatch.setenv("BRAIN_HOME", str(home))
    monkeypatch.setenv("BRAIN_DB_PATH", str(home / "brain.db"))
    monkeypatch.setattr("brain_mcp.cli.init.FastEmbedEmbedder", _FakeFastEmbedEmbedder)

    runner = CliRunner()
    runner.invoke(app, ["init"])
    first = (home / "device_id").read_text().strip()

    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    second = (home / "device_id").read_text().strip()
    assert first != second

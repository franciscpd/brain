"""Shared pytest fixtures for brain-mcp tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import run_upgrade_head


class FakeEmbedder:
    """Deterministic in-memory embedder for tests. Implements the Embedder protocol."""

    dimension = 768
    model_id = "fake-embedder-v1"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._fake_vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._fake_vec(text)

    def _fake_vec(self, text: str) -> list[float]:
        h = hash(text)
        return [((h >> i) & 0xFF) / 255.0 for i in range(self.dimension)]


@pytest.fixture
def tmp_brain_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def tmp_db(tmp_brain_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_brain_home / "brain.db"
    monkeypatch.setenv("BRAIN_DB_PATH", str(db_file))
    run_upgrade_head()
    return db_file


@pytest.fixture
def db_conn(tmp_db: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_db)
    try:
        yield conn
    finally:
        conn.close()

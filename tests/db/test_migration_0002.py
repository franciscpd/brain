from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import ALEMBIC_CFG_PATH


def _make_cfg(db_path: Path) -> Config:
    # env.py resolves the DB path via BRAIN_DB_PATH / resolve_db_path(),
    # not via sqlalchemy.url — so we must set the env var.
    os.environ["BRAIN_DB_PATH"] = str(db_path)
    cfg = Config(str(ALEMBIC_CFG_PATH))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_upgrade_adds_columns(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    with connect(db) as conn:
        assert "topic" in _columns(conn, "rules")
        assert "content_hash" in _columns(conn, "knowledge_items")
        assert "context" in _columns(conn, "decisions")


def test_upgrade_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")


def test_downgrade_removes_columns(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001_initial")
    with connect(db) as conn:
        assert "topic" not in _columns(conn, "rules")
        assert "content_hash" not in _columns(conn, "knowledge_items")
        assert "context" not in _columns(conn, "decisions")


def test_upgrade_then_downgrade_then_upgrade(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001_initial")
    command.upgrade(cfg, "head")
    with connect(db) as conn:
        assert "topic" in _columns(conn, "rules")

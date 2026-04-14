"""Tests for brain_mcp.db.connection — pragmas and sqlite-vec loading."""

from pathlib import Path

import pytest

from brain_mcp.db.connection import connect, transaction


def _pragma(conn, name: str) -> str:
    row = conn.execute(f"PRAGMA {name}").fetchone()
    return row[0] if row else ""


def test_connect_sets_wal_mode(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        assert _pragma(conn, "journal_mode").lower() == "wal"
    finally:
        conn.close()


def test_connect_sets_busy_timeout(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        assert int(_pragma(conn, "busy_timeout")) == 5000
    finally:
        conn.close()


def test_connect_enables_foreign_keys(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        assert int(_pragma(conn, "foreign_keys")) == 1
    finally:
        conn.close()


def test_connect_loads_sqlite_vec(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        row = conn.execute("SELECT vec_version()").fetchone()
        assert row is not None
        assert isinstance(row[0], str)
    finally:
        conn.close()


def test_connect_creates_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "brain.db"
    conn = connect(nested)
    try:
        assert nested.parent.is_dir()
    finally:
        conn.close()


def test_transaction_commits_on_success(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        with transaction(conn):
            conn.execute("INSERT INTO t (x) VALUES (1)")
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    finally:
        conn.close()


def test_transaction_rolls_back_on_exception(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        with pytest.raises(RuntimeError):
            with transaction(conn):
                conn.execute("INSERT INTO t (x) VALUES (1)")
                raise RuntimeError("boom")
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
    finally:
        conn.close()

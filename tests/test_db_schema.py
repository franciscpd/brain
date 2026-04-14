"""Tests for schema shape — CHECK constraints, FKs, FTS triggers, vec insert."""

from __future__ import annotations

import struct
import uuid
from datetime import UTC, datetime

import pytest

from brain_mcp.db.connection import transaction


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _insert_rule(conn, *, title="t", content="c", scope_type="global", scope_value=None) -> str:
    item_id = uuid.uuid4().hex
    with transaction(conn):
        conn.execute(
            "INSERT INTO knowledge_items "
            "(id, kind, title, content, scope_type, scope_value, created_at, updated_at, sync_id, device_id) "
            "VALUES (?, 'rule', ?, ?, ?, ?, ?, ?, ?, 'dev1')",
            (
                item_id,
                title,
                content,
                scope_type,
                scope_value,
                _now(),
                _now(),
                uuid.uuid4().hex,
            ),
        )
        conn.execute(
            "INSERT INTO rules (item_id, priority) VALUES (?, 50)", (item_id,)
        )
    return item_id


def test_kind_check_constraint_rejects_bad_value(db_conn) -> None:
    with pytest.raises(Exception):  # noqa: B017
        with transaction(db_conn):
            db_conn.execute(
                "INSERT INTO knowledge_items "
                "(id, kind, title, content, scope_type, created_at, updated_at, sync_id, device_id) "
                "VALUES ('x', 'not_a_kind', 't', 'c', 'global', ?, ?, 'sid', 'd')",
                (_now(), _now()),
            )


def test_scope_type_check_constraint_rejects_bad_value(db_conn) -> None:
    with pytest.raises(Exception):  # noqa: B017
        with transaction(db_conn):
            db_conn.execute(
                "INSERT INTO knowledge_items "
                "(id, kind, title, content, scope_type, created_at, updated_at, sync_id, device_id) "
                "VALUES ('x', 'rule', 't', 'c', 'team', ?, ?, 'sid', 'd')",
                (_now(), _now()),
            )


def test_rules_fk_cascade_delete(db_conn) -> None:
    item_id = _insert_rule(db_conn)
    assert db_conn.execute("SELECT COUNT(*) FROM rules WHERE item_id = ?", (item_id,)).fetchone()[0] == 1
    with transaction(db_conn):
        db_conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
    assert db_conn.execute("SELECT COUNT(*) FROM rules WHERE item_id = ?", (item_id,)).fetchone()[0] == 0


def test_fts_trigger_populates_on_insert(db_conn) -> None:
    _insert_rule(db_conn, title="alpha rule", content="always ruff format")
    row = db_conn.execute(
        "SELECT title, content FROM knowledge_fts WHERE knowledge_fts MATCH 'ruff'"
    ).fetchone()
    assert row is not None
    assert "alpha rule" in row[0]


def test_fts_trigger_clears_on_delete(db_conn) -> None:
    item_id = _insert_rule(db_conn, title="to be deleted", content="match me")
    with transaction(db_conn):
        db_conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
    rows = db_conn.execute(
        "SELECT title FROM knowledge_fts WHERE knowledge_fts MATCH 'match'"
    ).fetchall()
    assert rows == []


def test_vec0_accepts_768_dim_insert(db_conn) -> None:
    vector = [0.1] * 768
    blob = struct.pack(f"{len(vector)}f", *vector)
    with transaction(db_conn):
        db_conn.execute("INSERT INTO knowledge_vec (embedding) VALUES (?)", (blob,))
    count = db_conn.execute("SELECT COUNT(*) FROM knowledge_vec").fetchone()[0]
    assert count == 1

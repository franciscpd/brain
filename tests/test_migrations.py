"""Tests for Alembic migration cycle."""

from pathlib import Path

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import run_downgrade_base, run_upgrade_head


def _table_names(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%'"
    ).fetchall()
    return {r[0] for r in rows}


def test_upgrade_head_creates_all_tables(tmp_db: Path) -> None:
    conn = connect(tmp_db)
    try:
        tables = _table_names(conn)
        assert "knowledge_items" in tables
        assert "rules" in tables
        assert "snippets" in tables
        assert "decisions" in tables
        assert "bug_lessons" in tables
        assert "knowledge_tags" in tables
        assert "knowledge_vec" in tables
        assert "vec_rowid_map" in tables
        assert "knowledge_fts" in tables
    finally:
        conn.close()


def test_upgrade_is_idempotent(tmp_db: Path) -> None:
    run_upgrade_head()  # already applied by fixture; run again
    conn = connect(tmp_db)
    try:
        row = conn.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()
        assert row[0] == 0
    finally:
        conn.close()


def test_downgrade_then_upgrade_cycle(tmp_db: Path) -> None:
    run_downgrade_base()
    conn = connect(tmp_db)
    try:
        assert "knowledge_items" not in _table_names(conn)
    finally:
        conn.close()

    run_upgrade_head()
    conn = connect(tmp_db)
    try:
        assert "knowledge_items" in _table_names(conn)
    finally:
        conn.close()

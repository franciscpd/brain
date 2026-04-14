"""Row ↔ Pydantic domain model serializers.

Every insert goes through a single entry point per kind to guarantee that
the parent row, extension row, and tag rows are written together. Reads
assemble the Pydantic model back from the joined rows.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from brain_mcp.db.connection import transaction
from brain_mcp.db.schema import (
    BugLesson,
    Decision,
    KnowledgeItem,
    KnowledgeKind,
    Rule,
    Scope,
    ScopeType,
    Snippet,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def insert_knowledge_item(conn: sqlite3.Connection, item: KnowledgeItem) -> None:
    """Insert the parent row, the extension row, and tag rows in one transaction."""
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO knowledge_items
              (id, kind, title, content, scope_type, scope_value,
               created_at, updated_at, sync_id, device_id, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.kind.value,
                item.title,
                item.content,
                item.scope.type.value,
                item.scope.value,
                _iso(item.created_at),
                _iso(item.updated_at),
                item.sync_id,
                item.device_id,
                _iso(item.synced_at) if item.synced_at else None,
            ),
        )
        _insert_extension(conn, item)
        for tag in item.tags:
            conn.execute(
                "INSERT INTO knowledge_tags (item_id, tag) VALUES (?, ?)",
                (item.id, tag),
            )


def _insert_extension(conn: sqlite3.Connection, item: KnowledgeItem) -> None:
    if isinstance(item, Rule):
        conn.execute(
            "INSERT INTO rules (item_id, priority) VALUES (?, ?)",
            (item.id, item.priority),
        )
    elif isinstance(item, Snippet):
        conn.execute(
            "INSERT INTO snippets (item_id, language, usage_context) VALUES (?, ?, ?)",
            (item.id, item.language, item.usage_context),
        )
    elif isinstance(item, Decision):
        conn.execute(
            "INSERT INTO decisions (item_id, rationale, alternatives) VALUES (?, ?, ?)",
            (item.id, item.rationale, item.alternatives),
        )
    elif isinstance(item, BugLesson):
        conn.execute(
            "INSERT INTO bug_lessons "
            "(item_id, symptom, root_cause, fix, prevention) VALUES (?, ?, ?, ?, ?)",
            (item.id, item.symptom, item.root_cause, item.fix, item.prevention),
        )


def load_knowledge_item(conn: sqlite3.Connection, item_id: str) -> KnowledgeItem | None:
    row = conn.execute(
        "SELECT * FROM knowledge_items WHERE id = ?", (item_id,)
    ).fetchone()
    if row is None:
        return None

    tags = [
        r[0]
        for r in conn.execute(
            "SELECT tag FROM knowledge_tags WHERE item_id = ? ORDER BY tag",
            (item_id,),
        ).fetchall()
    ]

    base_kwargs: dict[str, Any] = dict(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        scope=Scope(
            type=ScopeType(row["scope_type"]),
            value=row["scope_value"],
        ),
        tags=tags,
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
        sync_id=row["sync_id"],
        device_id=row["device_id"],
        synced_at=_parse_dt(row["synced_at"]),
    )

    kind = KnowledgeKind(row["kind"])
    if kind == KnowledgeKind.RULE:
        ext = conn.execute(
            "SELECT priority FROM rules WHERE item_id = ?", (item_id,)
        ).fetchone()
        return Rule(**base_kwargs, priority=ext["priority"])
    if kind == KnowledgeKind.SNIPPET:
        ext = conn.execute(
            "SELECT language, usage_context FROM snippets WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return Snippet(
            **base_kwargs,
            language=ext["language"],
            usage_context=ext["usage_context"],
        )
    if kind == KnowledgeKind.DECISION:
        ext = conn.execute(
            "SELECT rationale, alternatives FROM decisions WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return Decision(
            **base_kwargs,
            rationale=ext["rationale"],
            alternatives=ext["alternatives"],
        )
    if kind == KnowledgeKind.BUG_LESSON:
        ext = conn.execute(
            "SELECT symptom, root_cause, fix, prevention FROM bug_lessons WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return BugLesson(
            **base_kwargs,
            symptom=ext["symptom"],
            root_cause=ext["root_cause"],
            fix=ext["fix"],
            prevention=ext["prevention"],
        )
    return None

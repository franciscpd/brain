"""Tests for brain_mcp.db.serializers — domain model ↔ row helpers."""

from __future__ import annotations

import sqlite3

from brain_mcp.db.schema import BugLesson, Decision, Rule, Scope, ScopeType, Snippet
from brain_mcp.db.serializers import (
    insert_knowledge_item,
    load_knowledge_item,
)


def _make_rule(device_id: str = "dev1") -> Rule:
    return Rule(
        title="always ruff format",
        content="run `ruff format` before commit",
        scope=Scope(type=ScopeType.GLOBAL),
        tags=["python", "format"],
        device_id=device_id,
        priority=80,
    )


def test_insert_and_load_rule(db_conn: sqlite3.Connection) -> None:
    rule = _make_rule()
    insert_knowledge_item(db_conn, rule)
    loaded = load_knowledge_item(db_conn, rule.id)
    assert isinstance(loaded, Rule)
    assert loaded.title == rule.title
    assert loaded.priority == 80
    assert set(loaded.tags) == {"python", "format"}
    assert loaded.scope == rule.scope
    assert loaded.device_id == "dev1"


def test_insert_and_load_snippet(db_conn: sqlite3.Connection) -> None:
    snippet = Snippet(
        title="python context manager",
        content="with open(p) as f: ...",
        scope=Scope(type=ScopeType.LANGUAGE, value="python"),
        device_id="dev1",
        language="python",
        usage_context="reading small files",
    )
    insert_knowledge_item(db_conn, snippet)
    loaded = load_knowledge_item(db_conn, snippet.id)
    assert isinstance(loaded, Snippet)
    assert loaded.language == "python"
    assert loaded.usage_context == "reading small files"


def test_insert_and_load_decision(db_conn: sqlite3.Connection) -> None:
    decision = Decision(
        title="use raw sqlite3 not SQLAlchemy",
        content="decided in Phase 1",
        scope=Scope(type=ScopeType.PROJECT, value="brain-mcp"),
        device_id="dev1",
        rationale="ORMs are hostile to sqlite-vec virtual tables",
        alternatives="SQLAlchemy Core, SQLAlchemy ORM",
    )
    insert_knowledge_item(db_conn, decision)
    loaded = load_knowledge_item(db_conn, decision.id)
    assert isinstance(loaded, Decision)
    assert loaded.rationale.startswith("ORMs")
    assert loaded.alternatives is not None


def test_insert_and_load_bug_lesson(db_conn: sqlite3.Connection) -> None:
    lesson = BugLesson(
        title="sqlite pragma must run on every connection",
        content="foreign_keys pragma is per-connection",
        scope=Scope(type=ScopeType.LANGUAGE, value="python"),
        device_id="dev1",
        symptom="FK violations not raised",
        root_cause="PRAGMA foreign_keys not set",
        fix="Set PRAGMA on connect",
        prevention="Connection factory helper",
    )
    insert_knowledge_item(db_conn, lesson)
    loaded = load_knowledge_item(db_conn, lesson.id)
    assert isinstance(loaded, BugLesson)
    assert loaded.prevention == "Connection factory helper"


def test_load_missing_returns_none(db_conn: sqlite3.Connection) -> None:
    assert load_knowledge_item(db_conn, "does-not-exist") is None

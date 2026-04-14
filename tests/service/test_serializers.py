from __future__ import annotations

import hashlib

from brain_mcp.db.schema import (
    BugLesson,
    Decision,
    Rule,
    Scope,
    ScopeType,
    Snippet,
)
from brain_mcp.service.serializers import content_hash_for, serialize_for_embedding


def _rule() -> Rule:
    return Rule(
        title="Always use ruff format",
        content="Use ruff for formatting Python code.",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
    )


def test_rule_serializes_to_content() -> None:
    text = serialize_for_embedding(_rule())
    assert "Use ruff for formatting Python code." in text
    assert "Always use ruff format" in text


def test_hash_is_deterministic() -> None:
    rule = _rule()
    h1 = content_hash_for(rule)
    h2 = content_hash_for(rule)
    assert h1 == h2
    assert h1 == hashlib.sha256(serialize_for_embedding(rule).encode()).hexdigest()


def test_bug_lesson_serializer_concatenates_fields() -> None:
    bug = BugLesson(
        title="Lost session cookies",
        content="User reports logouts",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        symptom="User logged out randomly",
        root_cause="SameSite=Strict blocked cross-site redirect",
        fix="Set SameSite=Lax",
        prevention="Test cross-site redirects in CI",
    )
    text = serialize_for_embedding(bug)
    assert "User logged out randomly" in text
    assert "Set SameSite=Lax" in text
    assert "Test cross-site redirects in CI" in text


def test_snippet_uses_language_in_text() -> None:
    sn = Snippet(
        title="Async retry helper",
        content="async def retry(fn, n=3): ...",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        language="python",
    )
    text = serialize_for_embedding(sn)
    assert "python" in text
    assert "async def retry" in text


def test_decision_includes_rationale_and_context() -> None:
    d = Decision(
        title="Use SQLite over Postgres",
        content="Use SQLite for brain v1.",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        context="Single-user, local-first.",
        rationale="Zero install friction.",
        alternatives="Postgres, DuckDB.",
    )
    text = serialize_for_embedding(d)
    assert "Zero install friction." in text
    assert "Single-user" in text


def test_decision_without_optional_fields() -> None:
    d = Decision(
        title="T",
        content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        rationale="R",
    )
    text = serialize_for_embedding(d)
    assert "R" in text

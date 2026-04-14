"""Tests for brain_mcp.db.schema — Pydantic domain models."""

from datetime import datetime

import pytest

from brain_mcp.db.schema import (
    BugLesson,
    Decision,
    KnowledgeKind,
    Rule,
    Scope,
    ScopeType,
    Snippet,
)


def test_scope_global_is_frozen() -> None:
    scope = Scope(type=ScopeType.GLOBAL)
    with pytest.raises(Exception):  # noqa: B017
        scope.value = "project-x"  # type: ignore[misc]


def test_scope_str_global() -> None:
    assert str(Scope(type=ScopeType.GLOBAL)) == "global"


def test_scope_str_project() -> None:
    assert str(Scope(type=ScopeType.PROJECT, value="brain")) == "project:brain"


def test_rule_defaults() -> None:
    rule = Rule(
        title="always use ruff format",
        content="run `ruff format` before commit",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="abc123",
    )
    assert rule.kind == KnowledgeKind.RULE
    assert rule.priority == 50
    assert rule.tags == []
    assert isinstance(rule.id, str)
    assert len(rule.id) == 32  # uuid4 hex
    assert isinstance(rule.created_at, datetime)
    assert rule.sync_id != rule.id  # independently generated


def test_rule_priority_bounds() -> None:
    with pytest.raises(Exception):  # noqa: B017
        Rule(
            title="x",
            content="x",
            scope=Scope(type=ScopeType.GLOBAL),
            device_id="d",
            priority=101,
        )


def test_snippet_requires_language() -> None:
    with pytest.raises(Exception):  # noqa: B017
        Snippet(  # type: ignore[call-arg]
            title="x",
            content="x",
            scope=Scope(type=ScopeType.GLOBAL),
            device_id="d",
        )


def test_decision_requires_rationale() -> None:
    with pytest.raises(Exception):  # noqa: B017
        Decision(  # type: ignore[call-arg]
            title="x",
            content="x",
            scope=Scope(type=ScopeType.GLOBAL),
            device_id="d",
        )


def test_bug_lesson_has_all_narrative_fields() -> None:
    lesson = BugLesson(
        title="sqlite3 TEXT vs BLOB",
        content="summary",
        scope=Scope(type=ScopeType.LANGUAGE, value="python"),
        device_id="d",
        symptom="weird bytes",
        root_cause="wrong column affinity",
        fix="use TEXT",
    )
    assert lesson.kind == KnowledgeKind.BUG_LESSON
    assert lesson.prevention is None

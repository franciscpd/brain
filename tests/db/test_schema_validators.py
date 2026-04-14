from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from brain_mcp.db.normalize import (
    normalize_language,
    normalize_tag,
    normalize_topic,
    slugify,
)
from brain_mcp.db.schema import (
    Decision,
    KnowledgeKind,
    Rule,
    Scope,
    ScopeType,
    Snippet,
)


def test_slugify_lowercases_and_hyphenizes() -> None:
    assert slugify("Hello World") == "hello-world"
    assert slugify("Python_Async ") == "python-async"
    assert slugify("  Mixed_Case Name ") == "mixed-case-name"
    assert slugify("") == ""
    assert slugify("---") == ""


def test_normalize_tag_matches_slugify() -> None:
    assert normalize_tag("Python Async") == "python-async"
    assert normalize_tag(" python-async ") == "python-async"
    assert normalize_tag("python_async") == "python-async"


def test_normalize_language_lowercases_only() -> None:
    assert normalize_language("Python") == "python"
    assert normalize_language("  TypeScript ") == "typescript"


def test_normalize_topic_matches_slugify() -> None:
    assert normalize_topic("Code Style") == "code-style"
    assert normalize_topic(None) is None


def test_rule_tags_are_normalized_and_sorted() -> None:
    rule = Rule(
        title="T", content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        tags=["Python_Async", "PYTHON-async", " effects "],
    )
    assert rule.tags == ["effects", "python-async"]


def test_snippet_language_normalized() -> None:
    s = Snippet(
        title="T", content="print(1)",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        language="Python",
    )
    assert s.language == "python"


def test_rule_topic_normalized() -> None:
    r = Rule(
        title="T", content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        topic="Code Style",
    )
    assert r.topic == "code-style"


def test_decision_context_optional() -> None:
    d = Decision(
        title="D", content="use SQLite",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        rationale="simple",
    )
    assert d.context is None
    d2 = Decision(
        title="D", content="use SQLite",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        rationale="simple",
        context="single user",
    )
    assert d2.context == "single user"


def test_scope_project_requires_value() -> None:
    with pytest.raises(PydanticValidationError):
        Rule(
            title="T", content="C",
            scope=Scope(type=ScopeType.PROJECT, value=None),
            device_id="dev1",
        )


def test_scope_global_rejects_value() -> None:
    with pytest.raises(PydanticValidationError):
        Rule(
            title="T", content="C",
            scope=Scope(type=ScopeType.GLOBAL, value="brain"),
            device_id="dev1",
        )


def test_scope_language_requires_value() -> None:
    with pytest.raises(PydanticValidationError):
        Snippet(
            title="T", content="C",
            scope=Scope(type=ScopeType.LANGUAGE, value=None),
            device_id="dev1",
            language="python",
        )


from brain_mcp.db.schema import KnowledgeItemPatch


def test_patch_accepts_partial_content_update() -> None:
    patch = KnowledgeItemPatch(content="new content")
    dumped = patch.model_dump(exclude_unset=True)
    assert dumped == {"content": "new content"}


def test_patch_rejects_immutable_id() -> None:
    with pytest.raises(PydanticValidationError):
        KnowledgeItemPatch(id="xyz")


def test_patch_rejects_immutable_kind() -> None:
    with pytest.raises(PydanticValidationError):
        KnowledgeItemPatch(kind=KnowledgeKind.RULE)


def test_patch_rejects_immutable_created_at() -> None:
    from datetime import UTC, datetime
    with pytest.raises(PydanticValidationError):
        KnowledgeItemPatch(created_at=datetime.now(tz=UTC))


def test_patch_normalizes_tags_like_base() -> None:
    patch = KnowledgeItemPatch(tags=["Python_Async", "effects"])
    assert patch.tags == ["effects", "python-async"]


def test_patch_normalizes_language() -> None:
    patch = KnowledgeItemPatch(language="Python")
    assert patch.language == "python"


def test_patch_normalizes_topic() -> None:
    patch = KnowledgeItemPatch(topic="Code Style")
    assert patch.topic == "code-style"

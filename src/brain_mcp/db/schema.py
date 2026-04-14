"""Pydantic domain models for brain-mcp knowledge items.

Every knowledge item inherits KnowledgeItemBase (shared fields).
The four concrete types (Rule, Snippet, Decision, BugLesson) add type-specific
fields and are discriminated by the `kind` field.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from brain_mcp.db.normalize import normalize_language, normalize_tag, normalize_topic


class KnowledgeKind(StrEnum):
    RULE = "rule"
    SNIPPET = "snippet"
    DECISION = "decision"
    BUG_LESSON = "bug_lesson"


class ScopeType(StrEnum):
    GLOBAL = "global"
    PROJECT = "project"
    LANGUAGE = "language"


class Scope(BaseModel):
    """Immutable value object describing the reach of a knowledge item."""

    model_config = ConfigDict(frozen=True)

    type: ScopeType
    value: str | None = None  # None only when type == GLOBAL

    def __str__(self) -> str:
        return f"{self.type.value}:{self.value}" if self.value else self.type.value


class KnowledgeItemBase(BaseModel):
    """Fields shared by every knowledge item."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    content: str
    scope: Scope
    tags: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    sync_id: str = Field(default_factory=lambda: uuid4().hex)
    device_id: str
    synced_at: datetime | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, v: object) -> list[str]:
        if not v:
            return []
        raw: list[str] = list(v)  # type: ignore[arg-type]
        normalized = [normalize_tag(t) for t in raw if t and t.strip()]
        deduped = sorted(set(normalized))
        return deduped

    @model_validator(mode="after")
    def _check_scope(self) -> "KnowledgeItemBase":
        scope = self.scope
        if scope.type == ScopeType.GLOBAL and scope.value is not None:
            raise ValueError("GLOBAL scope must have value=None")
        if scope.type in (ScopeType.PROJECT, ScopeType.LANGUAGE) and not scope.value:
            raise ValueError(f"{scope.type} scope requires a non-empty value")
        return self


class Rule(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.RULE] = KnowledgeKind.RULE
    priority: int = Field(default=50, ge=0, le=100)
    topic: str | None = None

    @field_validator("topic", mode="before")
    @classmethod
    def _normalize_topic(cls, v: object) -> object:
        if v is None:
            return None
        return normalize_topic(str(v))


class Snippet(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.SNIPPET] = KnowledgeKind.SNIPPET
    language: str
    usage_context: str | None = None

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_language(cls, v: object) -> str:
        result = normalize_language(str(v))
        if not result:
            raise ValueError("language must be a non-empty string")
        return result


class Decision(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.DECISION] = KnowledgeKind.DECISION
    rationale: str
    alternatives: str | None = None
    context: str | None = None


class BugLesson(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.BUG_LESSON] = KnowledgeKind.BUG_LESSON
    symptom: str
    root_cause: str
    fix: str
    prevention: str | None = None


KnowledgeItem = Rule | Snippet | Decision | BugLesson


class KnowledgeItemPatch(BaseModel):
    """Partial update payload for a KnowledgeItem.

    Immutable fields (id, kind, created_at) are not present on this model —
    passing them raises PydanticValidationError via ``extra='forbid'``.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    content: str | None = None
    scope: Scope | None = None
    tags: list[str] | None = None

    # kind-specific (all optional)
    priority: int | None = Field(default=None, ge=0, le=100)
    topic: str | None = None
    language: str | None = None
    usage_context: str | None = None
    context: str | None = None
    rationale: str | None = None
    alternatives: str | None = None
    symptom: str | None = None
    root_cause: str | None = None
    fix: str | None = None
    prevention: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = {normalize_tag(t) for t in value if t and normalize_tag(t)}
        return sorted(normalized)

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_language(value)

    @field_validator("topic", mode="before")
    @classmethod
    def _normalize_topic(cls, value: str | None) -> str | None:
        return normalize_topic(value)

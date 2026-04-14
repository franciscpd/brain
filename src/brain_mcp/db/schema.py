"""Pydantic domain models for brain-mcp knowledge items.

Every knowledge item inherits KnowledgeItemBase (shared fields).
The four concrete types (Rule, Snippet, Decision, BugLesson) add type-specific
fields and are discriminated by the `kind` field.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


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
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    sync_id: str = Field(default_factory=lambda: uuid4().hex)
    device_id: str
    synced_at: datetime | None = None


class Rule(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.RULE] = KnowledgeKind.RULE
    priority: int = Field(default=50, ge=0, le=100)


class Snippet(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.SNIPPET] = KnowledgeKind.SNIPPET
    language: str
    usage_context: str | None = None


class Decision(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.DECISION] = KnowledgeKind.DECISION
    rationale: str
    alternatives: str | None = None


class BugLesson(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.BUG_LESSON] = KnowledgeKind.BUG_LESSON
    symptom: str
    root_cause: str
    fix: str
    prevention: str | None = None


KnowledgeItem = Rule | Snippet | Decision | BugLesson

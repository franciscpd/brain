# Phase 2: Knowledge CRUD + Scoping + MCP Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a working stdio MCP server (`brain-server`) exposing six tools (`brain_capture`, `brain_get`, `brain_update`, `brain_delete`, `brain_list`, `brain_search`) and one Resource (`brain://session/{project_id}/context`), backed by a `KnowledgeService` that performs CRUD + hard-filtered scoping + secret scanning + content-hash-triggered re-embedding for all four knowledge kinds. End state: every Phase 2 success criterion from ROADMAP.md is green and verifiable in MCP Inspector.

**Architecture:** Layered. New packages `scanner/`, `scope/`, `service/`, `mcp/` build on Phase 1's `db/`, `embedding/`, `errors.py`, `logging.py`, `paths.py`. `KnowledgeService` is the only module that touches SQL; `scanner` and `scope` are pure helpers; the `mcp/` package is thin glue (lifespan + tool handlers + error translator). Concurrency is a single `asyncio.Lock` on `BrainContext`, taken by every tool handler. One additive migration (`0002_phase2`).

**Tech Stack:** Python 3.11+, `mcp[cli]==1.27.0` (FastMCP), `pydantic>=2`, `sqlite3` stdlib via `brain_mcp.db.connection`, `sqlite-vec==0.1.9`, `alembic==1.15+`, `fastembed==0.8.0` (Phase 1), `detect-secrets` (new), `pytest` + `pytest-asyncio`.

**Inputs:** `.planning/phases/02-knowledge-crud-scoping-mcp-core/02-CONTEXT.md` (33 locked decisions) and `.../BRAINSTORMING.md` (13 sections). This plan supersedes both wherever the implementation details below disagree with either.

---

## Phase 1 Residuals Discovered During Planning

Reading `src/brain_mcp/db/` found that the Phase 1 schema differs from what `BRAINSTORMING.md` §2 and §4 assumed. These differences are real and authoritative — the plan uses them:

| Topic | BRAINSTORMING assumed | Phase 1 reality | Impact on this plan |
|---|---|---|---|
| Tag storage | JSON array on `knowledge_items.tags` | Junction table `knowledge_tags(item_id, tag)` | Service writes/reads tags via junction; list filter uses subqueries |
| `Scope` | Flat `scope_type` / `scope_value` on Pydantic model | `Scope` value object: `item.scope.type`, `item.scope.value` | Tool handlers build `Scope` objects; service validates via existing class |
| `Decision.context` | Not mentioned | Missing in both model and DB (KNOW-03 gap) | Migration 0002 adds `decisions.context`; Pydantic `Decision` gets `context: str \| None` |
| `embedding_model_id` | Thought missing from Phase 1 | Lives on `vec_rowid_map` (correct per STOR-02) | No column change needed |
| `Snippet` / `BugLesson` fields | Need expansion | Already complete in Phase 1 | No changes to those models |

**Migration 0002 final column list:**
1. `rules.topic TEXT NULL` + partial index
2. `knowledge_items.content_hash TEXT NULL` (for re-embed diffing)
3. `decisions.context TEXT NULL` (KNOW-03 residual)

Everything else listed in BRAINSTORMING.md §4 was already done in Phase 1.

---

## File Structure

New files:

| Path | Responsibility |
|---|---|
| `src/brain_mcp/db/migrations/versions/0002_phase2.py` | Alembic migration adding 3 columns |
| `src/brain_mcp/scanner/__init__.py` | Package init, exports `SecretScanner` |
| `src/brain_mcp/scanner/secrets.py` | `SecretScanner` wrapping `detect-secrets` |
| `src/brain_mcp/scope/__init__.py` | Package init, exports `ScopeResolver`, `resolve_project_id` |
| `src/brain_mcp/scope/project_id.py` | `resolve_project_id(mcp_roots, cwd)` pure function + `_slugify` |
| `src/brain_mcp/scope/resolver.py` | `ScopeResolver` with `build_filter` and `apply_rule_override` |
| `src/brain_mcp/service/__init__.py` | Package init, exports `KnowledgeService` |
| `src/brain_mcp/service/knowledge.py` | `KnowledgeService` with full CRUD + list + search stub |
| `src/brain_mcp/service/serializers.py` | `serialize_for_embedding(item)` + `content_hash_for(item)` helpers |
| `src/brain_mcp/mcp/__init__.py` | Package init |
| `src/brain_mcp/mcp/context.py` | `BrainContext` frozen dataclass |
| `src/brain_mcp/mcp/errors.py` | `error_response(err: BrainError) -> dict` translator |
| `src/brain_mcp/mcp/server.py` | FastMCP app, lifespan, `main()` entry point |
| `src/brain_mcp/mcp/tools.py` | 6 tool handlers registered on the app |
| `src/brain_mcp/mcp/resources.py` | `session_context` Resource + `render_briefing_markdown` |

Modified files:

| Path | Change |
|---|---|
| `src/brain_mcp/errors.py` | Add `SecretDetectedError`, `NotFoundError`, `ValidationError`, `ScopeError` subclasses |
| `src/brain_mcp/db/schema.py` | Add `content_hash` + scope validator on `KnowledgeItemBase`; add `topic` + normalizer on `Rule`; add `context` on `Decision`; add tag/language/topic normalizers; add `KnowledgeItemPatch` model |
| `pyproject.toml` | Add `detect-secrets` dep; add `brain-server` console script |

New test files:

| Path | Covers |
|---|---|
| `tests/db/test_migration_0002.py` | upgrade/downgrade/idempotency |
| `tests/db/test_schema_validators.py` | tag/language/topic normalization + scope validator |
| `tests/test_errors.py` | new error subclasses carry the right codes |
| `tests/scanner/test_secret_scanner.py` | detects AWS/JWT/PEM; never echoes values |
| `tests/scope/test_project_id.py` | MCP roots → .git walk → cwd fallback matrix |
| `tests/scope/test_resolver.py` | filter shape + topic override + order preservation |
| `tests/service/test_knowledge_service_crud.py` | create/get/delete per kind |
| `tests/service/test_knowledge_service_reembed.py` | content-hash re-embed on update |
| `tests/service/test_knowledge_service_list.py` | scope hard filter, override, tag AND, pagination |
| `tests/service/test_knowledge_service_search.py` | stub search shape |
| `tests/mcp/test_server_lifespan.py` | DB-missing fast fail + stderr-only logging |
| `tests/mcp/test_server_capture.py` | happy path per kind + SECRET_DETECTED + VALIDATION_ERROR |
| `tests/mcp/test_server_crud.py` | get/update/delete lifecycle + NOT_FOUND |
| `tests/mcp/test_server_list_and_search.py` | scoped list + search stub shape |
| `tests/mcp/test_server_resource.py` | session briefing + override visible |
| `tests/mcp/test_server_error_contract.py` | all error codes → correct JSON |
| `tests/mcp/test_tool_count.py` | `len(tools) <= 8` |

---

## Conventions

- Every service/scanner/resolver takes dependencies via constructor. No module-level singletons.
- Every SQL query goes through `brain_mcp.db.connection.connect(...)` or the existing `transaction(conn)` context manager. Never call `sqlite3.connect()` directly.
- Every new Python file starts with `from __future__ import annotations`.
- Every test file mirrors the module layout under `src/brain_mcp/` to `tests/`.
- Every commit message uses the format `type(scope): description` per `CLAUDE.md`. Prefer atomic commits: one concept per commit, test + impl together.
- Run the full suite before every commit: `uv run pytest -q`.
- Tests use a **fake embedder** (see helper in Task 15) to avoid the 270MB fastembed download.

---

## Test Helper — Fake Embedder

Phase 1 already uses a fake embedder in `tests/test_cli_init.py`. This plan relies on a shared version living at `tests/conftest.py` (or a new `tests/_fakes.py`). Task 15 introduces it formally; from Task 15 onward every service/MCP test imports it.

The fake embedder is a minimal object with two methods:

```python
class FakeEmbedder:
    """Deterministic in-memory embedder for tests.

    Produces 768-dim vectors (matching knowledge_vec[float[768]]) by
    hashing the input text. Counts calls so tests can assert that
    re-embed did/didn't happen.
    """

    model_id = "fake-embed-v1"

    def __init__(self) -> None:
        self.document_calls: list[str] = []
        self.query_calls: list[str] = []

    def embed_document(self, text: str) -> list[float]:
        self.document_calls.append(text)
        return self._vector(text)

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        # Expand 32 bytes → 768 floats by cycling, values in [0, 1)
        return [(h[i % 32] / 256.0) for i in range(768)]
```

This exact class is introduced in Task 15 and reused unchanged by Tasks 16–29.

---

## Tasks

### Task 1: Alembic migration 0002 — topic, content_hash, context

**Files:**
- Create: `src/brain_mcp/db/migrations/versions/0002_phase2.py`
- Create: `tests/db/__init__.py` (if not already present — Task-time check)
- Create: `tests/db/test_migration_0002.py`

- [ ] **Step 1: Write the failing migration test**

Create `tests/db/test_migration_0002.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import ALEMBIC_CFG_PATH


def _make_cfg(db_path: Path) -> Config:
    cfg = Config(str(ALEMBIC_CFG_PATH))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_upgrade_adds_columns(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    with connect(db) as conn:
        assert "topic" in _columns(conn, "rules")
        assert "content_hash" in _columns(conn, "knowledge_items")
        assert "context" in _columns(conn, "decisions")


def test_upgrade_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    # Second run is a no-op, must not raise.
    command.upgrade(cfg, "head")


def test_downgrade_removes_columns(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001_initial")
    with connect(db) as conn:
        assert "topic" not in _columns(conn, "rules")
        assert "content_hash" not in _columns(conn, "knowledge_items")
        assert "context" not in _columns(conn, "decisions")


def test_upgrade_then_downgrade_then_upgrade(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    cfg = _make_cfg(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0001_initial")
    command.upgrade(cfg, "head")
    with connect(db) as conn:
        assert "topic" in _columns(conn, "rules")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/db/test_migration_0002.py -q
```
Expected: **FAIL** with `ModuleNotFoundError` or `No such revision` — migration file doesn't exist yet.

- [ ] **Step 3: Write the migration**

Create `src/brain_mcp/db/migrations/versions/0002_phase2.py`:

```python
"""phase 2: rules.topic, knowledge_items.content_hash, decisions.context.

Revision ID: 0002_phase2
Revises: 0001_initial
Create Date: 2026-04-14
"""

from __future__ import annotations

from alembic import op

revision = "0002_phase2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rules") as batch:
        batch.execute("ALTER TABLE rules ADD COLUMN topic TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rules_topic "
        "ON rules(topic) WHERE topic IS NOT NULL"
    )

    with op.batch_alter_table("knowledge_items") as batch:
        batch.execute("ALTER TABLE knowledge_items ADD COLUMN content_hash TEXT")

    with op.batch_alter_table("decisions") as batch:
        batch.execute("ALTER TABLE decisions ADD COLUMN context TEXT")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_rules_topic")
    # SQLite pre-3.35 doesn't support DROP COLUMN without batch mode.
    with op.batch_alter_table("decisions") as batch:
        batch.drop_column("context")
    with op.batch_alter_table("knowledge_items") as batch:
        batch.drop_column("content_hash")
    with op.batch_alter_table("rules") as batch:
        batch.drop_column("topic")
```

Note: the `with op.batch_alter_table(...): batch.execute(...)` form on upgrade is used because `ALTER TABLE ... ADD COLUMN` is the only SQLite alteration that works outside batch mode for these cases. We wrap it anyway so the pattern is uniform. For downgrade, `drop_column` absolutely requires batch mode.

- [ ] **Step 4: Run the migration tests — must pass**

```bash
uv run pytest tests/db/test_migration_0002.py -q
```
Expected: **4 passed**.

- [ ] **Step 5: Run the full existing test suite — must still pass**

```bash
uv run pytest -q
```
Expected: everything from Phase 1 still green (46+ tests).

- [ ] **Step 6: Commit**

```bash
git add src/brain_mcp/db/migrations/versions/0002_phase2.py tests/db/test_migration_0002.py
git commit -m "feat(db): add migration 0002 (topic, content_hash, decisions.context)"
```

---

### Task 2: Expand `errors.py` with Phase 2 error subclasses

**Files:**
- Modify: `src/brain_mcp/errors.py`
- Create: `tests/test_errors_phase2.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_errors_phase2.py`:

```python
from __future__ import annotations

from brain_mcp.errors import (
    BrainError,
    NotFoundError,
    ScopeError,
    SecretDetectedError,
    ValidationError,
)


def test_secret_detected_has_code_and_details() -> None:
    err = SecretDetectedError(
        "Secret detected in content",
        details={"hits": [{"plugin": "AWSKeyDetector", "line": 3}]},
    )
    assert isinstance(err, BrainError)
    assert err.code == "SECRET_DETECTED"
    assert err.details["hits"][0]["plugin"] == "AWSKeyDetector"


def test_not_found_error() -> None:
    err = NotFoundError("missing id xyz", details={"id": "xyz"})
    assert err.code == "NOT_FOUND"
    assert isinstance(err, BrainError)


def test_validation_error() -> None:
    err = ValidationError("missing required field", details={"field": "title"})
    assert err.code == "VALIDATION_ERROR"


def test_scope_error() -> None:
    err = ScopeError(
        "scope=language requires scope_value",
        details={"scope_type": "language"},
    )
    assert err.code == "SCOPE_INVALID"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_errors_phase2.py -q
```
Expected: **FAIL** with `ImportError`.

- [ ] **Step 3: Add the subclasses to `errors.py`**

Append to `src/brain_mcp/errors.py`:

```python
class SecretDetectedError(BrainError):
    code = "SECRET_DETECTED"


class NotFoundError(BrainError):
    code = "NOT_FOUND"


class ValidationError(BrainError):
    code = "VALIDATION_ERROR"


class ScopeError(BrainError):
    code = "SCOPE_INVALID"
```

Verify the existing `BrainError` base already supports `code` as a class attribute and `details: dict` via constructor. If it does not, adjust the base minimally:

```python
class BrainError(Exception):
    code: str = "BRAIN_ERROR"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}
```

(If the existing base already matches this shape, leave it alone.)

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_errors_phase2.py -q
```
Expected: **4 passed**.

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -q
```
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/brain_mcp/errors.py tests/test_errors_phase2.py
git commit -m "feat(errors): add phase 2 error subclasses (secret, not_found, validation, scope)"
```

---

### Task 3: Normalization helpers and schema validators

**Files:**
- Create: `src/brain_mcp/db/normalize.py`
- Modify: `src/brain_mcp/db/schema.py`
- Create: `tests/db/test_schema_validators.py`

**Why a dedicated module:** tag / topic / language / project-id slugification all share the same primitives. A single `normalize.py` avoids four near-duplicate helper functions and gives one test surface for the rules.

- [ ] **Step 1: Write the failing test**

Create `tests/db/test_schema_validators.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from brain_mcp.db.normalize import normalize_language, normalize_tag, normalize_topic, slugify
from brain_mcp.db.schema import KnowledgeKind, Rule, Scope, ScopeType, Snippet


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
    # Language is not hyphenized — spaces are rejected.
    assert normalize_language("Python") == "python"
    assert normalize_language("  TypeScript ") == "typescript"


def test_normalize_topic_matches_slugify() -> None:
    assert normalize_topic("Code Style") == "code-style"
    assert normalize_topic(None) is None


def test_rule_tags_are_normalized_and_sorted() -> None:
    rule = Rule(
        title="T",
        content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        tags=["Python_Async", "PYTHON-async", " effects "],  # dup + casing + whitespace
    )
    assert rule.tags == ["effects", "python-async"]


def test_snippet_language_normalized() -> None:
    s = Snippet(
        title="T",
        content="print(1)",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        language="Python",
    )
    assert s.language == "python"


def test_rule_topic_normalized() -> None:
    r = Rule(
        title="T",
        content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        topic="Code Style",
    )
    assert r.topic == "code-style"


def test_scope_project_requires_value() -> None:
    # Scope is the value object; Pydantic validator on KnowledgeItemBase catches the mismatch.
    with pytest.raises(PydanticValidationError):
        Rule(
            title="T",
            content="C",
            scope=Scope(type=ScopeType.PROJECT, value=None),
            device_id="dev1",
        )


def test_scope_global_rejects_value() -> None:
    with pytest.raises(PydanticValidationError):
        Rule(
            title="T",
            content="C",
            scope=Scope(type=ScopeType.GLOBAL, value="brain"),
            device_id="dev1",
        )
```

- [ ] **Step 2: Run — expect failures**

```bash
uv run pytest tests/db/test_schema_validators.py -q
```
Expected: **FAIL** — `normalize.py` missing, validators missing, `Rule.topic` missing.

- [ ] **Step 3: Create `src/brain_mcp/db/normalize.py`**

```python
"""String normalization primitives for brain-mcp domain models."""

from __future__ import annotations

import re

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


def slugify(value: str) -> str:
    """Lowercase, replace any run of non-alphanumerics with '-', trim dashes."""
    lowered = value.strip().lower()
    hyphenized = _NON_SLUG.sub("-", lowered)
    collapsed = _MULTI_DASH.sub("-", hyphenized)
    return collapsed.strip("-")


def normalize_tag(tag: str) -> str:
    return slugify(tag)


def normalize_topic(topic: str | None) -> str | None:
    if topic is None:
        return None
    normalized = slugify(topic)
    return normalized or None


def normalize_language(lang: str) -> str:
    return lang.strip().lower()
```

- [ ] **Step 4: Add validators + `topic` field to `schema.py`**

In `src/brain_mcp/db/schema.py`:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from brain_mcp.db.normalize import normalize_language, normalize_tag, normalize_topic
```

Extend `KnowledgeItemBase`:

```python
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
    def _normalize_tags(cls, value: list[str] | None) -> list[str]:
        if not value:
            return []
        normalized = {normalize_tag(t) for t in value if t and normalize_tag(t)}
        return sorted(normalized)

    @model_validator(mode="after")
    def _check_scope(self):
        if self.scope.type == ScopeType.GLOBAL and self.scope.value is not None:
            raise ValueError("scope=global must not carry a value")
        if self.scope.type != ScopeType.GLOBAL and not self.scope.value:
            raise ValueError(f"scope={self.scope.type.value} requires a non-empty value")
        return self
```

Update `Rule`:

```python
class Rule(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.RULE] = KnowledgeKind.RULE
    priority: int = Field(default=50, ge=0, le=100)
    topic: str | None = None

    @field_validator("topic", mode="before")
    @classmethod
    def _normalize_topic(cls, value: str | None) -> str | None:
        return normalize_topic(value)
```

Update `Snippet`:

```python
class Snippet(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.SNIPPET] = KnowledgeKind.SNIPPET
    language: str
    usage_context: str | None = None

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        normalized = normalize_language(value)
        if not normalized:
            raise ValueError("language is required and cannot be empty")
        return normalized
```

Update `Decision`:

```python
class Decision(KnowledgeItemBase):
    kind: Literal[KnowledgeKind.DECISION] = KnowledgeKind.DECISION
    context: str | None = None
    rationale: str
    alternatives: str | None = None
```

`BugLesson` needs no changes.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/db/test_schema_validators.py -q
```
Expected: **all green**.

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest -q
```
Expected: Phase 1 tests that construct `Rule`/`Snippet` still pass (the normalizers are idempotent on canonical input).

- [ ] **Step 7: Commit**

```bash
git add src/brain_mcp/db/normalize.py src/brain_mcp/db/schema.py tests/db/test_schema_validators.py
git commit -m "feat(schema): tag/topic/language normalizers + scope validator + rule.topic + decision.context"
```

---

### Task 4: `KnowledgeItemPatch` model

**Files:**
- Modify: `src/brain_mcp/db/schema.py`
- Modify: `tests/db/test_schema_validators.py`

- [ ] **Step 1: Add failing test**

Append to `tests/db/test_schema_validators.py`:

```python
from brain_mcp.db.schema import KnowledgeItemPatch


def test_patch_accepts_partial_content_update() -> None:
    patch = KnowledgeItemPatch(content="new content")
    dumped = patch.model_dump(exclude_unset=True)
    assert dumped == {"content": "new content"}


def test_patch_rejects_immutable_fields() -> None:
    with pytest.raises(PydanticValidationError):
        KnowledgeItemPatch(id="xyz")  # id is immutable
    with pytest.raises(PydanticValidationError):
        KnowledgeItemPatch(kind=KnowledgeKind.RULE)
    with pytest.raises(PydanticValidationError):
        KnowledgeItemPatch(created_at=__import__("datetime").datetime.now())


def test_patch_normalizes_tags_like_base() -> None:
    patch = KnowledgeItemPatch(tags=["Python_Async", "effects"])
    assert patch.tags == ["effects", "python-async"]
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/db/test_schema_validators.py::test_patch_accepts_partial_content_update -q
```
Expected: `ImportError`.

- [ ] **Step 3: Add `KnowledgeItemPatch` to `schema.py`**

```python
class KnowledgeItemPatch(BaseModel):
    """Partial update payload for a KnowledgeItem.

    Immutable fields (id, kind, created_at) are not present on this model —
    passing them raises PydanticValidationError via 'extra=forbid'.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    content: str | None = None
    scope: Scope | None = None
    tags: list[str] | None = None

    # kind-specific
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
```

Note `extra="forbid"` is what makes `id=...` / `kind=...` / `created_at=...` raise instead of silently ignoring.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/db/test_schema_validators.py -q
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/brain_mcp/db/schema.py tests/db/test_schema_validators.py
git commit -m "feat(schema): add KnowledgeItemPatch model with immutability guard"
```

---

### Task 5: `serialize_for_embedding` + `content_hash_for` helpers

**Files:**
- Create: `src/brain_mcp/service/__init__.py`
- Create: `src/brain_mcp/service/serializers.py`
- Create: `tests/service/__init__.py`
- Create: `tests/service/test_serializers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/service/test_serializers.py`:

```python
from __future__ import annotations

import hashlib

from brain_mcp.db.schema import BugLesson, Decision, KnowledgeKind, Rule, Scope, ScopeType, Snippet
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
        content="",  # will be synthesized
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
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/service/test_serializers.py -q
```
Expected: `ImportError`.

- [ ] **Step 3: Create the serializer**

`src/brain_mcp/service/__init__.py`:

```python
"""Service layer: knowledge CRUD + scoping + secret-gated writes."""

from brain_mcp.service.knowledge import KnowledgeService  # noqa: F401 — re-export
from brain_mcp.service.serializers import content_hash_for, serialize_for_embedding  # noqa: F401
```

**Wait:** don't import `KnowledgeService` yet — it doesn't exist. For now:

```python
"""Service layer: serializers only until Task 7 introduces KnowledgeService."""

from brain_mcp.service.serializers import content_hash_for, serialize_for_embedding  # noqa: F401
```

`src/brain_mcp/service/serializers.py`:

```python
"""Canonical text representation + hash for knowledge items.

The serialized text is what gets embedded (FTS5 + sqlite-vec). The hash is
computed on the same string, so update-time hash comparison tracks changes
in embedding input exactly — metadata-only updates (tags, priority) never
change the hash.
"""

from __future__ import annotations

import hashlib

from brain_mcp.db.schema import (
    BugLesson,
    Decision,
    KnowledgeItemBase,
    KnowledgeKind,
    Rule,
    Snippet,
)


def serialize_for_embedding(item: KnowledgeItemBase) -> str:
    """Return the canonical string used for embedding + content_hash.

    The serialization is intentionally simple and stable:
        <title>\n\n<body>
    where <body> is kind-specific.
    """
    body = _body_for_kind(item)
    return f"{item.title}\n\n{body}"


def content_hash_for(item: KnowledgeItemBase) -> str:
    """SHA-256 hex digest of the serialized embedding text."""
    return hashlib.sha256(serialize_for_embedding(item).encode()).hexdigest()


def _body_for_kind(item: KnowledgeItemBase) -> str:
    if isinstance(item, Rule):
        return item.content
    if isinstance(item, Snippet):
        return f"language: {item.language}\n\n{item.content}"
    if isinstance(item, Decision):
        lines = [item.content]
        if item.context:
            lines.append(f"context: {item.context}")
        if item.rationale:
            lines.append(f"rationale: {item.rationale}")
        if item.alternatives:
            lines.append(f"alternatives: {item.alternatives}")
        return "\n\n".join(lines)
    if isinstance(item, BugLesson):
        lines = [
            f"symptom: {item.symptom}",
            f"root_cause: {item.root_cause}",
            f"fix: {item.fix}",
        ]
        if item.prevention:
            lines.append(f"prevention: {item.prevention}")
        return "\n\n".join(lines)
    raise TypeError(f"unknown kind: {type(item)}")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/service/test_serializers.py -q
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/brain_mcp/service/__init__.py src/brain_mcp/service/serializers.py tests/service/__init__.py tests/service/test_serializers.py
git commit -m "feat(service): add serialize_for_embedding + content_hash_for helpers"
```

---

### Task 6: `SecretScanner`

**Files:**
- Create: `src/brain_mcp/scanner/__init__.py`
- Create: `src/brain_mcp/scanner/secrets.py`
- Create: `tests/scanner/__init__.py`
- Create: `tests/scanner/test_secret_scanner.py`
- Modify: `pyproject.toml` (add `detect-secrets` dep)

- [ ] **Step 1: Add the dependency**

```bash
uv add detect-secrets
```

- [ ] **Step 2: Write the failing test**

Create `tests/scanner/test_secret_scanner.py`:

```python
from __future__ import annotations

import pytest

from brain_mcp.errors import SecretDetectedError
from brain_mcp.scanner.secrets import SecretScanner


@pytest.fixture(scope="module")
def scanner() -> SecretScanner:
    return SecretScanner()


def test_clean_python_snippet_passes(scanner: SecretScanner) -> None:
    scanner.assert_clean(
        "def add(a, b):\n    return a + b",
        field="content",
    )  # no raise


def test_aws_key_is_detected(scanner: SecretScanner) -> None:
    fake_aws_key = "AKIA" + "I" * 16
    with pytest.raises(SecretDetectedError) as ei:
        scanner.assert_clean(
            f"export AWS_ACCESS_KEY_ID={fake_aws_key}",
            field="content",
        )
    err = ei.value
    assert err.code == "SECRET_DETECTED"
    # The secret value must NOT appear in the error message or details.
    assert fake_aws_key not in str(err)
    assert fake_aws_key not in str(err.details)
    # The hits list must identify a plugin name.
    assert err.details["hits"]
    assert all("plugin" in h for h in err.details["hits"])


def test_private_key_is_detected(scanner: SecretScanner) -> None:
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBA...\n-----END RSA PRIVATE KEY-----"
    with pytest.raises(SecretDetectedError):
        scanner.assert_clean(pem, field="content")


def test_scan_returns_hits_list_for_inspection(scanner: SecretScanner) -> None:
    fake_aws_key = "AKIA" + "J" * 16
    hits = scanner.scan(f"KEY={fake_aws_key}")
    assert hits, "scan should return at least one hit"
    for hit in hits:
        assert "plugin" in hit
        assert "line" in hit
```

- [ ] **Step 3: Run — fail**

```bash
uv run pytest tests/scanner/test_secret_scanner.py -q
```
Expected: `ImportError`.

- [ ] **Step 4: Implement the scanner**

`src/brain_mcp/scanner/__init__.py`:

```python
from brain_mcp.scanner.secrets import SecretScanner  # noqa: F401
```

`src/brain_mcp/scanner/secrets.py`:

```python
"""detect-secrets wrapper for brain-mcp write paths.

Never stores, logs, or returns secret VALUES — only plugin name + line hint.
"""

from __future__ import annotations

from typing import TypedDict

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings

from brain_mcp.errors import SecretDetectedError


class SecretHit(TypedDict):
    plugin: str
    line: int


class SecretScanner:
    """Single-instance scanner reused across requests.

    `detect-secrets` is plugin-based: AWS keys, JWTs, PEMs, Slack tokens,
    high-entropy base64, keywords (password=, secret=, ...).
    """

    def __init__(self) -> None:
        # Holding a live default_settings() context across the lifetime is
        # not supported by detect-secrets — instead we enter it on every scan.
        pass

    def scan(self, text: str) -> list[SecretHit]:
        collection = SecretsCollection()
        with default_settings():
            collection.scan_string(text)
        hits: list[SecretHit] = []
        for _filename, secret in collection:
            hits.append({"plugin": secret.type, "line": int(secret.line_number or 0)})
        return hits

    def assert_clean(self, text: str, *, field: str) -> None:
        hits = self.scan(text)
        if hits:
            raise SecretDetectedError(
                f"Secret detected in field '{field}'",
                details={"field": field, "hits": hits},
            )
```

**Note on `detect-secrets` API:** the `scan_string` method may be named `scan_string` or the collection may need `scan_file`. If `scan_string` does not exist in the installed version, use:

```python
# Alternative: write to a temp file, then scan_file.
import tempfile, os
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
    f.write(text)
    tmp_path = f.name
try:
    with default_settings():
        collection.scan_file(tmp_path)
finally:
    os.unlink(tmp_path)
```

The implementer picks based on the shipped API and sticks with one approach — document which one in a single-line code comment.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/scanner/test_secret_scanner.py -q
```
Expected: all green. If the AWS detector does not fire on the test fixture, adjust the fake key to match the detector's regex exactly (real AWS keys are 20 chars, start with `AKIA`).

- [ ] **Step 6: Commit**

```bash
git add src/brain_mcp/scanner/ tests/scanner/ pyproject.toml uv.lock
git commit -m "feat(scanner): SecretScanner using detect-secrets; never echoes values"
```

---

### Task 7: `resolve_project_id` + `_slugify`

**Files:**
- Create: `src/brain_mcp/scope/__init__.py`
- Create: `src/brain_mcp/scope/project_id.py`
- Create: `tests/scope/__init__.py`
- Create: `tests/scope/test_project_id.py`

- [ ] **Step 1: Write the failing test**

`tests/scope/test_project_id.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from brain_mcp.scope.project_id import resolve_project_id


def test_mcp_roots_wins(tmp_path: Path) -> None:
    (tmp_path / "my-app").mkdir()
    got = resolve_project_id(mcp_roots=[str(tmp_path / "my-app")], cwd=tmp_path)
    assert got == "my-app"


def test_empty_mcp_roots_falls_through(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    got = resolve_project_id(mcp_roots=[], cwd=tmp_path)
    # Falls to the .git walk — tmp_path.name is the project id.
    assert got == resolve_project_id(mcp_roots=None, cwd=tmp_path)


def test_git_walk_finds_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "alpha-repo"
    (repo / ".git").mkdir(parents=True)
    nested = repo / "src" / "inner"
    nested.mkdir(parents=True)
    got = resolve_project_id(mcp_roots=None, cwd=nested)
    assert got == "alpha-repo"


def test_git_file_worktree_is_equivalent_to_dir(tmp_path: Path) -> None:
    repo = tmp_path / "beta"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: ../main/.git\n")
    got = resolve_project_id(mcp_roots=None, cwd=repo)
    assert got == "beta"


def test_no_git_falls_back_to_cwd_basename(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    got = resolve_project_id(mcp_roots=None, cwd=plain)
    assert got == "plain"


def test_unknown_when_everything_fails(tmp_path: Path) -> None:
    # Fabricate a cwd with an unslugifiable name
    weird = tmp_path / "!!!"
    weird.mkdir()
    got = resolve_project_id(mcp_roots=None, cwd=weird)
    assert got == "unknown"


def test_uppercase_and_spaces_slugified(tmp_path: Path) -> None:
    repo = tmp_path / "My Cool App"
    repo.mkdir()
    (repo / ".git").mkdir()
    got = resolve_project_id(mcp_roots=None, cwd=repo)
    assert got == "my-cool-app"
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/scope/test_project_id.py -q
```

- [ ] **Step 3: Implement**

`src/brain_mcp/scope/__init__.py`:

```python
from brain_mcp.scope.project_id import resolve_project_id  # noqa: F401
from brain_mcp.scope.resolver import ScopeResolver  # noqa: F401
```

**BUT:** `ScopeResolver` doesn't exist yet. For now, export only `resolve_project_id`:

```python
from brain_mcp.scope.project_id import resolve_project_id  # noqa: F401
```

`src/brain_mcp/scope/project_id.py`:

```python
"""Resolve a stable project identifier from MCP roots or filesystem."""

from __future__ import annotations

from pathlib import Path

from brain_mcp.db.normalize import slugify


def resolve_project_id(
    *,
    mcp_roots: list[str] | None,
    cwd: Path,
) -> str:
    """Resolution order:

    1. If `mcp_roots` is non-empty, return slugify(first_root.name).
    2. Walk from cwd upward; if a directory contains .git (dir or file),
       return slugify(that_dir.name).
    3. Return slugify(cwd.name).
    4. If everything slugifies to empty, return "unknown".
    """
    if mcp_roots:
        first = Path(mcp_roots[0])
        return slugify(first.name) or "unknown"

    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".git").exists():
            return slugify(candidate.name) or "unknown"

    return slugify(cwd.name) or "unknown"
```

- [ ] **Step 4: Run tests — pass**

```bash
uv run pytest tests/scope/test_project_id.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/brain_mcp/scope/__init__.py src/brain_mcp/scope/project_id.py tests/scope/__init__.py tests/scope/test_project_id.py
git commit -m "feat(scope): resolve_project_id with MCP roots -> .git walk -> cwd fallback"
```

---

### Task 8: `ScopeResolver.build_filter`

**Files:**
- Create: `src/brain_mcp/scope/resolver.py`
- Modify: `src/brain_mcp/scope/__init__.py`
- Create: `tests/scope/test_resolver.py`

- [ ] **Step 1: Write the failing test**

`tests/scope/test_resolver.py`:

```python
from __future__ import annotations

from brain_mcp.scope.resolver import ScopeResolver


def test_filter_global_only_when_no_context() -> None:
    sql, params = ScopeResolver.build_filter(project_id=None, language=None)
    assert "scope_type = 'global'" in sql
    assert params == {}


def test_filter_includes_project_when_given() -> None:
    sql, params = ScopeResolver.build_filter(project_id="brain", language=None)
    assert "scope_type='global'" in sql.replace(" ", "")
    assert ":project_id" in sql
    assert params == {"project_id": "brain"}


def test_filter_includes_language_when_given() -> None:
    sql, params = ScopeResolver.build_filter(project_id=None, language="python")
    assert ":language" in sql
    assert params == {"language": "python"}


def test_filter_is_parenthesized() -> None:
    sql, _ = ScopeResolver.build_filter(project_id="brain", language="python")
    assert sql.startswith("(")
    assert sql.endswith(")")
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/scope/test_resolver.py -q
```

- [ ] **Step 3: Implement**

`src/brain_mcp/scope/resolver.py`:

```python
"""ScopeResolver: SQL filter builder + read-time rule override."""

from __future__ import annotations

from typing import Any

from brain_mcp.db.schema import Rule


class ScopeResolver:
    """Stateless helper. Two static methods, nothing else."""

    @staticmethod
    def build_filter(
        *,
        project_id: str | None,
        language: str | None,
    ) -> tuple[str, dict[str, Any]]:
        """Return a parenthesized SQL fragment + params dict.

        Matches rows whose scope is global, or matches the given project_id,
        or matches the given language. If both project_id and language are
        None, collapses to `(scope_type = 'global')`.
        """
        clauses = ["scope_type = 'global'"]
        params: dict[str, Any] = {}
        if project_id is not None:
            clauses.append("(scope_type = 'project' AND scope_value = :project_id)")
            params["project_id"] = project_id
        if language is not None:
            clauses.append("(scope_type = 'language' AND scope_value = :language)")
            params["language"] = language
        return "(" + " OR ".join(clauses) + ")", params

    @staticmethod
    def apply_rule_override(
        rules: list[Rule],
        *,
        project_id: str | None,
    ) -> list[Rule]:
        """Filter a rule list so project-scoped topics hide same-topic globals.

        - Rules without a topic are always kept.
        - A rule with scope=project and topic=T hides every rule with
          scope=global and topic=T from the returned list.
        - Order is preserved.
        """
        suppressed_topics: set[str] = {
            r.topic for r in rules
            if r.topic
            and r.scope.type.value == "project"
            and (project_id is None or r.scope.value == project_id)
        }
        out: list[Rule] = []
        for r in rules:
            if (
                r.topic
                and r.topic in suppressed_topics
                and r.scope.type.value == "global"
            ):
                continue
            out.append(r)
        return out
```

Update `src/brain_mcp/scope/__init__.py`:

```python
from brain_mcp.scope.project_id import resolve_project_id  # noqa: F401
from brain_mcp.scope.resolver import ScopeResolver  # noqa: F401
```

- [ ] **Step 4: Run build_filter tests — pass**

```bash
uv run pytest tests/scope/test_resolver.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/brain_mcp/scope/resolver.py src/brain_mcp/scope/__init__.py tests/scope/test_resolver.py
git commit -m "feat(scope): ScopeResolver.build_filter returns parenthesized SQL + params"
```

---

### Task 9: `ScopeResolver.apply_rule_override`

**Files:**
- Modify: `tests/scope/test_resolver.py`

- [ ] **Step 1: Append failing tests**

```python
import pytest

from brain_mcp.db.schema import KnowledgeKind, Rule, Scope, ScopeType


def _rule(topic: str | None, scope_type: ScopeType, scope_value: str | None, title: str) -> Rule:
    return Rule(
        title=title,
        content=title,
        scope=Scope(type=scope_type, value=scope_value),
        device_id="dev1",
        topic=topic,
    )


def test_override_hides_global_when_project_has_same_topic() -> None:
    g = _rule("style", ScopeType.GLOBAL, None, "global-style")
    p = _rule("style", ScopeType.PROJECT, "brain", "project-style")
    result = ScopeResolver.apply_rule_override([g, p], project_id="brain")
    titles = [r.title for r in result]
    assert titles == ["project-style"]


def test_override_keeps_global_when_topics_differ() -> None:
    g = _rule("format", ScopeType.GLOBAL, None, "g-format")
    p = _rule("tests", ScopeType.PROJECT, "brain", "p-tests")
    result = ScopeResolver.apply_rule_override([g, p], project_id="brain")
    assert [r.title for r in result] == ["g-format", "p-tests"]


def test_override_never_touches_topicless_rules() -> None:
    g = _rule(None, ScopeType.GLOBAL, None, "g-none")
    p = _rule("x", ScopeType.PROJECT, "brain", "p-x")
    result = ScopeResolver.apply_rule_override([g, p], project_id="brain")
    assert [r.title for r in result] == ["g-none", "p-x"]


def test_override_preserves_order() -> None:
    a = _rule("x", ScopeType.PROJECT, "brain", "first")
    b = _rule("y", ScopeType.GLOBAL, None, "second")
    c = _rule("x", ScopeType.GLOBAL, None, "third-hidden")
    d = _rule(None, ScopeType.GLOBAL, None, "fourth")
    result = ScopeResolver.apply_rule_override([a, b, c, d], project_id="brain")
    assert [r.title for r in result] == ["first", "second", "fourth"]
```

- [ ] **Step 2: Run — pass (implementation already done in Task 8)**

```bash
uv run pytest tests/scope/test_resolver.py -q
```
Expected: all green. If any fail, fix `apply_rule_override` and re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/scope/test_resolver.py
git commit -m "test(scope): cover apply_rule_override topic override + order preservation"
```

---

### Task 10: `FakeEmbedder` test fixture + `KnowledgeService.create` (rule)

**Files:**
- Create: `tests/conftest.py` (or modify if it exists)
- Create: `src/brain_mcp/service/knowledge.py`
- Modify: `src/brain_mcp/service/__init__.py`
- Create: `tests/service/test_knowledge_service_crud.py`

- [ ] **Step 1: Add fake embedder fixture**

Append (or create) `tests/conftest.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import ALEMBIC_CFG_PATH


class FakeEmbedder:
    """Deterministic in-memory embedder for tests."""

    model_id = "fake-embed-v1"

    def __init__(self) -> None:
        self.document_calls: list[str] = []
        self.query_calls: list[str] = []

    def embed_document(self, text: str) -> list[float]:
        self.document_calls.append(text)
        return self._vector(text)

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        return [(h[i % 32] / 256.0) for i in range(768)]


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fresh_db(tmp_path: Path):
    """A brand-new SQLite DB migrated to head, yielded as a connection."""
    db = tmp_path / "brain.db"
    cfg = Config(str(ALEMBIC_CFG_PATH))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    conn = connect(db)
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 2: Write the failing service test**

Create `tests/service/test_knowledge_service_crud.py`:

```python
from __future__ import annotations

from brain_mcp.db.schema import KnowledgeKind, Rule, Scope, ScopeType
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver
from brain_mcp.service.knowledge import KnowledgeService


def _svc(fresh_db, fake_embedder) -> KnowledgeService:
    return KnowledgeService(
        conn=fresh_db,
        embedder=fake_embedder,
        scanner=SecretScanner(),
        scope_resolver=ScopeResolver(),
    )


def test_create_rule_persists_row_and_tags_and_vector(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    rule = Rule(
        title="Always use ruff",
        content="Use ruff format on save.",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
        tags=["Python", "tooling"],
    )
    saved = svc.create(rule)

    # Core row
    row = fresh_db.execute("SELECT id, kind, title FROM knowledge_items WHERE id=?", (saved.id,)).fetchone()
    assert row is not None
    assert row[1] == "rule"
    assert row[2] == "Always use ruff"

    # Extension row
    ext = fresh_db.execute("SELECT priority, topic FROM rules WHERE item_id=?", (saved.id,)).fetchone()
    assert ext == (50, None)

    # Tags junction
    tags = {r[0] for r in fresh_db.execute("SELECT tag FROM knowledge_tags WHERE item_id=?", (saved.id,)).fetchall()}
    assert tags == {"python", "tooling"}

    # Vector row
    vec = fresh_db.execute("SELECT vec_rowid, embedding_model_id FROM vec_rowid_map WHERE item_id=?", (saved.id,)).fetchone()
    assert vec is not None
    assert vec[1] == "fake-embed-v1"

    # content_hash was populated
    h = fresh_db.execute("SELECT content_hash FROM knowledge_items WHERE id=?", (saved.id,)).fetchone()[0]
    assert h and len(h) == 64

    # Embedder was called exactly once for embed_document
    assert len(fake_embedder.document_calls) == 1
```

- [ ] **Step 3: Run — fail**

```bash
uv run pytest tests/service/test_knowledge_service_crud.py -q
```
Expected: `ImportError` on `KnowledgeService`.

- [ ] **Step 4: Implement `KnowledgeService.create`**

`src/brain_mcp/service/knowledge.py`:

```python
"""KnowledgeService: CRUD + list + search stub for all four knowledge kinds."""

from __future__ import annotations

import json
import sqlite3
import struct
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from brain_mcp.db.connection import transaction
from brain_mcp.db.schema import (
    BugLesson,
    Decision,
    KnowledgeItemBase,
    KnowledgeItemPatch,
    KnowledgeKind,
    Rule,
    Snippet,
)
from brain_mcp.errors import NotFoundError, SecretDetectedError, ValidationError
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver
from brain_mcp.service.serializers import content_hash_for, serialize_for_embedding


def _serialize_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class KnowledgeService:
    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        embedder: Any,            # Protocol: embed_document, embed_query, model_id
        scanner: SecretScanner,
        scope_resolver: ScopeResolver,
    ) -> None:
        self.conn = conn
        self.embedder = embedder
        self.scanner = scanner
        self.scope_resolver = scope_resolver

    # ---- CREATE ----------------------------------------------------------

    def create(self, item: KnowledgeItemBase) -> KnowledgeItemBase:
        self._scan_writable_fields(item)

        embed_text = serialize_for_embedding(item)
        item_hash = content_hash_for(item)

        with transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO knowledge_items
                (id, kind, title, content, scope_type, scope_value,
                 created_at, updated_at, sync_id, device_id, synced_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.kind.value,
                    item.title,
                    item.content,
                    item.scope.type.value,
                    item.scope.value,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                    item.sync_id,
                    item.device_id,
                    item.synced_at.isoformat() if item.synced_at else None,
                    item_hash,
                ),
            )
            self._insert_extension_row(item)
            self._replace_tags(item.id, item.tags)
            self._insert_vector(item.id, embed_text)

        # Re-hydrate the Pydantic with the stored hash so callers see it.
        return item.model_copy(update={"content_hash": item_hash})

    # ---- helpers ---------------------------------------------------------

    def _scan_writable_fields(self, item: KnowledgeItemBase) -> None:
        # Scan the user-provided text bodies. The serializer output is also
        # scanned so synthesized content (e.g. BugLesson body) is covered.
        self.scanner.assert_clean(item.title, field="title")
        self.scanner.assert_clean(item.content, field="content")
        if isinstance(item, Decision):
            if item.context:
                self.scanner.assert_clean(item.context, field="context")
            self.scanner.assert_clean(item.rationale, field="rationale")
            if item.alternatives:
                self.scanner.assert_clean(item.alternatives, field="alternatives")
        elif isinstance(item, BugLesson):
            self.scanner.assert_clean(item.symptom, field="symptom")
            self.scanner.assert_clean(item.root_cause, field="root_cause")
            self.scanner.assert_clean(item.fix, field="fix")
            if item.prevention:
                self.scanner.assert_clean(item.prevention, field="prevention")

    def _insert_extension_row(self, item: KnowledgeItemBase) -> None:
        if isinstance(item, Rule):
            self.conn.execute(
                "INSERT INTO rules (item_id, priority, topic) VALUES (?, ?, ?)",
                (item.id, item.priority, item.topic),
            )
        elif isinstance(item, Snippet):
            self.conn.execute(
                "INSERT INTO snippets (item_id, language, usage_context) VALUES (?, ?, ?)",
                (item.id, item.language, item.usage_context),
            )
        elif isinstance(item, Decision):
            self.conn.execute(
                "INSERT INTO decisions (item_id, context, rationale, alternatives) VALUES (?, ?, ?, ?)",
                (item.id, item.context, item.rationale, item.alternatives),
            )
        elif isinstance(item, BugLesson):
            self.conn.execute(
                "INSERT INTO bug_lessons (item_id, symptom, root_cause, fix, prevention) VALUES (?, ?, ?, ?, ?)",
                (item.id, item.symptom, item.root_cause, item.fix, item.prevention),
            )
        else:
            raise ValidationError(
                f"unknown kind: {type(item).__name__}",
                details={"kind": getattr(item, "kind", None)},
            )

    def _replace_tags(self, item_id: str, tags: list[str]) -> None:
        self.conn.execute("DELETE FROM knowledge_tags WHERE item_id=?", (item_id,))
        self.conn.executemany(
            "INSERT INTO knowledge_tags (item_id, tag) VALUES (?, ?)",
            [(item_id, t) for t in tags],
        )

    def _insert_vector(self, item_id: str, embed_text: str) -> None:
        vec = self.embedder.embed_document(embed_text)
        self.conn.execute(
            "INSERT INTO knowledge_vec (embedding) VALUES (?)",
            (_serialize_vector(vec),),
        )
        vec_rowid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.conn.execute(
            """
            INSERT INTO vec_rowid_map (vec_rowid, item_id, chunk_index, embedding_model_id, created_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (vec_rowid, item_id, self.embedder.model_id, _now_iso()),
        )
```

Update `src/brain_mcp/service/__init__.py`:

```python
from brain_mcp.service.knowledge import KnowledgeService  # noqa: F401
from brain_mcp.service.serializers import content_hash_for, serialize_for_embedding  # noqa: F401
```

- [ ] **Step 5: Run the create test**

```bash
uv run pytest tests/service/test_knowledge_service_crud.py::test_create_rule_persists_row_and_tags_and_vector -q
```
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/brain_mcp/service/knowledge.py src/brain_mcp/service/__init__.py tests/conftest.py tests/service/test_knowledge_service_crud.py
git commit -m "feat(service): KnowledgeService.create for rules with tags + vector + hash"
```

---

### Task 11: `KnowledgeService.create` for snippet / decision / bug_lesson

**Files:**
- Modify: `tests/service/test_knowledge_service_crud.py`

The implementation already handles all four kinds (`_insert_extension_row` dispatches by type). Only need tests to cover them.

- [ ] **Step 1: Add tests for the other three kinds**

```python
from brain_mcp.db.schema import BugLesson, Decision, Snippet


def test_create_snippet(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    sn = Snippet(
        title="Retry helper",
        content="def retry(fn): ...",
        scope=Scope(type=ScopeType.LANGUAGE, value="python"),
        device_id="dev1",
        language="Python",
        usage_context="HTTP clients",
    )
    saved = svc.create(sn)
    row = fresh_db.execute("SELECT language, usage_context FROM snippets WHERE item_id=?", (saved.id,)).fetchone()
    assert row == ("python", "HTTP clients")


def test_create_decision(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    d = Decision(
        title="Use SQLite",
        content="We will use SQLite for v1.",
        scope=Scope(type=ScopeType.PROJECT, value="brain"),
        device_id="dev1",
        context="Single-user, local-first.",
        rationale="Zero install friction.",
        alternatives="Postgres, DuckDB.",
    )
    saved = svc.create(d)
    row = fresh_db.execute(
        "SELECT context, rationale, alternatives FROM decisions WHERE item_id=?",
        (saved.id,),
    ).fetchone()
    assert row == ("Single-user, local-first.", "Zero install friction.", "Postgres, DuckDB.")


def test_create_bug_lesson(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    bug = BugLesson(
        title="SameSite redirect loss",
        content="User cookies lost on cross-site redirect.",
        scope=Scope(type=ScopeType.PROJECT, value="brain"),
        device_id="dev1",
        symptom="Random logouts",
        root_cause="SameSite=Strict",
        fix="Set SameSite=Lax",
        prevention="Test redirects in CI",
    )
    saved = svc.create(bug)
    row = fresh_db.execute(
        "SELECT symptom, root_cause, fix, prevention FROM bug_lessons WHERE item_id=?",
        (saved.id,),
    ).fetchone()
    assert row == ("Random logouts", "SameSite=Strict", "Set SameSite=Lax", "Test redirects in CI")
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/service/test_knowledge_service_crud.py -q
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add tests/service/test_knowledge_service_crud.py
git commit -m "test(service): cover create for snippet/decision/bug_lesson"
```

---

### Task 12: `KnowledgeService.get`

**Files:**
- Modify: `src/brain_mcp/service/knowledge.py`
- Modify: `tests/service/test_knowledge_service_crud.py`

- [ ] **Step 1: Append failing test**

```python
import pytest

from brain_mcp.errors import NotFoundError


def test_get_returns_rule(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    rule = Rule(
        title="T", content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
    )
    saved = svc.create(rule)
    got = svc.get(saved.id)
    assert got.id == saved.id
    assert isinstance(got, Rule)


def test_get_missing_raises_not_found(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    with pytest.raises(NotFoundError) as ei:
        svc.get("nonexistent")
    assert ei.value.code == "NOT_FOUND"
```

- [ ] **Step 2: Implement `get`**

Add to `KnowledgeService`:

```python
    # ---- READ ------------------------------------------------------------

    def get(self, item_id: str) -> KnowledgeItemBase:
        row = self.conn.execute(
            """
            SELECT id, kind, title, content, scope_type, scope_value,
                   created_at, updated_at, sync_id, device_id, synced_at, content_hash
            FROM knowledge_items WHERE id=?
            """,
            (item_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"knowledge item not found: {item_id}", details={"id": item_id})
        return self._hydrate(row)

    def _hydrate(self, row: tuple) -> KnowledgeItemBase:
        from brain_mcp.db.schema import Scope, ScopeType
        (
            item_id, kind, title, content, scope_type, scope_value,
            created_at, updated_at, sync_id, device_id, synced_at, content_hash,
        ) = row
        tags = [r[0] for r in self.conn.execute(
            "SELECT tag FROM knowledge_tags WHERE item_id=? ORDER BY tag",
            (item_id,),
        ).fetchall()]
        base_kwargs = dict(
            id=item_id,
            title=title,
            content=content,
            scope=Scope(type=ScopeType(scope_type), value=scope_value),
            tags=tags,
            content_hash=content_hash,
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at),
            sync_id=sync_id,
            device_id=device_id,
            synced_at=datetime.fromisoformat(synced_at) if synced_at else None,
        )
        if kind == "rule":
            ext = self.conn.execute(
                "SELECT priority, topic FROM rules WHERE item_id=?", (item_id,),
            ).fetchone()
            return Rule(**base_kwargs, priority=ext[0], topic=ext[1])
        if kind == "snippet":
            ext = self.conn.execute(
                "SELECT language, usage_context FROM snippets WHERE item_id=?", (item_id,),
            ).fetchone()
            return Snippet(**base_kwargs, language=ext[0], usage_context=ext[1])
        if kind == "decision":
            ext = self.conn.execute(
                "SELECT context, rationale, alternatives FROM decisions WHERE item_id=?", (item_id,),
            ).fetchone()
            return Decision(**base_kwargs, context=ext[0], rationale=ext[1], alternatives=ext[2])
        if kind == "bug_lesson":
            ext = self.conn.execute(
                "SELECT symptom, root_cause, fix, prevention FROM bug_lessons WHERE item_id=?", (item_id,),
            ).fetchone()
            return BugLesson(
                **base_kwargs,
                symptom=ext[0], root_cause=ext[1], fix=ext[2], prevention=ext[3],
            )
        raise ValidationError(f"unknown kind in DB: {kind}", details={"id": item_id})
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/service/test_knowledge_service_crud.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/service/knowledge.py tests/service/test_knowledge_service_crud.py
git commit -m "feat(service): KnowledgeService.get + _hydrate for all kinds"
```

---

### Task 13: `KnowledgeService.delete`

**Files:**
- Modify: `src/brain_mcp/service/knowledge.py`
- Modify: `tests/service/test_knowledge_service_crud.py`

- [ ] **Step 1: Failing test**

```python
def test_delete_removes_core_and_extension_and_vector(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    rule = Rule(
        title="T", content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
    )
    saved = svc.create(rule)
    svc.delete(saved.id)
    assert fresh_db.execute("SELECT 1 FROM knowledge_items WHERE id=?", (saved.id,)).fetchone() is None
    assert fresh_db.execute("SELECT 1 FROM rules WHERE item_id=?", (saved.id,)).fetchone() is None
    assert fresh_db.execute("SELECT 1 FROM vec_rowid_map WHERE item_id=?", (saved.id,)).fetchone() is None


def test_delete_missing_raises_not_found(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    with pytest.raises(NotFoundError):
        svc.delete("missing")
```

- [ ] **Step 2: Implement**

Append to `KnowledgeService`:

```python
    # ---- DELETE ----------------------------------------------------------

    def delete(self, item_id: str) -> None:
        with transaction(self.conn):
            # Look up vec rowids before deleting knowledge_items so we can
            # drop them from the virtual table explicitly (FK cascade only
            # covers vec_rowid_map, not the vec0 virtual table).
            vec_rowids = [
                r[0] for r in self.conn.execute(
                    "SELECT vec_rowid FROM vec_rowid_map WHERE item_id=?",
                    (item_id,),
                ).fetchall()
            ]
            cursor = self.conn.execute("DELETE FROM knowledge_items WHERE id=?", (item_id,))
            if cursor.rowcount == 0:
                raise NotFoundError(f"cannot delete: {item_id}", details={"id": item_id})
            for rowid in vec_rowids:
                self.conn.execute("DELETE FROM knowledge_vec WHERE rowid=?", (rowid,))
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/service/test_knowledge_service_crud.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/service/knowledge.py tests/service/test_knowledge_service_crud.py
git commit -m "feat(service): KnowledgeService.delete with cascade + vec cleanup"
```

---

### Task 14: `KnowledgeService.update` with content-hash re-embed

**Files:**
- Modify: `src/brain_mcp/service/knowledge.py`
- Create: `tests/service/test_knowledge_service_reembed.py`

- [ ] **Step 1: Failing test**

`tests/service/test_knowledge_service_reembed.py`:

```python
from __future__ import annotations

import pytest

from brain_mcp.db.schema import KnowledgeItemPatch, Rule, Scope, ScopeType
from brain_mcp.errors import NotFoundError, ValidationError
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver
from brain_mcp.service.knowledge import KnowledgeService


def _svc(db, embedder):
    return KnowledgeService(conn=db, embedder=embedder, scanner=SecretScanner(), scope_resolver=ScopeResolver())


def _seed_rule(svc) -> Rule:
    return svc.create(Rule(
        title="original", content="original body",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
    ))


def test_metadata_only_update_does_not_reembed(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    saved = _seed_rule(svc)
    assert len(fake_embedder.document_calls) == 1

    svc.update(saved.id, KnowledgeItemPatch(tags=["new-tag"], priority=90))

    # No additional embedder call
    assert len(fake_embedder.document_calls) == 1

    # Tags stored
    tags = {r[0] for r in fresh_db.execute("SELECT tag FROM knowledge_tags WHERE item_id=?", (saved.id,))}
    assert tags == {"new-tag"}

    # Priority updated
    prio = fresh_db.execute("SELECT priority FROM rules WHERE item_id=?", (saved.id,)).fetchone()[0]
    assert prio == 90


def test_content_change_triggers_reembed(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    saved = _seed_rule(svc)
    assert len(fake_embedder.document_calls) == 1

    svc.update(saved.id, KnowledgeItemPatch(content="brand new body text"))

    assert len(fake_embedder.document_calls) == 2
    new_hash = fresh_db.execute("SELECT content_hash FROM knowledge_items WHERE id=?", (saved.id,)).fetchone()[0]
    assert new_hash != saved.content_hash


def test_update_missing_raises_not_found(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    with pytest.raises(NotFoundError):
        svc.update("missing", KnowledgeItemPatch(title="x"))


def test_update_bumps_sync_id_and_updated_at(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    saved = _seed_rule(svc)
    row_before = fresh_db.execute("SELECT sync_id, updated_at FROM knowledge_items WHERE id=?", (saved.id,)).fetchone()
    svc.update(saved.id, KnowledgeItemPatch(title="renamed"))
    row_after = fresh_db.execute("SELECT sync_id, updated_at FROM knowledge_items WHERE id=?", (saved.id,)).fetchone()
    assert row_before[0] != row_after[0]
    assert row_before[1] != row_after[1]
```

- [ ] **Step 2: Implement `update`**

Append to `KnowledgeService`:

```python
    # ---- UPDATE ----------------------------------------------------------

    def update(self, item_id: str, patch: KnowledgeItemPatch) -> KnowledgeItemBase:
        current = self.get(item_id)  # raises NotFoundError if missing
        updates = patch.model_dump(exclude_unset=True)

        # Merge patch over current, producing a new model instance of the same kind.
        merged_data = current.model_dump()
        merged_data.update(updates)
        merged_data["updated_at"] = datetime.now(tz=UTC)
        merged_data["sync_id"] = uuid4().hex

        merged: KnowledgeItemBase
        if isinstance(current, Rule):
            merged = Rule(**merged_data)
        elif isinstance(current, Snippet):
            merged = Snippet(**merged_data)
        elif isinstance(current, Decision):
            merged = Decision(**merged_data)
        elif isinstance(current, BugLesson):
            merged = BugLesson(**merged_data)
        else:
            raise ValidationError("unknown kind during update", details={"id": item_id})

        # Secret scan BEFORE persisting anything.
        self._scan_writable_fields(merged)

        new_hash = content_hash_for(merged)
        hash_changed = current.content_hash != new_hash

        with transaction(self.conn):
            self.conn.execute(
                """
                UPDATE knowledge_items
                SET title=?, content=?, scope_type=?, scope_value=?, updated_at=?, sync_id=?, content_hash=?
                WHERE id=?
                """,
                (
                    merged.title, merged.content,
                    merged.scope.type.value, merged.scope.value,
                    merged.updated_at.isoformat(),
                    merged.sync_id,
                    new_hash,
                    item_id,
                ),
            )
            self._replace_tags(item_id, merged.tags)
            self._update_extension_row(merged)
            if hash_changed:
                self._replace_vector(item_id, serialize_for_embedding(merged))

        return merged.model_copy(update={"content_hash": new_hash})

    def _update_extension_row(self, item: KnowledgeItemBase) -> None:
        if isinstance(item, Rule):
            self.conn.execute(
                "UPDATE rules SET priority=?, topic=? WHERE item_id=?",
                (item.priority, item.topic, item.id),
            )
        elif isinstance(item, Snippet):
            self.conn.execute(
                "UPDATE snippets SET language=?, usage_context=? WHERE item_id=?",
                (item.language, item.usage_context, item.id),
            )
        elif isinstance(item, Decision):
            self.conn.execute(
                "UPDATE decisions SET context=?, rationale=?, alternatives=? WHERE item_id=?",
                (item.context, item.rationale, item.alternatives, item.id),
            )
        elif isinstance(item, BugLesson):
            self.conn.execute(
                "UPDATE bug_lessons SET symptom=?, root_cause=?, fix=?, prevention=? WHERE item_id=?",
                (item.symptom, item.root_cause, item.fix, item.prevention, item.id),
            )

    def _replace_vector(self, item_id: str, embed_text: str) -> None:
        old_rowids = [
            r[0] for r in self.conn.execute(
                "SELECT vec_rowid FROM vec_rowid_map WHERE item_id=?", (item_id,),
            ).fetchall()
        ]
        for rowid in old_rowids:
            self.conn.execute("DELETE FROM knowledge_vec WHERE rowid=?", (rowid,))
        self.conn.execute("DELETE FROM vec_rowid_map WHERE item_id=?", (item_id,))
        self._insert_vector(item_id, embed_text)
```

- [ ] **Step 3: Run reembed tests**

```bash
uv run pytest tests/service/test_knowledge_service_reembed.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/service/knowledge.py tests/service/test_knowledge_service_reembed.py
git commit -m "feat(service): KnowledgeService.update with content-hash re-embed"
```

---

### Task 15: `KnowledgeService.list` — scope filter + tag AND + pagination + override

**Files:**
- Modify: `src/brain_mcp/service/knowledge.py`
- Create: `tests/service/test_knowledge_service_list.py`

- [ ] **Step 1: Failing test**

`tests/service/test_knowledge_service_list.py`:

```python
from __future__ import annotations

from brain_mcp.db.schema import KnowledgeKind, Rule, Scope, ScopeType
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver
from brain_mcp.service.knowledge import KnowledgeService


def _svc(db, embedder):
    return KnowledgeService(conn=db, embedder=embedder, scanner=SecretScanner(), scope_resolver=ScopeResolver())


def _mk(svc, **kwargs) -> Rule:
    defaults = dict(
        title="T", content="C",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
    )
    defaults.update(kwargs)
    return svc.create(Rule(**defaults))


def test_list_hard_filter_by_project(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    _mk(svc, title="glob")
    _mk(svc, title="proj-a", scope=Scope(type=ScopeType.PROJECT, value="a"))
    _mk(svc, title="proj-b", scope=Scope(type=ScopeType.PROJECT, value="b"))

    result = svc.list(
        kind=KnowledgeKind.RULE,
        scope_type=None,
        scope_value=None,
        tags=None,
        project_id="a",
    )
    titles = {i.title for i in result.items}
    assert titles == {"glob", "proj-a"}


def test_list_applies_rule_override(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    _mk(svc, title="g", topic="style")
    _mk(svc, title="p", scope=Scope(type=ScopeType.PROJECT, value="brain"), topic="style")

    result = svc.list(
        kind=KnowledgeKind.RULE,
        scope_type=None, scope_value=None, tags=None,
        project_id="brain",
    )
    titles = [i.title for i in result.items]
    assert titles == ["p"]


def test_list_tag_and_filter(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    _mk(svc, title="py-only", tags=["python"])
    _mk(svc, title="both", tags=["python", "async"])
    _mk(svc, title="async-only", tags=["async"])

    result = svc.list(
        kind=KnowledgeKind.RULE,
        scope_type=None, scope_value=None,
        tags=["python", "async"],
        project_id=None,
    )
    titles = {i.title for i in result.items}
    assert titles == {"both"}


def test_list_pagination_and_clamp(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    for i in range(5):
        _mk(svc, title=f"r{i}")

    page1 = svc.list(
        kind=KnowledgeKind.RULE, scope_type=None, scope_value=None,
        tags=None, project_id=None, limit=2, offset=0,
    )
    page2 = svc.list(
        kind=KnowledgeKind.RULE, scope_type=None, scope_value=None,
        tags=None, project_id=None, limit=2, offset=2,
    )
    assert len(page1.items) == 2
    assert len(page2.items) == 2
    # No overlap
    assert {i.id for i in page1.items}.isdisjoint({i.id for i in page2.items})

    # Clamp: limit 10_000 is capped to 500
    clamped = svc.list(
        kind=KnowledgeKind.RULE, scope_type=None, scope_value=None,
        tags=None, project_id=None, limit=10000, offset=0,
    )
    assert len(clamped.items) <= 500
```

- [ ] **Step 2: Implement**

Add to `KnowledgeService`:

```python
from dataclasses import dataclass, field

@dataclass
class KnowledgeList:
    items: list[KnowledgeItemBase]
    returned: int
    total_after_override: int
```

Then:

```python
    # ---- LIST ------------------------------------------------------------

    MAX_LIMIT = 500

    def list(
        self,
        *,
        kind: KnowledgeKind | None,
        scope_type,              # ScopeType | None
        scope_value: str | None,
        tags: list[str] | None,
        project_id: str | None,
        limit: int = 50,
        offset: int = 0,
    ) -> "KnowledgeList":
        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)

        scope_sql, scope_params = self.scope_resolver.build_filter(
            project_id=project_id,
            language=scope_value if (scope_type and scope_type.value == "language") else None,
        )

        clauses: list[str] = [scope_sql]
        params: dict[str, Any] = dict(scope_params)

        if kind is not None:
            clauses.append("kind = :kind")
            params["kind"] = kind.value

        if scope_type is not None:
            clauses.append("scope_type = :explicit_scope_type")
            params["explicit_scope_type"] = scope_type.value
            if scope_value is not None:
                clauses.append("scope_value = :explicit_scope_value")
                params["explicit_scope_value"] = scope_value

        if tags:
            # AND semantics: item must have every tag.
            for idx, tag in enumerate(tags):
                key = f"tag_{idx}"
                clauses.append(
                    f"id IN (SELECT item_id FROM knowledge_tags WHERE tag = :{key})"
                )
                params[key] = tag

        where = " AND ".join(clauses)
        sql = f"""
            SELECT id FROM knowledge_items
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT :hard_cap
        """
        params["hard_cap"] = self.MAX_LIMIT

        ids = [row[0] for row in self.conn.execute(sql, params).fetchall()]
        hydrated = [self.get(item_id) for item_id in ids]

        # Apply rule override only over rules — unaffected for other kinds.
        if kind == KnowledgeKind.RULE or kind is None:
            rules = [i for i in hydrated if isinstance(i, Rule)]
            non_rules = [i for i in hydrated if not isinstance(i, Rule)]
            rules = self.scope_resolver.apply_rule_override(rules, project_id=project_id)
            # Preserve original interleaved order: we reconstruct by id.
            kept_ids = {r.id for r in rules} | {n.id for n in non_rules}
            hydrated = [i for i in hydrated if i.id in kept_ids]

        total = len(hydrated)
        page = hydrated[offset : offset + limit]
        return KnowledgeList(items=page, returned=len(page), total_after_override=total)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/service/test_knowledge_service_list.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/service/knowledge.py tests/service/test_knowledge_service_list.py
git commit -m "feat(service): KnowledgeService.list with scope filter + tag AND + override + pagination"
```

---

### Task 16: `KnowledgeService.search` stub

**Files:**
- Modify: `src/brain_mcp/service/knowledge.py`
- Create: `tests/service/test_knowledge_service_search.py`

- [ ] **Step 1: Failing test**

`tests/service/test_knowledge_service_search.py`:

```python
from __future__ import annotations

from brain_mcp.db.schema import KnowledgeKind, Rule, Scope, ScopeType
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver
from brain_mcp.service.knowledge import KnowledgeService


def _svc(db, embedder):
    return KnowledgeService(conn=db, embedder=embedder, scanner=SecretScanner(), scope_resolver=ScopeResolver())


def test_search_matches_in_title_and_content(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    svc.create(Rule(
        title="ruff formatting", content="Always use ruff",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
    ))
    svc.create(Rule(
        title="pytest", content="Run pytest -q",
        scope=Scope(type=ScopeType.GLOBAL),
        device_id="dev1",
    ))

    result = svc.search(query="ruff", kind=KnowledgeKind.RULE, project_id=None)
    titles = {i.title for i in result.items}
    assert titles == {"ruff formatting"}


def test_search_respects_scope(fresh_db, fake_embedder) -> None:
    svc = _svc(fresh_db, fake_embedder)
    svc.create(Rule(
        title="proj only", content="Secret to project",
        scope=Scope(type=ScopeType.PROJECT, value="a"),
        device_id="dev1",
    ))
    result = svc.search(query="Secret", kind=KnowledgeKind.RULE, project_id="b")
    assert result.items == []
```

- [ ] **Step 2: Implement**

```python
    # ---- SEARCH STUB (Phase 3 replaces this with hybrid RRF) -------------

    def search(
        self,
        *,
        query: str,
        kind: KnowledgeKind | None,
        project_id: str | None,
    ) -> "KnowledgeList":
        scope_sql, scope_params = self.scope_resolver.build_filter(
            project_id=project_id, language=None,
        )
        clauses = [scope_sql, "(title LIKE :like OR content LIKE :like)"]
        params: dict[str, Any] = dict(scope_params)
        params["like"] = f"%{query}%"
        if kind is not None:
            clauses.append("kind = :kind")
            params["kind"] = kind.value
        sql = f"""
            SELECT id FROM knowledge_items
            WHERE {" AND ".join(clauses)}
            ORDER BY updated_at DESC
            LIMIT 50
        """
        ids = [row[0] for row in self.conn.execute(sql, params).fetchall()]
        hydrated = [self.get(item_id) for item_id in ids]
        return KnowledgeList(items=hydrated, returned=len(hydrated), total_after_override=len(hydrated))
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/service/test_knowledge_service_search.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/service/knowledge.py tests/service/test_knowledge_service_search.py
git commit -m "feat(service): KnowledgeService.search (Phase 2 structured stub)"
```

---

### Task 17: `BrainContext` + MCP error translator

**Files:**
- Create: `src/brain_mcp/mcp/__init__.py`
- Create: `src/brain_mcp/mcp/context.py`
- Create: `src/brain_mcp/mcp/errors.py`
- Create: `tests/mcp/__init__.py`
- Create: `tests/mcp/test_error_contract.py`

- [ ] **Step 1: Failing test**

`tests/mcp/test_error_contract.py`:

```python
from __future__ import annotations

import json

from brain_mcp.errors import (
    NotFoundError,
    ScopeError,
    SecretDetectedError,
    ValidationError,
)
from brain_mcp.mcp.errors import error_response


def _parse(resp: dict) -> dict:
    return json.loads(resp["content"][0]["text"])


def test_secret_detected_translates() -> None:
    err = SecretDetectedError("nope", details={"field": "content", "hits": []})
    resp = error_response(err)
    assert resp["isError"] is True
    body = _parse(resp)
    assert body["code"] == "SECRET_DETECTED"
    assert body["details"]["field"] == "content"


def test_not_found_translates() -> None:
    resp = error_response(NotFoundError("missing", details={"id": "x"}))
    assert _parse(resp)["code"] == "NOT_FOUND"


def test_validation_error_translates() -> None:
    resp = error_response(ValidationError("bad", details={"field": "title"}))
    assert _parse(resp)["code"] == "VALIDATION_ERROR"


def test_scope_error_translates() -> None:
    resp = error_response(ScopeError("bad scope", details={"scope_type": "project"}))
    assert _parse(resp)["code"] == "SCOPE_INVALID"
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/mcp/test_error_contract.py -q
```

- [ ] **Step 3: Implement**

`src/brain_mcp/mcp/__init__.py`:

```python
"""MCP server surface: BrainContext, tool handlers, error translator, resource."""
```

`src/brain_mcp/mcp/context.py`:

```python
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from typing import Any

from brain_mcp.paths import BrainPaths
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver
from brain_mcp.service.knowledge import KnowledgeService


@dataclass(frozen=True)
class BrainContext:
    conn: sqlite3.Connection
    embedder: Any
    scanner: SecretScanner
    scope_resolver: ScopeResolver
    paths: BrainPaths
    lock: asyncio.Lock

    def service(self) -> KnowledgeService:
        return KnowledgeService(
            conn=self.conn,
            embedder=self.embedder,
            scanner=self.scanner,
            scope_resolver=self.scope_resolver,
        )
```

`src/brain_mcp/mcp/errors.py`:

```python
from __future__ import annotations

import json

from brain_mcp.errors import BrainError


def error_response(err: BrainError) -> dict:
    """Convert a BrainError into a FastMCP isError payload."""
    body = {
        "code": err.code,
        "message": str(err),
        "details": err.details,
    }
    return {
        "isError": True,
        "content": [{"type": "text", "text": json.dumps(body, ensure_ascii=False)}],
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/mcp/test_error_contract.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/brain_mcp/mcp/ tests/mcp/__init__.py tests/mcp/test_error_contract.py
git commit -m "feat(mcp): BrainContext + error_response translator"
```

---

### Task 18: FastMCP server + lifespan + `main()`

**Files:**
- Create: `src/brain_mcp/mcp/server.py`
- Create: `tests/mcp/test_server_lifespan.py`

- [ ] **Step 1: Failing test**

`tests/mcp/test_server_lifespan.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from brain_mcp.errors import BrainError


def test_main_fails_fast_when_db_missing(tmp_path: Path, monkeypatch) -> None:
    # Point BRAIN_HOME at an empty directory so the DB doesn't exist.
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    from brain_mcp.mcp.server import lifespan_context_sync_check

    with pytest.raises(BrainError) as ei:
        lifespan_context_sync_check(tmp_path / "brain.db")
    assert ei.value.code == "DB_NOT_INITIALIZED"


def test_logging_is_stderr_only_after_server_init(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    from brain_mcp.logging import configure_logging
    configure_logging(stderr_only=True)
    logger = logging.getLogger("brain_mcp.test")
    logger.error("stderr line")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "stderr line" in captured.err
```

- [ ] **Step 2: Implement**

`src/brain_mcp/mcp/server.py`:

```python
"""Brain MCP stdio server entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from brain_mcp.db.connection import connect
from brain_mcp.embedding.service import EmbeddingService
from brain_mcp.errors import BrainError
from brain_mcp.logging import configure_logging
from brain_mcp.mcp.context import BrainContext
from brain_mcp.paths import BrainPaths
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver

logger = logging.getLogger("brain_mcp.mcp.server")


def lifespan_context_sync_check(db_path: Path) -> None:
    """Raise BrainError if the DB file is missing.

    Split out for direct unit-testing without spinning the full lifespan.
    """
    if not db_path.exists():
        raise BrainError(
            f"Database not found at {db_path}. Run 'brain init' first.",
            details={"db_path": str(db_path)},
        ).with_code("DB_NOT_INITIALIZED")


# Monkey-patch for code clarity: BrainError needs a way to set a one-off code
# without subclassing. Add once in errors.py during this task if not present:
#
#     def with_code(self, code: str) -> "BrainError":
#         self.code = code
#         return self


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[BrainContext]:
    configure_logging(stderr_only=True)
    paths = BrainPaths.from_env()
    lifespan_context_sync_check(paths.db_path)

    conn = connect(paths.db_path)
    try:
        ctx = BrainContext(
            conn=conn,
            embedder=EmbeddingService(paths=paths),
            scanner=SecretScanner(),
            scope_resolver=ScopeResolver(),
            paths=paths,
            lock=asyncio.Lock(),
        )
        yield ctx
    finally:
        conn.close()


app = FastMCP("brain", lifespan=lifespan)


def main() -> None:
    try:
        app.run()
    except BrainError as e:
        logger.error("startup failed: %s (%s)", e, e.code)
        sys.exit(2)
```

Add the `with_code` helper to `errors.py`:

```python
class BrainError(Exception):
    code: str = "BRAIN_ERROR"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}

    def with_code(self, code: str) -> "BrainError":
        self.code = code
        return self
```

(Only add if the existing base lacks `with_code`.)

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/mcp/test_server_lifespan.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/mcp/server.py src/brain_mcp/errors.py tests/mcp/test_server_lifespan.py
git commit -m "feat(mcp): FastMCP app + lifespan + main() + db missing fast-fail"
```

---

### Task 19: Tool handlers — register `brain_capture`

**Files:**
- Create: `src/brain_mcp/mcp/tools.py`
- Modify: `src/brain_mcp/mcp/server.py` (import tools so registration runs)
- Create: `tests/mcp/test_server_capture.py`

For MCP end-to-end tests, use FastMCP's in-process tool invocation. The pattern is: construct the server, enter the lifespan with a fake embedder, call the registered tool function directly.

- [ ] **Step 1: Create a test helper for in-process MCP**

Append to `tests/conftest.py`:

```python
import asyncio
from contextlib import asynccontextmanager

from brain_mcp.mcp.context import BrainContext
from brain_mcp.scanner.secrets import SecretScanner
from brain_mcp.scope.resolver import ScopeResolver


@pytest.fixture
def mcp_context(fresh_db, fake_embedder, tmp_path) -> BrainContext:
    """A lifespan-equivalent BrainContext for in-process tool handler tests."""
    # BrainPaths is Phase 1 — build a lightweight stand-in if needed.
    class _Paths:
        db_path = tmp_path / "brain.db"
        brain_home = tmp_path
        model_cache = tmp_path / "models"
    return BrainContext(
        conn=fresh_db,
        embedder=fake_embedder,
        scanner=SecretScanner(),
        scope_resolver=ScopeResolver(),
        paths=_Paths(),  # type: ignore[arg-type]
        lock=asyncio.Lock(),
    )
```

- [ ] **Step 2: Failing test**

`tests/mcp/test_server_capture.py`:

```python
from __future__ import annotations

import asyncio
import json

import pytest

from brain_mcp.mcp.tools import brain_capture_impl


def _call(fn, **kwargs):
    return asyncio.run(fn(**kwargs))


def test_capture_rule_happy_path(mcp_context) -> None:
    result = _call(
        brain_capture_impl,
        ctx=mcp_context,
        mcp_roots=None,
        cwd=".",
        kind="rule",
        title="Use ruff",
        content="Always use ruff for formatting",
        scope_type="global",
        scope_value=None,
        tags=["python"],
    )
    assert "id" in result
    assert result["kind"] == "rule"


def test_capture_blocks_on_secret(mcp_context) -> None:
    fake_aws_key = "AKIA" + "K" * 16
    result = _call(
        brain_capture_impl,
        ctx=mcp_context,
        mcp_roots=None,
        cwd=".",
        kind="rule",
        title="export",
        content=f"export AWS_ACCESS_KEY_ID={fake_aws_key}",
        scope_type="global",
        scope_value=None,
        tags=None,
    )
    assert result["isError"] is True
    body = json.loads(result["content"][0]["text"])
    assert body["code"] == "SECRET_DETECTED"


def test_capture_validation_error_missing_snippet_fields(mcp_context) -> None:
    result = _call(
        brain_capture_impl,
        ctx=mcp_context,
        mcp_roots=None,
        cwd=".",
        kind="snippet",
        title="missing language",
        content="print(1)",
        scope_type="global",
        scope_value=None,
        tags=None,
        # language intentionally omitted
    )
    assert result["isError"] is True
    body = json.loads(result["content"][0]["text"])
    assert body["code"] == "VALIDATION_ERROR"


def test_capture_project_default_fills_scope_value(mcp_context) -> None:
    result = _call(
        brain_capture_impl,
        ctx=mcp_context,
        mcp_roots=["/tmp/my-project"],
        cwd=".",
        kind="rule",
        title="project rule",
        content="only in my project",
        scope_type="project",
        scope_value=None,   # should default to my-project
        tags=None,
    )
    assert result["scope_value"] == "my-project"
```

- [ ] **Step 3: Implement `tools.py` and `brain_capture`**

`src/brain_mcp/mcp/tools.py`:

```python
"""MCP tool handlers for the brain server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_mcp.db.schema import (
    BugLesson,
    Decision,
    KnowledgeKind,
    Rule,
    Scope,
    ScopeType,
    Snippet,
)
from brain_mcp.errors import BrainError, ValidationError
from brain_mcp.mcp.context import BrainContext
from brain_mcp.mcp.errors import error_response
from brain_mcp.mcp.server import app
from brain_mcp.scope.project_id import resolve_project_id

CAPTURE_DESC = (
    "Save a new piece of knowledge so it survives across sessions. "
    "Use when the user says 'save this rule', 'remember this', 'add a snippet', "
    "'log this decision', or 'write down this bug fix'. "
    "'kind' picks the type: rule for preferences, snippet for reusable code, "
    "decision for architectural choices, bug_lesson for fixes. "
    "'scope_type=project' ties it to the current project; 'global' makes it apply everywhere."
)


async def brain_capture_impl(
    *,
    ctx: BrainContext,
    mcp_roots: list[str] | None,
    cwd: str,
    kind: str,
    title: str,
    content: str,
    scope_type: str = "global",
    scope_value: str | None = None,
    tags: list[str] | None = None,
    priority: int | None = None,
    topic: str | None = None,
    language: str | None = None,
    usage_context: str | None = None,
    context: str | None = None,
    rationale: str | None = None,
    alternatives: str | None = None,
    symptom: str | None = None,
    root_cause: str | None = None,
    fix: str | None = None,
    prevention: str | None = None,
    device_id: str = "local",
) -> dict:
    async with ctx.lock:
        try:
            project_id = resolve_project_id(mcp_roots=mcp_roots, cwd=Path(cwd))
            if scope_type == "project" and scope_value is None:
                scope_value = project_id
            scope = Scope(type=ScopeType(scope_type), value=scope_value)
            item = _build_item_for_kind(
                kind=kind, title=title, content=content, scope=scope,
                tags=tags or [], device_id=device_id,
                priority=priority, topic=topic,
                language=language, usage_context=usage_context,
                context=context, rationale=rationale, alternatives=alternatives,
                symptom=symptom, root_cause=root_cause, fix=fix, prevention=prevention,
            )
            saved = ctx.service().create(item)
            return _serialize_item_for_tool_response(saved)
        except BrainError as e:
            return error_response(e)
        except Exception as e:
            return error_response(
                ValidationError(str(e), details={"type": type(e).__name__})
            )


def _build_item_for_kind(*, kind: str, **kwargs):
    if kind == "rule":
        return Rule(
            title=kwargs["title"], content=kwargs["content"],
            scope=kwargs["scope"], tags=kwargs["tags"], device_id=kwargs["device_id"],
            priority=kwargs.get("priority") or 50,
            topic=kwargs.get("topic"),
        )
    if kind == "snippet":
        lang = kwargs.get("language")
        if not lang:
            raise ValidationError("snippet requires 'language'", details={"field": "language"})
        return Snippet(
            title=kwargs["title"], content=kwargs["content"],
            scope=kwargs["scope"], tags=kwargs["tags"], device_id=kwargs["device_id"],
            language=lang,
            usage_context=kwargs.get("usage_context"),
        )
    if kind == "decision":
        rat = kwargs.get("rationale")
        if not rat:
            raise ValidationError("decision requires 'rationale'", details={"field": "rationale"})
        return Decision(
            title=kwargs["title"], content=kwargs["content"],
            scope=kwargs["scope"], tags=kwargs["tags"], device_id=kwargs["device_id"],
            context=kwargs.get("context"),
            rationale=rat,
            alternatives=kwargs.get("alternatives"),
        )
    if kind == "bug_lesson":
        required = {"symptom", "root_cause", "fix"}
        missing = [k for k in required if not kwargs.get(k)]
        if missing:
            raise ValidationError(
                f"bug_lesson requires: {', '.join(missing)}",
                details={"fields": missing},
            )
        return BugLesson(
            title=kwargs["title"], content=kwargs["content"],
            scope=kwargs["scope"], tags=kwargs["tags"], device_id=kwargs["device_id"],
            symptom=kwargs["symptom"],
            root_cause=kwargs["root_cause"],
            fix=kwargs["fix"],
            prevention=kwargs.get("prevention"),
        )
    raise ValidationError(f"unknown kind: {kind}", details={"kind": kind})


def _serialize_item_for_tool_response(item) -> dict:
    d = item.model_dump(mode="json")
    # Flatten scope for tool response shape.
    scope = d.pop("scope")
    d["scope_type"] = scope["type"]
    d["scope_value"] = scope["value"]
    return d


# FastMCP registration: thin wrapper that extracts roots/cwd from context.
@app.tool(description=CAPTURE_DESC)
async def brain_capture(
    ctx,                            # FastMCP-injected request context
    kind: str,
    title: str,
    content: str,
    scope_type: str = "global",
    scope_value: str | None = None,
    tags: list[str] | None = None,
    priority: int | None = None,
    topic: str | None = None,
    language: str | None = None,
    usage_context: str | None = None,
    context: str | None = None,
    rationale: str | None = None,
    alternatives: str | None = None,
    symptom: str | None = None,
    root_cause: str | None = None,
    fix: str | None = None,
    prevention: str | None = None,
) -> dict:
    bctx: BrainContext = ctx.request_context.lifespan_context
    return await brain_capture_impl(
        ctx=bctx,
        mcp_roots=getattr(ctx, "roots", None),
        cwd=str(Path.cwd()),
        kind=kind, title=title, content=content,
        scope_type=scope_type, scope_value=scope_value, tags=tags,
        priority=priority, topic=topic,
        language=language, usage_context=usage_context,
        context=context, rationale=rationale, alternatives=alternatives,
        symptom=symptom, root_cause=root_cause, fix=fix, prevention=prevention,
    )
```

Add to `src/brain_mcp/mcp/server.py` **at the bottom** (after `app = FastMCP(...)`):

```python
# Import registers tool handlers on `app`. MUST be last so `app` exists first.
from brain_mcp.mcp import tools  # noqa: E402, F401
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/mcp/test_server_capture.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/brain_mcp/mcp/tools.py src/brain_mcp/mcp/server.py tests/conftest.py tests/mcp/test_server_capture.py
git commit -m "feat(mcp): brain_capture tool with lock + project_id default + error translation"
```

---

### Task 20: `brain_get`, `brain_update`, `brain_delete` tool handlers

**Files:**
- Modify: `src/brain_mcp/mcp/tools.py`
- Create: `tests/mcp/test_server_crud.py`

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations

import asyncio
import json

from brain_mcp.mcp.tools import (
    brain_capture_impl,
    brain_delete_impl,
    brain_get_impl,
    brain_update_impl,
)


def _call(fn, **kwargs):
    return asyncio.run(fn(**kwargs))


def _seed(ctx) -> dict:
    return _call(
        brain_capture_impl,
        ctx=ctx, mcp_roots=None, cwd=".",
        kind="rule", title="T", content="C",
        scope_type="global", scope_value=None, tags=None,
    )


def test_get_happy(mcp_context) -> None:
    created = _seed(mcp_context)
    got = _call(brain_get_impl, ctx=mcp_context, item_id=created["id"])
    assert got["id"] == created["id"]


def test_get_not_found(mcp_context) -> None:
    got = _call(brain_get_impl, ctx=mcp_context, item_id="missing")
    assert got["isError"] is True
    assert json.loads(got["content"][0]["text"])["code"] == "NOT_FOUND"


def test_update_happy(mcp_context) -> None:
    created = _seed(mcp_context)
    updated = _call(
        brain_update_impl,
        ctx=mcp_context,
        item_id=created["id"],
        patch={"content": "new content"},
    )
    assert updated["content"] == "new content"


def test_update_rejects_immutable(mcp_context) -> None:
    created = _seed(mcp_context)
    result = _call(
        brain_update_impl,
        ctx=mcp_context,
        item_id=created["id"],
        patch={"id": "tamper"},
    )
    assert result["isError"] is True


def test_delete_happy_then_get_is_404(mcp_context) -> None:
    created = _seed(mcp_context)
    _call(brain_delete_impl, ctx=mcp_context, item_id=created["id"])
    got = _call(brain_get_impl, ctx=mcp_context, item_id=created["id"])
    assert got["isError"] is True
```

- [ ] **Step 2: Implement**

Append to `tools.py`:

```python
from brain_mcp.db.schema import KnowledgeItemPatch

GET_DESC = (
    "Fetch a single saved knowledge item by id. Use when you already have "
    "an id (from a previous capture or list/search call) and need the full record."
)
UPDATE_DESC = (
    "Update fields of a saved knowledge item. Immutable: id, kind, created_at. "
    "Re-embeds only if content changes. Use when editing a rule or snippet."
)
DELETE_DESC = (
    "Permanently delete a saved knowledge item by id. No soft-delete. Use when "
    "the user asks to remove a rule or says something is wrong and should be forgotten."
)


async def brain_get_impl(*, ctx: BrainContext, item_id: str) -> dict:
    async with ctx.lock:
        try:
            item = ctx.service().get(item_id)
            return _serialize_item_for_tool_response(item)
        except BrainError as e:
            return error_response(e)


async def brain_update_impl(*, ctx: BrainContext, item_id: str, patch: dict) -> dict:
    async with ctx.lock:
        try:
            try:
                model_patch = KnowledgeItemPatch(**patch)
            except Exception as e:
                raise ValidationError(f"invalid patch: {e}", details={"raw": patch})
            updated = ctx.service().update(item_id, model_patch)
            return _serialize_item_for_tool_response(updated)
        except BrainError as e:
            return error_response(e)


async def brain_delete_impl(*, ctx: BrainContext, item_id: str) -> dict:
    async with ctx.lock:
        try:
            ctx.service().delete(item_id)
            return {"ok": True, "id": item_id}
        except BrainError as e:
            return error_response(e)


@app.tool(description=GET_DESC)
async def brain_get(ctx, item_id: str) -> dict:
    bctx: BrainContext = ctx.request_context.lifespan_context
    return await brain_get_impl(ctx=bctx, item_id=item_id)


@app.tool(description=UPDATE_DESC)
async def brain_update(ctx, item_id: str, patch: dict) -> dict:
    bctx: BrainContext = ctx.request_context.lifespan_context
    return await brain_update_impl(ctx=bctx, item_id=item_id, patch=patch)


@app.tool(description=DELETE_DESC)
async def brain_delete(ctx, item_id: str) -> dict:
    bctx: BrainContext = ctx.request_context.lifespan_context
    return await brain_delete_impl(ctx=bctx, item_id=item_id)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/mcp/test_server_crud.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/mcp/tools.py tests/mcp/test_server_crud.py
git commit -m "feat(mcp): brain_get + brain_update + brain_delete tool handlers"
```

---

### Task 21: `brain_list` and `brain_search` tool handlers

**Files:**
- Modify: `src/brain_mcp/mcp/tools.py`
- Create: `tests/mcp/test_server_list_and_search.py`

- [ ] **Step 1: Failing test**

```python
from __future__ import annotations

import asyncio
import json

from brain_mcp.mcp.tools import (
    brain_capture_impl,
    brain_list_impl,
    brain_search_impl,
)


def _call(fn, **kwargs):
    return asyncio.run(fn(**kwargs))


def _seed(ctx, title, **kw) -> dict:
    return _call(
        brain_capture_impl,
        ctx=ctx, mcp_roots=None, cwd=".",
        kind="rule", title=title, content=title,
        scope_type="global", scope_value=None, tags=None,
        **kw,
    )


def test_list_returns_structured_result(mcp_context) -> None:
    _seed(mcp_context, "a")
    _seed(mcp_context, "b")
    result = _call(
        brain_list_impl,
        ctx=mcp_context,
        kind="rule", scope_type=None, scope_value=None,
        tags=None, mcp_roots=None, cwd=".",
        limit=50, offset=0,
    )
    assert "items" in result
    assert len(result["items"]) == 2
    assert result["returned"] == 2


def test_search_returns_structured_result(mcp_context) -> None:
    _seed(mcp_context, "ruff formatting")
    _seed(mcp_context, "pytest usage")
    result = _call(
        brain_search_impl,
        ctx=mcp_context,
        query="ruff", kind="rule",
        mcp_roots=None, cwd=".",
    )
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "ruff formatting"
```

- [ ] **Step 2: Implement**

Append to `tools.py`:

```python
LIST_DESC = (
    "List saved knowledge items filtered by kind/scope/tags. "
    "Use when the user asks to see what they've saved, "
    "or when you need to browse before deciding what to use."
)
SEARCH_DESC = (
    "Search saved knowledge by free-text query. Use when the user asks "
    "'how did we do X before?' or 'did we save anything about Y?'. "
    "Returns items matching the query in title or body."
)


async def brain_list_impl(
    *,
    ctx: BrainContext,
    kind: str | None,
    scope_type: str | None,
    scope_value: str | None,
    tags: list[str] | None,
    mcp_roots: list[str] | None,
    cwd: str,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    async with ctx.lock:
        try:
            project_id = resolve_project_id(mcp_roots=mcp_roots, cwd=Path(cwd))
            result = ctx.service().list(
                kind=KnowledgeKind(kind) if kind else None,
                scope_type=ScopeType(scope_type) if scope_type else None,
                scope_value=scope_value,
                tags=tags,
                project_id=project_id,
                limit=limit,
                offset=offset,
            )
            return {
                "items": [_serialize_item_for_tool_response(i) for i in result.items],
                "returned": result.returned,
                "total_after_override": result.total_after_override,
            }
        except BrainError as e:
            return error_response(e)


async def brain_search_impl(
    *,
    ctx: BrainContext,
    query: str,
    kind: str | None,
    mcp_roots: list[str] | None,
    cwd: str,
) -> dict:
    async with ctx.lock:
        try:
            project_id = resolve_project_id(mcp_roots=mcp_roots, cwd=Path(cwd))
            result = ctx.service().search(
                query=query,
                kind=KnowledgeKind(kind) if kind else None,
                project_id=project_id,
            )
            return {
                "items": [_serialize_item_for_tool_response(i) for i in result.items],
                "returned": result.returned,
            }
        except BrainError as e:
            return error_response(e)


@app.tool(description=LIST_DESC)
async def brain_list(
    ctx,
    kind: str | None = None,
    scope_type: str | None = None,
    scope_value: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    bctx: BrainContext = ctx.request_context.lifespan_context
    return await brain_list_impl(
        ctx=bctx, kind=kind, scope_type=scope_type, scope_value=scope_value,
        tags=tags, mcp_roots=getattr(ctx, "roots", None), cwd=str(Path.cwd()),
        limit=limit, offset=offset,
    )


@app.tool(description=SEARCH_DESC)
async def brain_search(ctx, query: str, kind: str | None = None) -> dict:
    bctx: BrainContext = ctx.request_context.lifespan_context
    return await brain_search_impl(
        ctx=bctx, query=query, kind=kind,
        mcp_roots=getattr(ctx, "roots", None), cwd=str(Path.cwd()),
    )
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/mcp/test_server_list_and_search.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/mcp/tools.py tests/mcp/test_server_list_and_search.py
git commit -m "feat(mcp): brain_list + brain_search tool handlers"
```

---

### Task 22: `session_context` Resource

**Files:**
- Create: `src/brain_mcp/mcp/resources.py`
- Modify: `src/brain_mcp/mcp/server.py` (import resources after tools)
- Create: `tests/mcp/test_server_resource.py`

- [ ] **Step 1: Failing test**

`tests/mcp/test_server_resource.py`:

```python
from __future__ import annotations

import asyncio

from brain_mcp.db.schema import Rule, Scope, ScopeType
from brain_mcp.mcp.resources import render_briefing_markdown, session_context_impl


def _seed(svc, title, scope, topic=None):
    svc.create(Rule(
        title=title, content=title,
        scope=scope, device_id="dev1",
        topic=topic,
    ))


def test_render_includes_global_and_project_sections() -> None:
    md = render_briefing_markdown([], [])
    assert "# Brain" in md
    assert "## Global rules" in md
    assert "## Project rules" in md


def test_resource_lists_seeded_rules(mcp_context) -> None:
    svc = mcp_context.service()
    _seed(svc, "global-rule", Scope(type=ScopeType.GLOBAL))
    _seed(svc, "project-rule", Scope(type=ScopeType.PROJECT, value="brain"))

    md = asyncio.run(session_context_impl(ctx=mcp_context, project_id="brain"))
    assert "global-rule" in md
    assert "project-rule" in md


def test_resource_applies_override(mcp_context) -> None:
    svc = mcp_context.service()
    _seed(svc, "global-style", Scope(type=ScopeType.GLOBAL), topic="style")
    _seed(svc, "project-style", Scope(type=ScopeType.PROJECT, value="brain"), topic="style")

    md = asyncio.run(session_context_impl(ctx=mcp_context, project_id="brain"))
    assert "project-style" in md
    assert "global-style" not in md
```

- [ ] **Step 2: Implement**

`src/brain_mcp/mcp/resources.py`:

```python
from __future__ import annotations

from brain_mcp.db.schema import KnowledgeKind, Rule, ScopeType
from brain_mcp.mcp.context import BrainContext
from brain_mcp.mcp.server import app


def render_briefing_markdown(global_rules: list[Rule], project_rules: list[Rule]) -> str:
    lines = ["# Brain: session context", "", "## Global rules", ""]
    if not global_rules:
        lines.append("_(none saved yet)_")
    for r in global_rules:
        lines.append(f"- **{r.title}**: {r.content}")
        if r.topic:
            lines[-1] += f"  _(topic: {r.topic})_"
    lines += ["", "## Project rules", ""]
    if not project_rules:
        lines.append("_(none saved yet)_")
    for r in project_rules:
        lines.append(f"- **{r.title}**: {r.content}")
        if r.topic:
            lines[-1] += f"  _(topic: {r.topic})_"
    return "\n".join(lines) + "\n"


async def session_context_impl(*, ctx: BrainContext, project_id: str) -> str:
    async with ctx.lock:
        svc = ctx.service()
        global_list = svc.list(
            kind=KnowledgeKind.RULE, scope_type=ScopeType.GLOBAL,
            scope_value=None, tags=None, project_id=project_id, limit=200,
        )
        project_list = svc.list(
            kind=KnowledgeKind.RULE, scope_type=ScopeType.PROJECT,
            scope_value=project_id, tags=None, project_id=project_id, limit=200,
        )
        return render_briefing_markdown(
            [i for i in global_list.items if isinstance(i, Rule)],
            [i for i in project_list.items if isinstance(i, Rule)],
        )


@app.resource("brain://session/{project_id}/context")
async def session_context(project_id: str) -> str:
    # FastMCP injects ctx via a different call shape for resources —
    # the implementer confirms the exact signature from the SDK docs
    # at task time (either `session_context(ctx, project_id)` or via
    # an implicit request_context lookup).
    from mcp.server.fastmcp.server import get_request_context  # type: ignore
    req_ctx = get_request_context()
    bctx: BrainContext = req_ctx.lifespan_context
    return await session_context_impl(ctx=bctx, project_id=project_id)
```

Import at the bottom of `server.py` **after** `from brain_mcp.mcp import tools`:

```python
from brain_mcp.mcp import resources  # noqa: E402, F401
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/mcp/test_server_resource.py -q
```

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/mcp/resources.py src/brain_mcp/mcp/server.py tests/mcp/test_server_resource.py
git commit -m "feat(mcp): session_context Resource with rule briefing + override"
```

---

### Task 23: `pyproject.toml` entry point + tool count guard

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/mcp/test_tool_count.py`

- [ ] **Step 1: Add entry point**

Edit `pyproject.toml` `[project.scripts]` table (or add if missing):

```toml
[project.scripts]
brain = "brain_mcp.cli:app"
brain-server = "brain_mcp.mcp.server:main"
```

- [ ] **Step 2: Failing tool count test**

`tests/mcp/test_tool_count.py`:

```python
from __future__ import annotations


def test_registered_tool_count_under_limit() -> None:
    # Importing the server registers all tools.
    from brain_mcp.mcp import server  # noqa: F401
    from brain_mcp.mcp.server import app

    tools = app.list_tools() if hasattr(app, "list_tools") else list(app._tools.values())  # type: ignore[attr-defined]
    assert len(tools) <= 8, f"Got {len(tools)} tools; MCP-06 cap is 8"
    # Expected exact set
    names = {t.name if hasattr(t, "name") else getattr(t, "__name__", "") for t in tools}
    assert "brain_capture" in names
    assert "brain_get" in names
    assert "brain_update" in names
    assert "brain_delete" in names
    assert "brain_list" in names
    assert "brain_search" in names
```

**Implementer note:** FastMCP's registered-tool introspection API changed across minor versions. If neither `list_tools()` nor `_tools` works, use `app.list_tools_sync()` (sync variant) or inspect `app._tool_manager._tools`. Pick the one that works in the pinned version and leave a one-line comment.

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/mcp/test_tool_count.py -q
```

- [ ] **Step 4: Smoke test `brain-server` startup**

```bash
uv sync
uv run brain init
uv run timeout 2 brain-server < /dev/null || true
```

Expected: server starts, logs to stderr, hangs waiting for stdin (which is closed by the redirect), exits cleanly. No stdout output, no tracebacks.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/mcp/test_tool_count.py
git commit -m "feat(pkg): add brain-server entry point + tool count guard"
```

---

### Task 24: Full-surface integration sweep + Phase 2 close

**Files:**
- Modify: `tests/mcp/test_server_lifespan.py` (add a full end-to-end stdout/stderr assertion)

- [ ] **Step 1: Full suite run**

```bash
uv run pytest -q
```
Expected: **all green**, ~76 tests total.

- [ ] **Step 2: Manual MCP Inspector smoke**

Run:

```bash
uv run mcp dev brain_mcp.mcp.server
```

In the Inspector UI, verify:

1. `brain init` completed and `~/.brain/brain.db` exists before launching inspector (if not, inspector will show DB_NOT_INITIALIZED — expected).
2. Tool list shows exactly: `brain_capture`, `brain_get`, `brain_update`, `brain_delete`, `brain_list`, `brain_search` (6 tools).
3. Call `brain_capture kind=rule title="test" content="hello" scope_type=global` — returns a JSON item with an id.
4. Call `brain_list kind=rule` — returns the just-saved rule.
5. Call `brain_capture kind=rule title="leaky" content="AKIA" + "X"*16` — returns `isError=true` with `code=SECRET_DETECTED`.
6. Read resource `brain://session/brain/context` — returns a Markdown briefing listing the saved rule.
7. Confirm zero stdout contamination in the inspector's server logs tab.

Record observations (pass/fail per step) in a short note appended to `.planning/phases/02-knowledge-crud-scoping-mcp-core/PROGRESS.md`.

- [ ] **Step 3: Success criteria review**

Walk through ROADMAP.md Phase 2 success criteria and confirm each is green:

| # | Criterion | Where verified |
|---|---|---|
| 1 | `brain_search` respects scope across projects | `tests/service/test_knowledge_service_list.py::test_list_hard_filter_by_project` + Inspector step 4 |
| 2 | Secret blocked in ANY write path | `tests/mcp/test_server_capture.py::test_capture_blocks_on_secret` |
| 3 | MCP Inspector returns structured results | Inspector step 3 + `tests/mcp/test_server_list_and_search.py` |
| 4 | No `print()` on stdout | `tests/mcp/test_server_lifespan.py::test_logging_is_stderr_only_after_server_init` + Inspector step 7 |
| 5 | Schema count ≤ 8 | `tests/mcp/test_tool_count.py` |

- [ ] **Step 4: Commit the phase close**

```bash
git add .planning/phases/02-knowledge-crud-scoping-mcp-core/PROGRESS.md
git commit -m "chore(phase-2): close — all success criteria verified, 76+ tests green"
```

---

## Appendix A: Commit message quick reference

| Task | Suggested message |
|---|---|
| 1 | `feat(db): add migration 0002 (topic, content_hash, decisions.context)` |
| 2 | `feat(errors): add phase 2 error subclasses (secret, not_found, validation, scope)` |
| 3 | `feat(schema): tag/topic/language normalizers + scope validator + rule.topic + decision.context` |
| 4 | `feat(schema): add KnowledgeItemPatch model with immutability guard` |
| 5 | `feat(service): add serialize_for_embedding + content_hash_for helpers` |
| 6 | `feat(scanner): SecretScanner using detect-secrets; never echoes values` |
| 7 | `feat(scope): resolve_project_id with MCP roots -> .git walk -> cwd fallback` |
| 8 | `feat(scope): ScopeResolver.build_filter returns parenthesized SQL + params` |
| 9 | `test(scope): cover apply_rule_override topic override + order preservation` |
| 10 | `feat(service): KnowledgeService.create for rules with tags + vector + hash` |
| 11 | `test(service): cover create for snippet/decision/bug_lesson` |
| 12 | `feat(service): KnowledgeService.get + _hydrate for all kinds` |
| 13 | `feat(service): KnowledgeService.delete with cascade + vec cleanup` |
| 14 | `feat(service): KnowledgeService.update with content-hash re-embed` |
| 15 | `feat(service): KnowledgeService.list with scope filter + tag AND + override + pagination` |
| 16 | `feat(service): KnowledgeService.search (Phase 2 structured stub)` |
| 17 | `feat(mcp): BrainContext + error_response translator` |
| 18 | `feat(mcp): FastMCP app + lifespan + main() + db missing fast-fail` |
| 19 | `feat(mcp): brain_capture tool with lock + project_id default + error translation` |
| 20 | `feat(mcp): brain_get + brain_update + brain_delete tool handlers` |
| 21 | `feat(mcp): brain_list + brain_search tool handlers` |
| 22 | `feat(mcp): session_context Resource with rule briefing + override` |
| 23 | `feat(pkg): add brain-server entry point + tool count guard` |
| 24 | `chore(phase-2): close — all success criteria verified, 76+ tests green` |

## Appendix B: Known API-version risks

1. **`detect-secrets` scan API** — `scan_string` vs `scan_file`. Task 6 documents the fallback.
2. **FastMCP tool enumeration** — `list_tools()` vs `_tool_manager._tools`. Task 23 documents the fallback.
3. **FastMCP resource handler signature** — whether `ctx` is injected as the first argument or retrieved via a module-level helper. Task 22 documents the fallback.
4. **Alembic `batch_alter_table` + `ADD COLUMN`** — plain `ALTER TABLE ADD COLUMN` works on SQLite without batch mode; batch is only required for `DROP COLUMN` and rename operations. Task 1 uses batch uniformly for consistency.
5. **sqlite-vec row deletion on virtual table** — `DELETE FROM knowledge_vec WHERE rowid=?` should work since vec0 supports rowid-based delete. If the deployed version requires a different syntax, Task 13 and 14 are the places to patch.

## Appendix C: Deferred out of Phase 2 (reiteration)

Pulled from CONTEXT.md §Deferred and BRAINSTORMING.md §12. No task in this plan touches these:

- Hybrid retrieval (Phase 3)
- Session briefing token budget, decision inclusion, recency (Phase 3)
- SessionStart hook shim for Claude Code (Phase 3)
- CLI `brain save` (Phase 4)
- Auto-capture Stop hook (Phase 4)
- Contradiction warning on write (Phase 5)
- `brain list/edit/delete/stats/reindex` CLI (Phase 5)
- Secret allowlist / per-request overrides (Phase 5)
- `uv tool install` + MCP registration docs + README quickstart (Phase 5)
- Sync-stable project ids (v2)
- MCP Prompt as an alternative to Resource (v1 reject)

---

*Phase: 02-knowledge-crud-scoping-mcp-core*
*Plan written: 2026-04-14*
*Plan input: `02-CONTEXT.md` (33 decisions) + `BRAINSTORMING.md` (13 sections)*

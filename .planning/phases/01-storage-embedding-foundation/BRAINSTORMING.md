# Phase 1 Design — Storage + Embedding Foundation

**Project:** brain-mcp
**Phase:** 01-storage-embedding-foundation
**Created:** 2026-04-14
**Status:** Design approved, ready for implementation planning

---

## 1. Goal & Scope

Phase 1 delivers the data layer and embedding service for `brain` — the personal, local-first MCP server that acts as shared knowledge across AI sessions. Every architectural decision that is expensive to retrofit lands in this phase, so the foundation is built correctly once.

### In Scope

- Local SQLite database at `~/.brain/brain.db` in WAL mode, with all PRAGMAs configured.
- Full schema: `knowledge_items` parent table, four extension tables (`rules`, `snippets`, `decisions`, `bug_lessons`), normalized `knowledge_tags`, `sqlite-vec` virtual table `knowledge_vec`, bridge table `vec_rowid_map`, FTS5 virtual table `knowledge_fts` kept in sync via triggers.
- Alembic migration `0001_initial` that applies cleanly on a fresh database and is idempotent on an existing one.
- `EmbeddingService` backed by `fastembed` with `nomic-ai/nomic-embed-text-v1.5-Q` (quantized, ~70MB) as the default model, lazy-loaded, with per-row `embedding_model_id` tagging and task-prefix handling.
- `Chunker` interface with a `WholeTextChunker` default implementation applied to all four knowledge kinds.
- `brain init` CLI command that creates the directory tree, runs migrations, downloads the model with visible progress, and runs a self-check.
- Supporting modules: `paths`, `errors`, `logging`, `config`, connection helpers.
- Test harness with a fake embedder, temp-DB fixtures, and a real-fastembed integration test behind a `slow` marker.

### Non-Goals for This Phase

- No MCP server wiring (Phase 2 — `MCP-01..06`).
- No `KnowledgeService` / domain-level CRUD surface (Phase 2 — `KNOW-01..06`).
- No scope filtering logic (Phase 2 — `SCOPE-01..04`).
- No retrieval / search logic (Phase 3 — `RET-01..06`, `SESS-01..04`).
- No AST-aware chunking — the `Chunker` interface is pre-built now; AST tree-sitter implementation is deferred to a later phase.
- No second embedding model — `EmbeddingService` dispatch interface is pre-built now; adding a code-specialized model later is a one-line change.
- No secret scanner — there are no write paths in Phase 1 to protect yet (Phase 2 — `KNOW-06`).
- No user-facing save/list/edit commands — Phase 1 only ships `brain init`.

### Requirements Satisfied

Phase 1 implements:

- **STOR-01..07** — SQLite file, schema, extension tables, vec virtual table, FTS5 index, Alembic migrations, sync-ready columns.
- **EMB-01..06** — Embedded fastembed service, lazy load, chunker, task prefixes, per-row model tagging, first-run UX.

---

## 2. Decisions Carried Into the Design

All decisions from `.planning/phases/01-storage-embedding-foundation/01-CONTEXT.md` apply, and the following additional decisions were locked during brainstorming (IDs `B-XX` to avoid collision with the `D-XX` ids from CONTEXT).

### Architecture Shape

- **B-01 — Middle Ground architecture.** Packages by concern (`db/`, `embedding/`, `cli/`). `Protocol` types are used only where multiple implementations are genuinely expected (`Chunker` and `Embedder`). Services receive dependencies via constructor injection (for testability), but no DI framework is used. Imports are direct everywhere else.

### Language & Tooling

- **B-02 — Python 3.11+ floor.** Access to `tomllib` stdlib, improved typing, and measurable performance gains justify the floor. Users on older distros install via `uv` / `pyenv`.
- **B-03 — `ruff` + `mypy --strict`.** `ruff` covers lint + format + import sort (replaces flake8/black/isort). `mypy --strict` enforces typing on `src/brain_mcp/`. Both run locally via `uv run` and in CI.

### Error Handling & Logging

- **B-04 — Custom exception hierarchy.** `BrainError` base + layered subclasses (`ConfigError`, `SchemaError`, `MigrationError`, `EmbeddingError`, `VectorStoreError`). The CLI top-level handler turns these into clean messages for the user. Internal code raises; the CLI layer is the only place that catches.
- **B-05 — stdlib `logging`.** No `structlog`, no `loguru`. A `setup_logging(stderr_only: bool)` helper configures a single root handler. CLI commands allow stdout (print) + stderr (log); the MCP server process (Phase 2) will use `stderr_only=True` to protect the JSON-RPC stream. Level is controlled via `BRAIN_LOG_LEVEL` env var, default `INFO`.

### Package & CLI

- **B-06 — Distribution name `brain-mcp`; import name `brain_mcp`.** The hyphenated distribution explicitly identifies this as an MCP server and avoids PyPI collisions with other `brain` packages. The underscored import follows Python conventions.
- **B-07 — `typer` CLI framework.** Type annotations become flags automatically, integrates naturally with Pydantic domain models, and builds on `click`. Chosen over raw `click` for ergonomics and over `argparse` for expressiveness.

### Test Strategy

- **B-08 — Pragmatic tests.** `pytest` with temp-file DB fixtures (not in-memory — `sqlite-vec` needs fresh connections) and a `FakeEmbedder` used in all database tests. One real-fastembed integration test exists per component, marked with `pytest.mark.slow` and skipped by default. Alembic `upgrade → downgrade → upgrade` cycle is explicitly tested. No coverage threshold in CI; target is "happy paths + obvious edge cases".

---

## 3. Module Layout

```
brain-mcp/                               # repository root
├── pyproject.toml                        # uv project, ruff config, mypy config, dependencies
├── alembic.ini                           # Alembic config
├── README.md                             # quickstart: `uv tool install brain-mcp && brain init`
├── src/
│   └── brain_mcp/                        # importable package
│       ├── __init__.py                   # exports package version and a few public types
│       ├── __main__.py                   # enables `python -m brain_mcp`
│       ├── errors.py                     # BrainError hierarchy
│       ├── paths.py                      # BRAIN_HOME / db / model cache / device_id resolution
│       ├── logging.py                    # setup_logging(stderr_only)
│       ├── config.py                     # Pydantic Settings skeleton — Phase 1 reads only env vars, populated in later phases
│       ├── db/
│       │   ├── __init__.py               # re-exports connect(), transaction(), domain models
│       │   ├── connection.py             # sqlite3 + pragmas + sqlite-vec loader
│       │   ├── schema.py                 # Pydantic domain models and enums
│       │   ├── serializers.py            # row ↔ Pydantic helpers
│       │   └── migrations/
│       │       ├── env.py                # Alembic env, wraps brain_mcp.db.connect()
│       │       ├── script.py.mako
│       │       └── versions/
│       │           └── 0001_initial.py   # full DDL for this phase
│       ├── embedding/
│       │   ├── __init__.py               # re-exports EmbeddingService, Chunker, WholeTextChunker
│       │   ├── service.py                # EmbeddingService with type-dispatch
│       │   ├── chunker.py                # Chunker Protocol + WholeTextChunker
│       │   └── models.py                 # EmbeddingModelSpec, DEFAULT_MODEL, FULL_MODEL, FastEmbedEmbedder
│       └── cli/
│           ├── __init__.py               # typer App, command registration, top-level exception handler
│           └── init.py                   # `brain init` command implementation
├── tests/
│   ├── conftest.py                       # tmp_db, db_conn, fake_embedding_service, whole_text_chunker fixtures
│   ├── test_db_connection.py
│   ├── test_db_schema.py
│   ├── test_serializers.py
│   ├── test_migrations.py
│   ├── test_chunker.py
│   ├── test_embedding_service.py
│   ├── test_embedding_integration.py     # @pytest.mark.slow — real fastembed
│   └── test_cli_init.py
└── .planning/                            # existing GSD planning directory
```

Rationale for `src/` layout: prevents accidental relative imports, required by modern `uv` / `pip` tooling, keeps tests out of the package.

---

## 4. Database Schema

Every table and virtual table is created by Alembic migration `0001_initial` via raw SQL (`op.execute`). The DDL below is the source of truth.

### 4.1 `knowledge_items` — parent table

```sql
CREATE TABLE knowledge_items (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('rule','snippet','decision','bug_lesson')),
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    scope_type  TEXT NOT NULL CHECK (scope_type IN ('global','project','language')),
    scope_value TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    sync_id     TEXT NOT NULL,
    device_id   TEXT NOT NULL,
    synced_at   TEXT
);

CREATE INDEX idx_knowledge_kind        ON knowledge_items(kind);
CREATE INDEX idx_knowledge_scope       ON knowledge_items(scope_type, scope_value);
CREATE INDEX idx_knowledge_updated_at  ON knowledge_items(updated_at);
```

- `id` is a UUID4 hex generated in Python.
- Timestamps are ISO 8601 UTC strings.
- `scope_value` is `NULL` when `scope_type = 'global'`.
- `sync_id`, `device_id`, `synced_at` exist now but are not used by any query in Phase 1. They make the future sync migration additive.

### 4.2 Extension tables (1:1 with `knowledge_items`)

```sql
CREATE TABLE rules (
    item_id  TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 50
);

CREATE TABLE snippets (
    item_id       TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    language      TEXT NOT NULL,
    usage_context TEXT
);

CREATE TABLE decisions (
    item_id      TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    rationale    TEXT NOT NULL,
    alternatives TEXT
);

CREATE TABLE bug_lessons (
    item_id    TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    symptom    TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    fix        TEXT NOT NULL,
    prevention TEXT
);
```

`ON DELETE CASCADE` means deleting a `knowledge_items` row automatically cleans up its extension row. Phase 2 `KnowledgeService.delete()` becomes a single DELETE.

### 4.3 Tags (normalized, per `D-10`)

```sql
CREATE TABLE knowledge_tags (
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    PRIMARY KEY (item_id, tag)
);

CREATE INDEX idx_tags_tag ON knowledge_tags(tag);
```

A composite primary key gives uniqueness per item; the `idx_tags_tag` index powers `WHERE tag IN (...)` filters for future search.

### 4.4 Vector store and bridge

```sql
CREATE VIRTUAL TABLE knowledge_vec USING vec0(
    embedding float[768]
);

CREATE TABLE vec_rowid_map (
    vec_rowid          INTEGER PRIMARY KEY,
    item_id            TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    chunk_index        INTEGER NOT NULL DEFAULT 0,
    embedding_model_id TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE INDEX idx_vec_map_item  ON vec_rowid_map(item_id);
CREATE INDEX idx_vec_map_model ON vec_rowid_map(embedding_model_id);
```

- `knowledge_vec` is an `sqlite-vec` virtual table holding 768-dimensional float vectors (matches `nomic-embed-text-v1.5` output dimension).
- `vec_rowid_map` is a plain table that bridges `knowledge_vec.rowid` back to the item. It carries `chunk_index` (always `0` in Phase 1; reserved for future AST chunking) and `embedding_model_id` (full fastembed model string).
- Phase 1 creates the schema but does **not** write to these tables. Writes happen in Phase 2 through `KnowledgeService`.

### 4.5 FTS5 index

```sql
CREATE VIRTUAL TABLE knowledge_fts USING fts5(
    title,
    content,
    content='knowledge_items',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
```

- Contentless FTS5: the index stores only tokens, the source text lives in `knowledge_items`. No duplication.
- `unicode61 remove_diacritics 2` matches "café" and "cafe" without losing non-Latin scripts.

### 4.6 FTS sync triggers

```sql
CREATE TRIGGER knowledge_items_ai AFTER INSERT ON knowledge_items BEGIN
    INSERT INTO knowledge_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER knowledge_items_ad AFTER DELETE ON knowledge_items BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content)
    VALUES('delete', old.rowid, old.title, old.content);
END;

CREATE TRIGGER knowledge_items_au AFTER UPDATE ON knowledge_items BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content)
    VALUES('delete', old.rowid, old.title, old.content);
    INSERT INTO knowledge_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;
```

- Insert/update/delete on `knowledge_items` keeps FTS in sync automatically. Application code never writes to `knowledge_fts` directly.
- `sqlite-vec` has no equivalent trigger mechanism for virtual tables, so vector writes are manual — Phase 2 `KnowledgeService` is responsible for writing to `knowledge_vec` and `vec_rowid_map`.

---

## 5. Core Python Interfaces

### 5.1 `brain_mcp/db/schema.py`

```python
from datetime import datetime, UTC
from enum import Enum
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeKind(str, Enum):
    RULE = "rule"
    SNIPPET = "snippet"
    DECISION = "decision"
    BUG_LESSON = "bug_lesson"


class ScopeType(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    LANGUAGE = "language"


class Scope(BaseModel):
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
```

### 5.2 `brain_mcp/embedding/chunker.py`

```python
from dataclasses import dataclass
from typing import Protocol
from brain_mcp.db.schema import KnowledgeKind


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int


class Chunker(Protocol):
    """Splits knowledge content into embedding-ready chunks."""
    def chunk(self, text: str, *, kind: KnowledgeKind) -> list[Chunk]: ...


class WholeTextChunker:
    """Single-chunk strategy: the entire content becomes one embedding."""
    def chunk(self, text: str, *, kind: KnowledgeKind) -> list[Chunk]:
        return [Chunk(text=text, index=0)]
```

### 5.3 `brain_mcp/embedding/service.py`

```python
from typing import Protocol
from brain_mcp.db.schema import KnowledgeKind


class Embedder(Protocol):
    """Abstract embedder — implemented by FastEmbedEmbedder and FakeEmbedder."""
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    @property
    def model_id(self) -> str: ...
    @property
    def dimension(self) -> int: ...


class EmbeddingService:
    """
    Type-dispatched embedding. In Phase 1 all kinds route to the same Embedder;
    the dispatch table exists so a future code-specialized model can be plugged
    in for KnowledgeKind.SNIPPET without touching callers.
    """

    def __init__(self, default_embedder: Embedder) -> None:
        self._default = default_embedder
        self._dispatch: dict[KnowledgeKind, Embedder] = {
            KnowledgeKind.RULE: default_embedder,
            KnowledgeKind.SNIPPET: default_embedder,
            KnowledgeKind.DECISION: default_embedder,
            KnowledgeKind.BUG_LESSON: default_embedder,
        }

    def _route(self, kind: KnowledgeKind) -> Embedder:
        return self._dispatch.get(kind, self._default)

    def embed_document(self, text: str, *, kind: KnowledgeKind) -> tuple[list[float], str]:
        embedder = self._route(kind)
        prefixed = f"search_document: {text}"
        vector = embedder.embed_documents([prefixed])[0]
        return vector, embedder.model_id

    def embed_query(self, text: str, *, kind: KnowledgeKind) -> tuple[list[float], str]:
        embedder = self._route(kind)
        prefixed = f"search_query: {text}"
        vector = embedder.embed_query(prefixed)
        return vector, embedder.model_id
```

### 5.4 `brain_mcp/embedding/models.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from fastembed import TextEmbedding


@dataclass(frozen=True)
class EmbeddingModelSpec:
    fastembed_id: str
    dimension: int
    variant: Literal["quantized", "full"]


DEFAULT_MODEL = EmbeddingModelSpec(
    fastembed_id="nomic-ai/nomic-embed-text-v1.5-Q",
    dimension=768,
    variant="quantized",
)

FULL_MODEL = EmbeddingModelSpec(
    fastembed_id="nomic-ai/nomic-embed-text-v1.5",
    dimension=768,
    variant="full",
)


class FastEmbedEmbedder:
    """Lazy-loaded fastembed wrapper implementing the Embedder protocol."""

    def __init__(self, spec: EmbeddingModelSpec, cache_dir: Path) -> None:
        self._spec = spec
        self._cache_dir = cache_dir
        self._model: TextEmbedding | None = None

    def _ensure_loaded(self) -> TextEmbedding:
        if self._model is None:
            self._model = TextEmbedding(
                model_name=self._spec.fastembed_id,
                cache_dir=str(self._cache_dir),
            )
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_loaded()
        return [list(vec) for vec in model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        model = self._ensure_loaded()
        return list(next(model.query_embed(text)))

    @property
    def model_id(self) -> str:
        return self._spec.fastembed_id

    @property
    def dimension(self) -> int:
        return self._spec.dimension
```

### 5.5 `brain_mcp/errors.py`

```python
class BrainError(Exception):
    """Base class for all brain-mcp errors."""


class ConfigError(BrainError):
    """Configuration or environment setup error."""


class SchemaError(BrainError):
    """Database schema error (missing table, invalid state, extension load failure)."""


class MigrationError(BrainError):
    """Alembic migration failure."""


class EmbeddingError(BrainError):
    """Embedding service failure (model load, inference, etc)."""


class VectorStoreError(BrainError):
    """sqlite-vec or vector storage failure."""
```

### 5.6 `brain_mcp/paths.py`

```python
from pathlib import Path
import os


def brain_home() -> Path:
    return Path(os.environ.get("BRAIN_HOME", Path.home() / ".brain")).expanduser()


def db_path() -> Path:
    override = os.environ.get("BRAIN_DB_PATH")
    return Path(override).expanduser() if override else brain_home() / "brain.db"


def model_cache_dir() -> Path:
    return brain_home() / "models"


def device_id_path() -> Path:
    return brain_home() / "device_id"
```

### 5.7 `brain_mcp/db/connection.py`

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import sqlite_vec

from brain_mcp.errors import SchemaError


def connect(db_path: Path) -> sqlite3.Connection:
    """
    Open a SQLite connection with all project-standard PRAGMAs and sqlite-vec loaded.
    Every connection in brain-mcp goes through this function.
    """
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_path,
        isolation_level=None,       # autocommit; explicit transactions via transaction()
        check_same_thread=False,    # MCP server may dispatch from worker threads
    )
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (sqlite3.OperationalError, AttributeError) as e:
        raise SchemaError(
            f"Failed to load sqlite-vec extension: {e}. "
            "Ensure sqlite3 was built with extension support."
        ) from e

    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Explicit transaction context (autocommit is default)."""
    conn.execute("BEGIN")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
```

---

## 6. `brain init` Command

### 6.1 Flow

```
brain init [--full-model] [--force]
    │
    ▼
  1. Ensure BRAIN_HOME directory tree exists
     (~/.brain/ and ~/.brain/models/ by default)
    │
    ▼
  2. Read or generate ~/.brain/device_id
     (uuid4 hex, written once per install)
    │
    ▼
  3. connect() the database
     - creates brain.db if missing
     - sets PRAGMAs (WAL, synchronous, busy_timeout, foreign_keys)
     - loads sqlite-vec extension
    │
    ▼
  4. run_upgrade_head()
     - Alembic applies 0001_initial
     - idempotent on existing databases
    │
    ▼
  5. FastEmbedEmbedder._ensure_loaded()
     - downloads model to BRAIN_HOME/models/
     - first-run: user sees the progress fastembed provides
     - subsequent runs: no-op
    │
    ▼
  6. Self-check (inside a rolled-back transaction)
     - INSERT a probe row into knowledge_items
     - Verify FTS trigger fired (knowledge_fts row exists)
     - embed_query("probe") returns a 768-d non-zero vector
     - sqlite-vec INSERT into knowledge_vec succeeds
     - INSERT into vec_rowid_map succeeds
     - ROLLBACK the transaction — DB is clean
    │
    ▼
  Success message:
     home     = /home/user/.brain
     database = /home/user/.brain/brain.db
     model    = nomic-ai/nomic-embed-text-v1.5-Q
```

### 6.2 Flags

| Flag | Purpose | Default |
|---|---|---|
| `--full-model` | Use the full-precision `nomic-embed-text-v1.5` (~274MB) instead of the quantized variant | `False` (quantized) |
| `--force` | Regenerate `device_id` and re-run migrations even if brain is already initialized | `False` |

### 6.3 Fallback when skipped

If the user runs a command that needs the database or the model and `brain init` has not been run, the CLI layer detects the missing state, logs a `WARNING`-level message (`"brain is not initialized — running init automatically..."`), and invokes `init_command(force=False)` inline before proceeding. The user sees the same output they would have seen running `brain init` explicitly.

### 6.4 Command module (`brain_mcp/cli/init.py`)

```python
import logging
from pathlib import Path
from uuid import uuid4

import typer

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import run_upgrade_head
from brain_mcp.embedding.models import DEFAULT_MODEL, FULL_MODEL, FastEmbedEmbedder
from brain_mcp.embedding.service import EmbeddingService
from brain_mcp.errors import BrainError
from brain_mcp.paths import (
    brain_home,
    db_path,
    device_id_path,
    model_cache_dir,
)

log = logging.getLogger("brain_mcp.cli.init")


def init_command(
    full_model: bool = typer.Option(
        False,
        "--full-model",
        help="Use full-precision model (~274MB) instead of quantized (~70MB).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-run init even if brain is already initialized.",
    ),
) -> None:
    """Initialize brain: create database, run migrations, download embedding model."""
    home = brain_home()
    db = db_path()
    cache = model_cache_dir()
    device_file = device_id_path()

    typer.echo(f"Initializing brain at {home}")

    home.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    if device_file.exists() and not force:
        device_id = device_file.read_text().strip()
    else:
        device_id = uuid4().hex
        device_file.write_text(device_id)
    typer.echo(f"  device_id: {device_id[:8]}...")

    typer.echo(f"  database:  {db}")
    conn = connect(db)
    try:
        run_upgrade_head()
        typer.echo("    schema applied (alembic head)")
    finally:
        conn.close()

    spec = FULL_MODEL if full_model else DEFAULT_MODEL
    typer.echo(f"  model:     {spec.fastembed_id} ({spec.variant})")
    typer.echo(f"    downloading / loading from {cache} ...")
    embedder = FastEmbedEmbedder(spec, cache_dir=cache)
    _ = embedder.embed_query("brain init warm-up probe")
    typer.echo(f"    model loaded (dimension={spec.dimension})")

    typer.echo("  self-check:")
    conn = connect(db)
    try:
        _self_check(conn, EmbeddingService(embedder), device_id)
        typer.echo("    schema, vec, fts all writable")
    finally:
        conn.close()

    typer.echo("")
    typer.echo("brain is ready.")
    typer.echo(f"  home:      {home}")
    typer.echo(f"  database:  {db}")
    typer.echo(f"  model:     {spec.fastembed_id}")


def _self_check(conn, embedding_service: EmbeddingService, device_id: str) -> None:
    """Insert a probe row through the full write path, then roll back."""
    # Implementation details: INSERT into knowledge_items + a rule row,
    # embed the content, INSERT into knowledge_vec + vec_rowid_map,
    # verify knowledge_fts has the row via trigger, then ROLLBACK.
    ...
```

The `_self_check` implementation is kept in the same module and exercises the full write path (insert → trigger fires → embed → vec insert → bridge insert), then rolls the transaction back so the DB stays clean.

---

## 7. Alembic Integration

### 7.1 `alembic.ini` (root)

```ini
[alembic]
script_location = src/brain_mcp/db/migrations
sqlalchemy.url = sqlite:///${BRAIN_DB_PATH}

[loggers]
keys = root,alembic
[handlers]
keys = console
[formatters]
keys = generic
# ... standard Alembic logging config ...
```

### 7.2 `src/brain_mcp/db/migrations/env.py`

```python
"""
Alembic environment — wraps brain_mcp.db.connect() so that migrations
run against a connection with WAL + sqlite-vec already loaded.
"""
from alembic import context

from brain_mcp.db.connection import connect
from brain_mcp.paths import db_path as resolve_db_path

config = context.config


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    db = resolve_db_path()
    conn = connect(db)
    try:
        context.configure(
            connection=conn,
            render_as_batch=True,   # SQLite ALTER limitations
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        conn.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 7.3 `src/brain_mcp/db/migrations/__init__.py`

```python
from pathlib import Path
from alembic.config import Config
from alembic import command

_ALEMBIC_CFG_PATH = Path(__file__).resolve().parents[3].parent / "alembic.ini"


def run_upgrade_head() -> None:
    """Programmatic entry point equivalent to `alembic upgrade head`."""
    cfg = Config(str(_ALEMBIC_CFG_PATH))
    command.upgrade(cfg, "head")
```

### 7.4 `0001_initial.py`

The full DDL from section 4 wrapped in an Alembic `upgrade()` / `downgrade()` pair using `op.execute(...)`. `upgrade()` creates the tables, indexes, virtual tables, and triggers in dependency order. `downgrade()` drops them in reverse order (triggers → virtual tables → concrete tables) to respect foreign keys.

---

## 8. Test Plan

### 8.1 Fixtures (`tests/conftest.py`)

```python
from pathlib import Path
from typing import Iterator
import sqlite3

import pytest

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import run_upgrade_head
from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.chunker import WholeTextChunker
from brain_mcp.embedding.service import EmbeddingService


class FakeEmbedder:
    """Deterministic in-memory embedder. Fast enough to use everywhere."""
    dimension = 768
    model_id = "fake-embedder-v1"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._fake_vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._fake_vec(text)

    def _fake_vec(self, text: str) -> list[float]:
        h = hash(text)
        return [((h >> i) & 0xFF) / 255.0 for i in range(self.dimension)]


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    monkeypatch.setenv("BRAIN_DB_PATH", str(db_file))
    run_upgrade_head()
    yield db_file


@pytest.fixture
def db_conn(tmp_db: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_db)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def fake_embedding_service() -> EmbeddingService:
    return EmbeddingService(default_embedder=FakeEmbedder())


@pytest.fixture
def whole_text_chunker() -> WholeTextChunker:
    return WholeTextChunker()
```

### 8.2 Test modules

| File | Scope | Real fastembed? |
|---|---|---|
| `test_db_connection.py` | `connect()` sets every required PRAGMA, loads `sqlite-vec`, raises `SchemaError` when extension unavailable, `transaction()` commits and rolls back correctly. | No |
| `test_db_schema.py` | All tables and indexes exist after migration. FKs cascade on delete. CHECK constraints reject invalid `kind` / `scope_type`. `knowledge_vec` accepts a 768-d insert. FTS5 triggers fire on insert / update / delete. | No |
| `test_serializers.py` | Round-trip: Pydantic `Rule` / `Snippet` / `Decision` / `BugLesson` → row (with tags table) → back. Timestamps preserved to ISO 8601 UTC. | No |
| `test_migrations.py` | `upgrade head` on fresh DB is clean, `downgrade base` drops everything, `upgrade head` again is clean. Idempotent on already-applied. | No |
| `test_chunker.py` | `WholeTextChunker.chunk(text, kind=...)` returns exactly one chunk with `index=0` and full text preserved, for every `KnowledgeKind`. | No |
| `test_embedding_service.py` | `EmbeddingService` dispatch routes every kind to the default embedder in Phase 1. Task prefixes `search_document: ` / `search_query: ` are applied correctly. Returns `(vector, model_id)` tuple with the right `model_id`. | No |
| `test_embedding_integration.py` | `@pytest.mark.slow` — downloads the real `nomic-embed-text-v1.5-Q`, computes a document and a query embedding, asserts dimension 768 and non-zero vector. Skipped by default. | **Yes** |
| `test_cli_init.py` | `typer.testing.CliRunner` runs `brain init` against a temp `BRAIN_HOME`. Asserts directory tree, `device_id` file, migrations applied, self-check passes. Uses `FakeEmbedder` via a monkey-patched factory. | No |

### 8.3 Conventions

- `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) registers the `slow` marker and sets `addopts = -m "not slow"` so default runs are fast.
- Running `pytest -m slow` or `pytest -m ""` executes the integration test that downloads the real model.
- `mypy --strict` runs on `src/brain_mcp/` in CI. Test modules are type-checked at `--warn-unused-ignores` level.
- No coverage threshold enforced in CI; the target is "happy paths + obvious edge cases" per the pragmatic test decision.

---

## 9. pyproject.toml Outline

```toml
[project]
name = "brain-mcp"
version = "0.1.0"
description = "Local-first MCP server with RAG for cross-project code knowledge"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.27.0",
    "fastembed>=0.8.0",
    "sqlite-vec>=0.1.9",
    "alembic>=1.13",
    "typer>=0.12",
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
]

[project.scripts]
brain = "brain_mcp.cli:app"
brain-mcp = "brain_mcp.cli:app"
# `brain-server` alias reserved for Phase 2 MCP server entrypoint

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"
extend-select = ["I", "N", "UP", "B", "A", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src/brain_mcp"]

[tool.pytest.ini_options]
addopts = "-m 'not slow' --strict-markers"
markers = [
    "slow: tests that require the real fastembed model (~70MB download)",
]
```

Phase 2 adds the `mcp` server-side dependencies and flips the `brain-server` entry point to the MCP stdio server. Phase 1 ships `brain` and `brain-mcp` as CLI entry points pointing at the same `typer` app.

---

## 10. Open Items for Research or Plan Phase

These are small uncertainties that should be verified by the researcher or picked up during implementation planning. None is a blocker.

- **`sqlite-vec` float serialization helper** — confirm the exact call: `sqlite_vec.serialize_float32(vector)` vs manually `struct.pack('f' * 768, *vector)`. Check against the current `sqlite-vec` Python example.
- **`fastembed` progress indicator** — verify whether `TextEmbedding(...)` emits a progress bar to stderr on first download, or if the CLI needs to manage progress display manually.
- **Alembic connection passing** — confirm that Alembic 1.13+ accepts passing a raw `sqlite3.Connection` via `context.configure(connection=...)` without wrapping in SQLAlchemy's `Engine`. Fall back to `create_engine("sqlite://", creator=lambda: conn)` if needed.
- **`nomic-embed-text-v1.5-Q` exact model string** — verify presence in `TextEmbedding.list_supported_models()` at the `fastembed` version in `pyproject.toml`.
- **`unicode61 remove_diacritics 2` vs `remove_diacritics 1`** — default `2` handles more code points than `1`, but check SQLite version compatibility.

---

## 11. Success Criteria (from ROADMAP.md, restated)

This phase is complete when:

1. Running `brain init` on a clean machine creates `~/.brain/brain.db` in WAL mode with every table, index, virtual table, and trigger in place. No manual setup is required.
2. Schema uses UUID text PKs, ISO 8601 UTC timestamps, and `sync_id` / `device_id` / `embedding_model_id` on every vector row. A future sync migration requires no breaking changes.
3. Saving a snippet causes the `EmbeddingService` to compute and store a vector with the correct task prefix and associated `model_id` — observable via a `SELECT` on `vec_rowid_map`.
4. On first run, the user sees a clear message about the ~70MB model download before it starts. No silent hang.
5. `alembic upgrade head` applies migration `0001_initial` cleanly on a fresh database and is idempotent on an existing one.

---

*Phase 1 design — brainstorming complete 2026-04-14*

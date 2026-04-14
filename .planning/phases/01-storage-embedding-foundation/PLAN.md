# Phase 1 — Storage + Embedding Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the data layer (SQLite + sqlite-vec + FTS5 + Alembic migrations) and the local embedding service (fastembed + chunker + type-dispatched `EmbeddingService`), wrapped by a `brain init` CLI, so that every architecturally-expensive decision in `brain-mcp` is locked in one cohesive foundation.

**Architecture:** Middle Ground (packages by concern: `db/`, `embedding/`, `cli/`; `Protocol` types only where multiple implementations are expected; constructor injection in services). Raw `sqlite3` + Pydantic domain models + Alembic via `op.execute()` raw SQL. Embedded `fastembed` with lazy-loaded `nomic-embed-text-v1.5-Q` (quantized, ~70MB). No MCP wiring, no CRUD surface, no retrieval — those belong to later phases.

**Tech Stack:** Python 3.11+, `uv`, `sqlite3` (stdlib), `sqlite-vec` 0.1.9, `fastembed` 0.8.0, `alembic` 1.13+, `typer` 0.12+, `pydantic` 2.x, `ruff`, `mypy --strict`, `pytest` 8+.

**Source of truth for design:** `.planning/phases/01-storage-embedding-foundation/BRAINSTORMING.md`. This plan translates that spec into TDD-sized tasks.

**Requirements covered:** `STOR-01..07`, `EMB-01..06` (13 total from `.planning/REQUIREMENTS.md`).

**Worktree note:** This plan is designed to run against the main branch of `brain-mcp` directly. Each task commits independently so rollback is granular if needed.

---

## File Structure

Files created in this plan (paths relative to repository root):

```
brain-mcp/
├── pyproject.toml                                     # Task 1
├── alembic.ini                                        # Task 6
├── .gitignore                                         # Task 1
├── README.md                                          # Task 1 (stub), expanded in Phase 5
├── src/
│   └── brain_mcp/
│       ├── __init__.py                                # Task 1
│       ├── __main__.py                                # Task 14
│       ├── errors.py                                  # Task 2
│       ├── paths.py                                   # Task 3
│       ├── logging.py                                 # Task 14
│       ├── db/
│       │   ├── __init__.py                            # Task 4
│       │   ├── schema.py                              # Task 4
│       │   ├── connection.py                          # Task 5
│       │   ├── serializers.py                         # Task 9
│       │   └── migrations/
│       │       ├── __init__.py                        # Task 6 (run_upgrade_head helper)
│       │       ├── env.py                             # Task 6
│       │       ├── script.py.mako                     # Task 6
│       │       └── versions/
│       │           └── 0001_initial.py                # Task 7
│       ├── embedding/
│       │   ├── __init__.py                            # Task 10
│       │   ├── chunker.py                             # Task 10
│       │   ├── models.py                              # Task 11
│       │   └── service.py                             # Task 12
│       └── cli/
│           ├── __init__.py                            # Task 14
│           └── init.py                                # Task 14
└── tests/
    ├── __init__.py                                    # Task 1
    ├── conftest.py                                    # Task 8 (tmp_db, db_conn, FakeEmbedder, etc.)
    ├── test_paths.py                                  # Task 3
    ├── test_schema_models.py                          # Task 4
    ├── test_db_connection.py                          # Task 5
    ├── test_migrations.py                             # Task 8
    ├── test_db_schema.py                              # Task 8
    ├── test_serializers.py                            # Task 9
    ├── test_chunker.py                                # Task 10
    ├── test_embedding_service.py                      # Task 12
    ├── test_embedding_integration.py                  # Task 13 (marked slow)
    └── test_cli_init.py                               # Task 15
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/brain_mcp/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "brain-mcp"
version = "0.1.0"
description = "Local-first MCP server with RAG for cross-project code knowledge"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.27.0",
    "fastembed>=0.8.0",
    "sqlite-vec>=0.1.9",
    "alembic>=1.13",
    "sqlalchemy>=2.0",
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

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/brain_mcp"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
extend-select = ["I", "N", "UP", "B", "A", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src/brain_mcp"]

[tool.pytest.ini_options]
addopts = "-m 'not slow' --strict-markers"
testpaths = ["tests"]
markers = [
    "slow: tests that require the real fastembed model (~70MB download)",
]
```

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
dist/
build/

# Project
*.db
*.db-wal
*.db-shm
```

- [ ] **Step 3: Create `README.md` stub**

```markdown
# brain-mcp

Local-first MCP server with RAG for cross-project code knowledge.

Quickstart will be added in Phase 5. For now, see `.planning/` for project docs.
```

- [ ] **Step 4: Create `src/brain_mcp/__init__.py`**

```python
"""brain-mcp: local-first MCP server with RAG for cross-project code knowledge."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create `tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 6: Install dev dependencies**

Run: `uv sync --all-extras`
Expected: Environment created, all deps installed, exit code 0.

- [ ] **Step 7: Verify package importable**

Run: `uv run python -c "import brain_mcp; print(brain_mcp.__version__)"`
Expected: `0.1.0`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore README.md src/brain_mcp/__init__.py tests/__init__.py
git commit -m "feat: project scaffold — pyproject.toml, src layout, dev deps"
```

---

## Task 2: Error Hierarchy

**Files:**
- Create: `src/brain_mcp/errors.py`

No dedicated test file — exception classes are trivial and tested transitively when raised.

- [ ] **Step 1: Create `src/brain_mcp/errors.py`**

```python
"""Exception hierarchy for brain-mcp.

All errors inherit from BrainError. CLI top-level handlers catch BrainError
and present friendly messages; internal code raises and lets exceptions bubble.
"""


class BrainError(Exception):
    """Base class for all brain-mcp errors."""


class ConfigError(BrainError):
    """Configuration or environment setup error."""


class SchemaError(BrainError):
    """Database schema error (missing table, invalid state, extension load failure)."""


class MigrationError(BrainError):
    """Alembic migration failure."""


class EmbeddingError(BrainError):
    """Embedding service failure (model load, inference, etc.)."""


class VectorStoreError(BrainError):
    """sqlite-vec or vector storage failure."""
```

- [ ] **Step 2: Type-check**

Run: `uv run mypy src/brain_mcp/errors.py`
Expected: `Success: no issues found in 1 source file`

- [ ] **Step 3: Lint**

Run: `uv run ruff check src/brain_mcp/errors.py`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add src/brain_mcp/errors.py
git commit -m "feat(errors): add BrainError exception hierarchy"
```

---

## Task 3: Path Resolution

**Files:**
- Create: `src/brain_mcp/paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write failing test `tests/test_paths.py`**

```python
"""Tests for brain_mcp.paths — environment-driven path resolution."""

from pathlib import Path

import pytest

from brain_mcp import paths


def test_brain_home_defaults_to_dot_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_HOME", raising=False)
    home = paths.brain_home()
    assert home == Path.home() / ".brain"


def test_brain_home_honors_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom_brain"
    monkeypatch.setenv("BRAIN_HOME", str(custom))
    assert paths.brain_home() == custom


def test_db_path_defaults_under_brain_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    monkeypatch.delenv("BRAIN_DB_PATH", raising=False)
    assert paths.db_path() == tmp_path / "brain.db"


def test_db_path_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    override = tmp_path / "elsewhere.db"
    monkeypatch.setenv("BRAIN_DB_PATH", str(override))
    assert paths.db_path() == override


def test_model_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    assert paths.model_cache_dir() == tmp_path / "models"


def test_device_id_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    assert paths.device_id_path() == tmp_path / "device_id"
```

- [ ] **Step 2: Run test — expect failure**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brain_mcp.paths'`

- [ ] **Step 3: Implement `src/brain_mcp/paths.py`**

```python
"""Filesystem path resolution for brain-mcp.

All paths derive from BRAIN_HOME (default: ~/.brain). BRAIN_DB_PATH overrides
just the database location without affecting the rest of the tree.
"""

import os
from pathlib import Path


def brain_home() -> Path:
    """Return the brain home directory. Honors BRAIN_HOME, defaults to ~/.brain."""
    return Path(os.environ.get("BRAIN_HOME", Path.home() / ".brain")).expanduser()


def db_path() -> Path:
    """Return the SQLite database path. BRAIN_DB_PATH overrides, else derived from brain_home()."""
    override = os.environ.get("BRAIN_DB_PATH")
    return Path(override).expanduser() if override else brain_home() / "brain.db"


def model_cache_dir() -> Path:
    """Return the fastembed model cache directory."""
    return brain_home() / "models"


def device_id_path() -> Path:
    """Return the path to the persistent device_id file."""
    return brain_home() / "device_id"
```

- [ ] **Step 4: Run test — expect pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: 6 passed

- [ ] **Step 5: Type-check & lint**

Run: `uv run mypy src/brain_mcp/paths.py && uv run ruff check src/brain_mcp/paths.py`
Expected: both clean

- [ ] **Step 6: Commit**

```bash
git add src/brain_mcp/paths.py tests/test_paths.py
git commit -m "feat(paths): add BRAIN_HOME / db_path / cache / device_id resolution"
```

---

## Task 4: Pydantic Domain Schema

**Files:**
- Create: `src/brain_mcp/db/__init__.py`
- Create: `src/brain_mcp/db/schema.py`
- Create: `tests/test_schema_models.py`

- [ ] **Step 1: Write failing test `tests/test_schema_models.py`**

```python
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
    with pytest.raises(Exception):
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
    with pytest.raises(Exception):
        Rule(
            title="x",
            content="x",
            scope=Scope(type=ScopeType.GLOBAL),
            device_id="d",
            priority=101,
        )


def test_snippet_requires_language() -> None:
    with pytest.raises(Exception):
        Snippet(  # type: ignore[call-arg]
            title="x",
            content="x",
            scope=Scope(type=ScopeType.GLOBAL),
            device_id="d",
        )


def test_decision_requires_rationale() -> None:
    with pytest.raises(Exception):
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
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_schema_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brain_mcp.db'`

- [ ] **Step 3: Create `src/brain_mcp/db/__init__.py`**

```python
"""Database layer — connection, schema, migrations, and serializers."""
```

- [ ] **Step 4: Implement `src/brain_mcp/db/schema.py`**

```python
"""Pydantic domain models for brain-mcp knowledge items.

Every knowledge item inherits KnowledgeItemBase (shared fields).
The four concrete types (Rule, Snippet, Decision, BugLesson) add type-specific
fields and are discriminated by the `kind` field.
"""

from datetime import UTC, datetime
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
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_schema_models.py -v`
Expected: 8 passed

- [ ] **Step 6: Type-check & lint**

Run: `uv run mypy src/brain_mcp/db/schema.py && uv run ruff check src/brain_mcp/db/schema.py`
Expected: both clean

- [ ] **Step 7: Commit**

```bash
git add src/brain_mcp/db/__init__.py src/brain_mcp/db/schema.py tests/test_schema_models.py
git commit -m "feat(db): pydantic schema for Rule/Snippet/Decision/BugLesson"
```

---

## Task 5: DB Connection Helper

**Files:**
- Create: `src/brain_mcp/db/connection.py`
- Create: `tests/test_db_connection.py`

- [ ] **Step 1: Write failing test `tests/test_db_connection.py`**

```python
"""Tests for brain_mcp.db.connection — pragmas and sqlite-vec loading."""

from pathlib import Path

import pytest

from brain_mcp.db.connection import connect, transaction


def _pragma(conn, name: str) -> str:
    row = conn.execute(f"PRAGMA {name}").fetchone()
    return row[0] if row else ""


def test_connect_sets_wal_mode(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        assert _pragma(conn, "journal_mode").lower() == "wal"
    finally:
        conn.close()


def test_connect_sets_busy_timeout(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        assert int(_pragma(conn, "busy_timeout")) == 5000
    finally:
        conn.close()


def test_connect_enables_foreign_keys(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        assert int(_pragma(conn, "foreign_keys")) == 1
    finally:
        conn.close()


def test_connect_loads_sqlite_vec(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        row = conn.execute("SELECT vec_version()").fetchone()
        assert row is not None
        assert isinstance(row[0], str)
    finally:
        conn.close()


def test_connect_creates_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "brain.db"
    conn = connect(nested)
    try:
        assert nested.parent.is_dir()
    finally:
        conn.close()


def test_transaction_commits_on_success(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        with transaction(conn):
            conn.execute("INSERT INTO t (x) VALUES (1)")
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    finally:
        conn.close()


def test_transaction_rolls_back_on_exception(tmp_path: Path) -> None:
    conn = connect(tmp_path / "brain.db")
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        with pytest.raises(RuntimeError):
            with transaction(conn):
                conn.execute("INSERT INTO t (x) VALUES (1)")
                raise RuntimeError("boom")
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
    finally:
        conn.close()
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_db_connection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brain_mcp.db.connection'`

- [ ] **Step 3: Implement `src/brain_mcp/db/connection.py`**

```python
"""SQLite connection factory with project-standard PRAGMAs and sqlite-vec loaded.

Every database connection in brain-mcp goes through connect(). Tests and
production code share the same pragmas and the same extension setup.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlite_vec

from brain_mcp.errors import SchemaError


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL, pragmas, and sqlite-vec extension loaded."""
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_path,
        isolation_level=None,  # autocommit; explicit transactions via transaction()
        check_same_thread=False,  # MCP server may dispatch from worker threads
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
    """Explicit transaction context over an autocommit connection."""
    conn.execute("BEGIN")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/test_db_connection.py -v`
Expected: 7 passed

- [ ] **Step 5: Type-check & lint**

Run: `uv run mypy src/brain_mcp/db/connection.py && uv run ruff check src/brain_mcp/db/connection.py`
Expected: both clean

- [ ] **Step 6: Commit**

```bash
git add src/brain_mcp/db/connection.py tests/test_db_connection.py
git commit -m "feat(db): connect() with WAL pragmas and sqlite-vec loaded"
```

---

## Task 6: Alembic Environment Wiring

**Files:**
- Create: `alembic.ini`
- Create: `src/brain_mcp/db/migrations/__init__.py`
- Create: `src/brain_mcp/db/migrations/env.py`
- Create: `src/brain_mcp/db/migrations/script.py.mako`
- Create: `src/brain_mcp/db/migrations/versions/__init__.py`

No tests yet — tested end-to-end in Task 8.

- [ ] **Step 1: Create `alembic.ini`**

```ini
[alembic]
script_location = src/brain_mcp/db/migrations
sqlalchemy.url = sqlite:///dummy.db
prepend_sys_path = .

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create `src/brain_mcp/db/migrations/__init__.py`**

```python
"""Alembic migrations for brain-mcp.

Exposes run_upgrade_head() as the programmatic entry point used by `brain init`
and by the pytest fixtures.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_CFG_PATH = _PACKAGE_ROOT.parent.parent / "alembic.ini"


def run_upgrade_head() -> None:
    """Equivalent to `alembic upgrade head`. Uses brain_mcp.db.connection under the hood."""
    cfg = Config(str(_ALEMBIC_CFG_PATH))
    command.upgrade(cfg, "head")


def run_downgrade_base() -> None:
    """Equivalent to `alembic downgrade base`."""
    cfg = Config(str(_ALEMBIC_CFG_PATH))
    command.downgrade(cfg, "base")
```

- [ ] **Step 3: Create `src/brain_mcp/db/migrations/env.py`**

```python
"""Alembic environment wired to brain_mcp.db.connect().

Instead of letting Alembic open a raw SQLAlchemy engine, we open a sqlite3
connection via our factory (so pragmas and sqlite-vec are loaded) and wrap
it in a SQLAlchemy engine via the `creator` pattern.
"""

from __future__ import annotations

import sqlite3
from typing import cast

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from brain_mcp.db.connection import connect
from brain_mcp.paths import db_path as resolve_db_path

config = context.config


def _make_engine() -> Engine:
    db = resolve_db_path()
    conn_holder: dict[str, sqlite3.Connection] = {}

    def creator() -> sqlite3.Connection:
        # Called by SQLAlchemy's connection pool. Return a fresh configured conn.
        # We cache one for the migration run so that sqlite-vec state persists.
        if "conn" not in conn_holder:
            conn_holder["conn"] = connect(db)
        return conn_holder["conn"]

    return cast(Engine, create_engine("sqlite://", creator=creator))


def run_migrations_offline() -> None:
    """Offline mode — rarely used but supported by Alembic."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode — real database connection via brain_mcp.db.connect()."""
    engine = _make_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            render_as_batch=True,  # SQLite ALTER limitations
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create `src/brain_mcp/db/migrations/script.py.mako`**

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Create `src/brain_mcp/db/migrations/versions/__init__.py`** (empty)

```python
```

- [ ] **Step 6: Verify alembic CLI works**

Run: `BRAIN_DB_PATH=/tmp/brain-alembic-check.db uv run alembic current`
Expected: no error, no revision (empty state). (It's OK if it prints nothing; error-free exit is the signal.)
Cleanup: `rm -f /tmp/brain-alembic-check.db*`

- [ ] **Step 7: Commit**

```bash
git add alembic.ini src/brain_mcp/db/migrations/
git commit -m "feat(db): alembic environment wired to brain_mcp.db.connect()"
```

---

## Task 7: Migration 0001 — Initial Schema

**Files:**
- Create: `src/brain_mcp/db/migrations/versions/0001_initial.py`

No dedicated test here — tested by `test_migrations.py` and `test_db_schema.py` in Task 8.

- [ ] **Step 1: Create `src/brain_mcp/db/migrations/versions/0001_initial.py`**

```python
"""initial schema: knowledge_items, extension tables, knowledge_vec, FTS5.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-14
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- parent table ---
    op.execute(
        """
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
        )
        """
    )
    op.execute("CREATE INDEX idx_knowledge_kind ON knowledge_items(kind)")
    op.execute("CREATE INDEX idx_knowledge_scope ON knowledge_items(scope_type, scope_value)")
    op.execute("CREATE INDEX idx_knowledge_updated_at ON knowledge_items(updated_at)")

    # --- extension tables ---
    op.execute(
        """
        CREATE TABLE rules (
            item_id  TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            priority INTEGER NOT NULL DEFAULT 50
        )
        """
    )
    op.execute(
        """
        CREATE TABLE snippets (
            item_id       TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            language      TEXT NOT NULL,
            usage_context TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE decisions (
            item_id      TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            rationale    TEXT NOT NULL,
            alternatives TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE bug_lessons (
            item_id    TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            symptom    TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            fix        TEXT NOT NULL,
            prevention TEXT
        )
        """
    )

    # --- tags ---
    op.execute(
        """
        CREATE TABLE knowledge_tags (
            item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            tag     TEXT NOT NULL,
            PRIMARY KEY (item_id, tag)
        )
        """
    )
    op.execute("CREATE INDEX idx_tags_tag ON knowledge_tags(tag)")

    # --- sqlite-vec virtual table ---
    op.execute(
        """
        CREATE VIRTUAL TABLE knowledge_vec USING vec0(
            embedding float[768]
        )
        """
    )

    # --- vec bridge ---
    op.execute(
        """
        CREATE TABLE vec_rowid_map (
            vec_rowid          INTEGER PRIMARY KEY,
            item_id            TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            chunk_index        INTEGER NOT NULL DEFAULT 0,
            embedding_model_id TEXT NOT NULL,
            created_at         TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX idx_vec_map_item ON vec_rowid_map(item_id)")
    op.execute("CREATE INDEX idx_vec_map_model ON vec_rowid_map(embedding_model_id)")

    # --- FTS5 contentless ---
    op.execute(
        """
        CREATE VIRTUAL TABLE knowledge_fts USING fts5(
            title,
            content,
            content='knowledge_items',
            content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )

    # --- FTS sync triggers ---
    op.execute(
        """
        CREATE TRIGGER knowledge_items_ai AFTER INSERT ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER knowledge_items_ad AFTER DELETE ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content)
            VALUES('delete', old.rowid, old.title, old.content);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER knowledge_items_au AFTER UPDATE ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content)
            VALUES('delete', old.rowid, old.title, old.content);
            INSERT INTO knowledge_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END
        """
    )


def downgrade() -> None:
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS knowledge_items_au")
    op.execute("DROP TRIGGER IF EXISTS knowledge_items_ad")
    op.execute("DROP TRIGGER IF EXISTS knowledge_items_ai")
    # Drop virtual tables
    op.execute("DROP TABLE IF EXISTS knowledge_fts")
    op.execute("DROP TABLE IF EXISTS vec_rowid_map")
    op.execute("DROP TABLE IF EXISTS knowledge_vec")
    # Drop concrete tables
    op.execute("DROP TABLE IF EXISTS knowledge_tags")
    op.execute("DROP TABLE IF EXISTS bug_lessons")
    op.execute("DROP TABLE IF EXISTS decisions")
    op.execute("DROP TABLE IF EXISTS snippets")
    op.execute("DROP TABLE IF EXISTS rules")
    op.execute("DROP TABLE IF EXISTS knowledge_items")
```

- [ ] **Step 2: Smoke-test the migration manually**

```bash
export BRAIN_DB_PATH=/tmp/brain-mig-check.db
rm -f /tmp/brain-mig-check.db*
uv run alembic upgrade head
uv run sqlite3 /tmp/brain-mig-check.db ".tables"
```

Expected `.tables` output contains: `bug_lessons`, `decisions`, `knowledge_fts`, `knowledge_items`, `knowledge_tags`, `knowledge_vec`, `rules`, `snippets`, `vec_rowid_map`, and Alembic's `alembic_version`. Cleanup: `rm -f /tmp/brain-mig-check.db*` and `unset BRAIN_DB_PATH`.

- [ ] **Step 3: Commit**

```bash
git add src/brain_mcp/db/migrations/versions/0001_initial.py
git commit -m "feat(db): migration 0001 — knowledge_items + extension tables + vec + fts5"
```

---

## Task 8: Migration Cycle + Schema Tests (conftest + two test modules)

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_migrations.py`
- Create: `tests/test_db_schema.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures for brain-mcp tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import run_upgrade_head


class FakeEmbedder:
    """Deterministic in-memory embedder for tests. Implements the Embedder protocol."""

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
def tmp_brain_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BRAIN_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def tmp_db(tmp_brain_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_brain_home / "brain.db"
    monkeypatch.setenv("BRAIN_DB_PATH", str(db_file))
    run_upgrade_head()
    return db_file


@pytest.fixture
def db_conn(tmp_db: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_db)
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 2: Write `tests/test_migrations.py`**

```python
"""Tests for Alembic migration cycle."""

from pathlib import Path

import pytest

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
```

- [ ] **Step 3: Write `tests/test_db_schema.py`**

```python
"""Tests for schema shape — CHECK constraints, FKs, FTS triggers, vec insert."""

from __future__ import annotations

import struct
import uuid
from datetime import UTC, datetime

import pytest

from brain_mcp.db.connection import transaction


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _insert_rule(conn, *, title="t", content="c", scope_type="global", scope_value=None) -> str:
    item_id = uuid.uuid4().hex
    with transaction(conn):
        conn.execute(
            "INSERT INTO knowledge_items "
            "(id, kind, title, content, scope_type, scope_value, created_at, updated_at, sync_id, device_id) "
            "VALUES (?, 'rule', ?, ?, ?, ?, ?, ?, ?, 'dev1')",
            (
                item_id,
                title,
                content,
                scope_type,
                scope_value,
                _now(),
                _now(),
                uuid.uuid4().hex,
            ),
        )
        conn.execute(
            "INSERT INTO rules (item_id, priority) VALUES (?, 50)", (item_id,)
        )
    return item_id


def test_kind_check_constraint_rejects_bad_value(db_conn) -> None:
    with pytest.raises(Exception):
        with transaction(db_conn):
            db_conn.execute(
                "INSERT INTO knowledge_items "
                "(id, kind, title, content, scope_type, created_at, updated_at, sync_id, device_id) "
                "VALUES ('x', 'not_a_kind', 't', 'c', 'global', ?, ?, 'sid', 'd')",
                (_now(), _now()),
            )


def test_scope_type_check_constraint_rejects_bad_value(db_conn) -> None:
    with pytest.raises(Exception):
        with transaction(db_conn):
            db_conn.execute(
                "INSERT INTO knowledge_items "
                "(id, kind, title, content, scope_type, created_at, updated_at, sync_id, device_id) "
                "VALUES ('x', 'rule', 't', 'c', 'team', ?, ?, 'sid', 'd')",
                (_now(), _now()),
            )


def test_rules_fk_cascade_delete(db_conn) -> None:
    item_id = _insert_rule(db_conn)
    assert db_conn.execute("SELECT COUNT(*) FROM rules WHERE item_id = ?", (item_id,)).fetchone()[0] == 1
    with transaction(db_conn):
        db_conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
    assert db_conn.execute("SELECT COUNT(*) FROM rules WHERE item_id = ?", (item_id,)).fetchone()[0] == 0


def test_fts_trigger_populates_on_insert(db_conn) -> None:
    item_id = _insert_rule(db_conn, title="alpha rule", content="always ruff format")
    row = db_conn.execute(
        "SELECT title, content FROM knowledge_fts WHERE knowledge_fts MATCH 'ruff'"
    ).fetchone()
    assert row is not None
    assert "alpha rule" in row[0]


def test_fts_trigger_clears_on_delete(db_conn) -> None:
    item_id = _insert_rule(db_conn, title="to be deleted", content="match me")
    with transaction(db_conn):
        db_conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
    rows = db_conn.execute(
        "SELECT title FROM knowledge_fts WHERE knowledge_fts MATCH 'match'"
    ).fetchall()
    assert rows == []


def test_vec0_accepts_768_dim_insert(db_conn) -> None:
    vector = [0.1] * 768
    blob = struct.pack(f"{len(vector)}f", *vector)
    with transaction(db_conn):
        db_conn.execute("INSERT INTO knowledge_vec (embedding) VALUES (?)", (blob,))
    count = db_conn.execute("SELECT COUNT(*) FROM knowledge_vec").fetchone()[0]
    assert count == 1
```

- [ ] **Step 4: Run all new tests — expect pass**

Run: `uv run pytest tests/test_migrations.py tests/test_db_schema.py -v`
Expected: 3 migration tests + 6 schema tests = 9 passed.

- [ ] **Step 5: Lint & type-check**

Run: `uv run ruff check tests/ && uv run mypy src/brain_mcp`
Expected: both clean

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_migrations.py tests/test_db_schema.py
git commit -m "test(db): migration cycle + schema shape coverage"
```

---

## Task 9: Row Serializers

**Files:**
- Create: `src/brain_mcp/db/serializers.py`
- Create: `tests/test_serializers.py`

- [ ] **Step 1: Write failing test `tests/test_serializers.py`**

```python
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
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_serializers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brain_mcp.db.serializers'`

- [ ] **Step 3: Implement `src/brain_mcp/db/serializers.py`**

```python
"""Row ↔ Pydantic domain model serializers.

Every insert goes through a single entry point per kind to guarantee that
the parent row, extension row, and tag rows are written together. Reads
assemble the Pydantic model back from the joined rows.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

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

    base_kwargs = dict(
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
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/test_serializers.py -v`
Expected: 5 passed

- [ ] **Step 5: Type-check & lint**

Run: `uv run mypy src/brain_mcp/db/serializers.py && uv run ruff check src/brain_mcp/db/serializers.py`
Expected: both clean

- [ ] **Step 6: Commit**

```bash
git add src/brain_mcp/db/serializers.py tests/test_serializers.py
git commit -m "feat(db): row ↔ Pydantic serializers for all 4 knowledge kinds"
```

---

## Task 10: Chunker Interface

**Files:**
- Create: `src/brain_mcp/embedding/__init__.py`
- Create: `src/brain_mcp/embedding/chunker.py`
- Create: `tests/test_chunker.py`

- [ ] **Step 1: Write failing test `tests/test_chunker.py`**

```python
"""Tests for brain_mcp.embedding.chunker."""

import pytest

from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.chunker import Chunk, WholeTextChunker


@pytest.mark.parametrize("kind", list(KnowledgeKind))
def test_whole_text_chunker_returns_single_chunk(kind: KnowledgeKind) -> None:
    chunker = WholeTextChunker()
    chunks = chunker.chunk("hello world", kind=kind)
    assert chunks == [Chunk(text="hello world", index=0)]


def test_whole_text_chunker_preserves_large_input() -> None:
    text = "a" * 10_000
    chunker = WholeTextChunker()
    chunks = chunker.chunk(text, kind=KnowledgeKind.SNIPPET)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].index == 0
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_chunker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brain_mcp.embedding'`

- [ ] **Step 3: Create `src/brain_mcp/embedding/__init__.py`**

```python
"""Embedding layer — chunker, embedder, and type-dispatched service."""

from brain_mcp.embedding.chunker import Chunk, Chunker, WholeTextChunker

__all__ = ["Chunk", "Chunker", "WholeTextChunker"]
```

- [ ] **Step 4: Implement `src/brain_mcp/embedding/chunker.py`**

```python
"""Chunker interface and the default WholeTextChunker implementation.

The WholeTextChunker produces exactly one chunk per entry. AST-aware chunking
is a deferred work item for a later phase; the interface stays the same.
"""

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

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_chunker.py -v`
Expected: 5 passed (4 parametrized + 1 extra)

- [ ] **Step 6: Type-check & lint**

Run: `uv run mypy src/brain_mcp/embedding && uv run ruff check src/brain_mcp/embedding`
Expected: both clean

- [ ] **Step 7: Commit**

```bash
git add src/brain_mcp/embedding/__init__.py src/brain_mcp/embedding/chunker.py tests/test_chunker.py
git commit -m "feat(embedding): Chunker Protocol + WholeTextChunker default"
```

---

## Task 11: FastEmbed Wrapper

**Files:**
- Create: `src/brain_mcp/embedding/models.py`

No unit test — `FastEmbedEmbedder` is exercised by the integration test in Task 13 (real model download) and indirectly by the CLI test in Task 15 via a fake.

- [ ] **Step 1: Implement `src/brain_mcp/embedding/models.py`**

```python
"""Embedding model specs and the lazy-loaded FastEmbedEmbedder wrapper.

DEFAULT_MODEL is the quantized nomic-embed-text-v1.5 (~70MB). FULL_MODEL is
the full-precision variant (~274MB), opt-in via `brain init --full-model`.

FastEmbedEmbedder implements the Embedder protocol (see service.py) and loads
the model lazily on first embed call. The model cache directory is passed in
so tests can point at a tmp_path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastembed import TextEmbedding

from brain_mcp.errors import EmbeddingError


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
            try:
                self._model = TextEmbedding(
                    model_name=self._spec.fastembed_id,
                    cache_dir=str(self._cache_dir),
                )
            except Exception as e:
                raise EmbeddingError(
                    f"Failed to load embedding model {self._spec.fastembed_id}: {e}"
                ) from e
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

- [ ] **Step 2: Type-check & lint**

Run: `uv run mypy src/brain_mcp/embedding/models.py && uv run ruff check src/brain_mcp/embedding/models.py`
Expected: both clean

- [ ] **Step 3: Commit**

```bash
git add src/brain_mcp/embedding/models.py
git commit -m "feat(embedding): FastEmbedEmbedder lazy wrapper + model specs"
```

---

## Task 12: EmbeddingService with Type Dispatch

**Files:**
- Create: `src/brain_mcp/embedding/service.py`
- Modify: `src/brain_mcp/embedding/__init__.py` (re-export service types)
- Create: `tests/test_embedding_service.py`

- [ ] **Step 1: Write failing test `tests/test_embedding_service.py`**

```python
"""Tests for brain_mcp.embedding.service — type dispatch and task prefixes."""

from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.service import EmbeddingService


class RecordingEmbedder:
    dimension = 768
    model_id = "recording-v1"

    def __init__(self) -> None:
        self.embed_document_calls: list[list[str]] = []
        self.embed_query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_document_calls.append(list(texts))
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embed_query_calls.append(text)
        return [0.0] * self.dimension


def test_embed_document_applies_search_document_prefix() -> None:
    recorder = RecordingEmbedder()
    service = EmbeddingService(default_embedder=recorder)
    vec, model_id = service.embed_document("always ruff format", kind=KnowledgeKind.RULE)
    assert model_id == "recording-v1"
    assert len(vec) == 768
    assert recorder.embed_document_calls == [["search_document: always ruff format"]]


def test_embed_query_applies_search_query_prefix() -> None:
    recorder = RecordingEmbedder()
    service = EmbeddingService(default_embedder=recorder)
    vec, model_id = service.embed_query("ruff", kind=KnowledgeKind.RULE)
    assert model_id == "recording-v1"
    assert recorder.embed_query_calls == ["search_query: ruff"]


def test_dispatch_routes_every_kind_to_default_in_phase_1() -> None:
    recorder = RecordingEmbedder()
    service = EmbeddingService(default_embedder=recorder)
    for kind in KnowledgeKind:
        service.embed_document(f"{kind.value} body", kind=kind)
    assert len(recorder.embed_document_calls) == len(KnowledgeKind)
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_embedding_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brain_mcp.embedding.service'`

- [ ] **Step 3: Implement `src/brain_mcp/embedding/service.py`**

```python
"""EmbeddingService with type-dispatched embedder routing.

Phase 1 ships a single default embedder; every KnowledgeKind routes to it.
The dispatch table is here on day one so a future code-specialized model for
KnowledgeKind.SNIPPET is a one-line change, not a refactor of callers.
"""

from typing import Protocol

from brain_mcp.db.schema import KnowledgeKind


class Embedder(Protocol):
    """Abstract embedder — implemented by FastEmbedEmbedder and test fakes."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    @property
    def model_id(self) -> str: ...
    @property
    def dimension(self) -> int: ...


class EmbeddingService:
    """Type-dispatched embedding facade over one or more Embedder implementations."""

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

    def embed_document(
        self, text: str, *, kind: KnowledgeKind
    ) -> tuple[list[float], str]:
        embedder = self._route(kind)
        prefixed = f"search_document: {text}"
        vector = embedder.embed_documents([prefixed])[0]
        return vector, embedder.model_id

    def embed_query(
        self, text: str, *, kind: KnowledgeKind
    ) -> tuple[list[float], str]:
        embedder = self._route(kind)
        prefixed = f"search_query: {text}"
        vector = embedder.embed_query(prefixed)
        return vector, embedder.model_id
```

- [ ] **Step 4: Update `src/brain_mcp/embedding/__init__.py` to re-export**

Replace the file with:

```python
"""Embedding layer — chunker, embedder, and type-dispatched service."""

from brain_mcp.embedding.chunker import Chunk, Chunker, WholeTextChunker
from brain_mcp.embedding.models import DEFAULT_MODEL, FULL_MODEL, FastEmbedEmbedder
from brain_mcp.embedding.service import Embedder, EmbeddingService

__all__ = [
    "Chunk",
    "Chunker",
    "WholeTextChunker",
    "DEFAULT_MODEL",
    "FULL_MODEL",
    "FastEmbedEmbedder",
    "Embedder",
    "EmbeddingService",
]
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_embedding_service.py -v`
Expected: 3 passed

- [ ] **Step 6: Type-check & lint**

Run: `uv run mypy src/brain_mcp/embedding && uv run ruff check src/brain_mcp/embedding`
Expected: both clean

- [ ] **Step 7: Commit**

```bash
git add src/brain_mcp/embedding/service.py src/brain_mcp/embedding/__init__.py tests/test_embedding_service.py
git commit -m "feat(embedding): EmbeddingService with type-dispatched routing + prefixes"
```

---

## Task 13: Real fastembed Integration Test (slow)

**Files:**
- Create: `tests/test_embedding_integration.py`

- [ ] **Step 1: Create `tests/test_embedding_integration.py`**

```python
"""End-to-end integration test for the real fastembed model.

Marked `slow` — downloads the real quantized nomic-embed-text-v1.5 model
(~70MB) on first run. Skipped by default; run with `pytest -m slow`.
"""

from pathlib import Path

import pytest

from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.models import DEFAULT_MODEL, FastEmbedEmbedder
from brain_mcp.embedding.service import EmbeddingService


@pytest.mark.slow
def test_real_fastembed_roundtrip(tmp_path: Path) -> None:
    embedder = FastEmbedEmbedder(DEFAULT_MODEL, cache_dir=tmp_path / "models")
    service = EmbeddingService(default_embedder=embedder)

    doc_vec, doc_model_id = service.embed_document(
        "use ruff format before every commit",
        kind=KnowledgeKind.RULE,
    )
    query_vec, query_model_id = service.embed_query(
        "format rule",
        kind=KnowledgeKind.RULE,
    )

    assert doc_model_id == DEFAULT_MODEL.fastembed_id
    assert query_model_id == DEFAULT_MODEL.fastembed_id
    assert len(doc_vec) == 768
    assert len(query_vec) == 768
    assert any(abs(x) > 0.0 for x in doc_vec)
    assert any(abs(x) > 0.0 for x in query_vec)
```

- [ ] **Step 2: Verify default run skips slow**

Run: `uv run pytest tests/test_embedding_integration.py -v`
Expected: 1 deselected (skipped due to `-m 'not slow'`).

- [ ] **Step 3: Run slow explicitly (optional but recommended locally)**

Run: `uv run pytest tests/test_embedding_integration.py -v -m slow`
Expected: 1 passed (first run may take 15-40 seconds downloading the model).

- [ ] **Step 4: Commit**

```bash
git add tests/test_embedding_integration.py
git commit -m "test(embedding): real fastembed integration (slow-marked)"
```

---

## Task 14: CLI App, `brain init` Command, logging, __main__

**Files:**
- Create: `src/brain_mcp/logging.py`
- Create: `src/brain_mcp/cli/__init__.py`
- Create: `src/brain_mcp/cli/init.py`
- Create: `src/brain_mcp/__main__.py`

Test lives in Task 15.

- [ ] **Step 1: Create `src/brain_mcp/logging.py`**

```python
"""Logging setup for brain-mcp.

CLI commands may write to stdout + stderr. The MCP server process (Phase 2)
must use stderr_only=True so that logging never corrupts the JSON-RPC stream.
"""

import logging
import os
import sys


def setup_logging(*, stderr_only: bool = False) -> None:
    """Configure the root 'brain_mcp' logger. Idempotent."""
    logger = logging.getLogger("brain_mcp")
    if logger.handlers:
        return

    level_name = os.environ.get("BRAIN_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))

    stream = sys.stderr if stderr_only else sys.stderr  # always stderr for now
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter("%(levelname)s [%(name)s] %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False
```

- [ ] **Step 2: Create `src/brain_mcp/cli/__init__.py`**

```python
"""brain CLI — typer app and top-level exception handler."""

from __future__ import annotations

import logging
import sys

import typer

from brain_mcp.cli.init import init_command
from brain_mcp.errors import BrainError
from brain_mcp.logging import setup_logging

app = typer.Typer(help="brain-mcp: local-first personal knowledge server.")
app.command("init")(init_command)


def main() -> None:
    setup_logging()
    try:
        app()
    except BrainError as exc:
        logging.getLogger("brain_mcp").error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `src/brain_mcp/cli/init.py`**

```python
"""`brain init` command — creates DB, runs migrations, downloads model, self-checks."""

from __future__ import annotations

import logging
import struct
import uuid
from datetime import UTC, datetime

import typer

from brain_mcp.db.connection import connect, transaction
from brain_mcp.db.migrations import run_upgrade_head
from brain_mcp.embedding.models import DEFAULT_MODEL, FULL_MODEL, FastEmbedEmbedder
from brain_mcp.embedding.service import EmbeddingService
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
        device_id = uuid.uuid4().hex
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
    """Insert a probe row end-to-end, then roll back so the DB stays empty."""
    from brain_mcp.db.schema import KnowledgeKind

    probe_id = uuid.uuid4().hex
    now = datetime.now(tz=UTC).isoformat()
    text = "brain init self-check probe"

    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO knowledge_items "
            "(id, kind, title, content, scope_type, scope_value, "
            "created_at, updated_at, sync_id, device_id) "
            "VALUES (?, 'rule', 'probe', ?, 'global', NULL, ?, ?, ?, ?)",
            (probe_id, text, now, now, uuid.uuid4().hex, device_id),
        )
        conn.execute(
            "INSERT INTO rules (item_id, priority) VALUES (?, 50)", (probe_id,)
        )

        row = conn.execute(
            "SELECT rowid FROM knowledge_items WHERE id = ?", (probe_id,)
        ).fetchone()
        internal_rowid = row[0]

        fts_row = conn.execute(
            "SELECT title FROM knowledge_fts WHERE rowid = ?", (internal_rowid,)
        ).fetchone()
        if fts_row is None:
            raise RuntimeError("FTS trigger did not populate knowledge_fts")

        vector, model_id = embedding_service.embed_document(text, kind=KnowledgeKind.RULE)
        blob = struct.pack(f"{len(vector)}f", *vector)
        cursor = conn.execute(
            "INSERT INTO knowledge_vec (embedding) VALUES (?)", (blob,)
        )
        vec_rowid = cursor.lastrowid
        conn.execute(
            "INSERT INTO vec_rowid_map "
            "(vec_rowid, item_id, chunk_index, embedding_model_id, created_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (vec_rowid, probe_id, model_id, now),
        )
    finally:
        conn.execute("ROLLBACK")
```

- [ ] **Step 4: Create `src/brain_mcp/__main__.py`**

```python
"""Enable `python -m brain_mcp`."""

from brain_mcp.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Smoke-test manually**

```bash
BRAIN_HOME=/tmp/brain-smoke BRAIN_DB_PATH=/tmp/brain-smoke/brain.db \
    uv run brain init
```

Expected output (paraphrased):
```
Initializing brain at /tmp/brain-smoke
  device_id: ...
  database:  /tmp/brain-smoke/brain.db
    schema applied (alembic head)
  model:     nomic-ai/nomic-embed-text-v1.5-Q (quantized)
    downloading / loading from /tmp/brain-smoke/models ...
    model loaded (dimension=768)
  self-check:
    schema, vec, fts all writable

brain is ready.
  ...
```

Cleanup: `rm -rf /tmp/brain-smoke`

- [ ] **Step 6: Type-check & lint**

Run: `uv run mypy src/brain_mcp && uv run ruff check src/brain_mcp`
Expected: both clean

- [ ] **Step 7: Commit**

```bash
git add src/brain_mcp/logging.py src/brain_mcp/cli/ src/brain_mcp/__main__.py
git commit -m "feat(cli): brain init command with self-check probe"
```

---

## Task 15: CLI Tests & Final Verification

**Files:**
- Create: `tests/test_cli_init.py`

- [ ] **Step 1: Write `tests/test_cli_init.py`**

```python
"""Tests for `brain init` via typer's CliRunner.

Uses a fake embedder via monkey-patching so the test does not download the
real fastembed model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from brain_mcp.cli import app
from brain_mcp.embedding.models import DEFAULT_MODEL


class _FakeFastEmbedEmbedder:
    def __init__(self, spec: Any, cache_dir: Path) -> None:
        self._spec = spec
        self._cache_dir = cache_dir

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.001 * (i + 1) for i in range(768)] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.001 * (i + 1) for i in range(768)]

    @property
    def model_id(self) -> str:
        return self._spec.fastembed_id

    @property
    def dimension(self) -> int:
        return 768


def test_brain_init_creates_full_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "brain_home"
    monkeypatch.setenv("BRAIN_HOME", str(home))
    monkeypatch.setenv("BRAIN_DB_PATH", str(home / "brain.db"))
    monkeypatch.setattr("brain_mcp.cli.init.FastEmbedEmbedder", _FakeFastEmbedEmbedder)

    runner = CliRunner()
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout

    assert home.is_dir()
    assert (home / "brain.db").exists()
    assert (home / "models").is_dir()
    assert (home / "device_id").exists()
    device_id = (home / "device_id").read_text().strip()
    assert len(device_id) == 32

    assert DEFAULT_MODEL.fastembed_id in result.stdout
    assert "brain is ready." in result.stdout


def test_brain_init_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "brain_home"
    monkeypatch.setenv("BRAIN_HOME", str(home))
    monkeypatch.setenv("BRAIN_DB_PATH", str(home / "brain.db"))
    monkeypatch.setattr("brain_mcp.cli.init.FastEmbedEmbedder", _FakeFastEmbedEmbedder)

    runner = CliRunner()
    runner.invoke(app, ["init"])
    first_device_id = (home / "device_id").read_text().strip()

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    second_device_id = (home / "device_id").read_text().strip()

    assert first_device_id == second_device_id
    assert "brain is ready." in result.stdout


def test_brain_init_force_regenerates_device_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "brain_home"
    monkeypatch.setenv("BRAIN_HOME", str(home))
    monkeypatch.setenv("BRAIN_DB_PATH", str(home / "brain.db"))
    monkeypatch.setattr("brain_mcp.cli.init.FastEmbedEmbedder", _FakeFastEmbedEmbedder)

    runner = CliRunner()
    runner.invoke(app, ["init"])
    first = (home / "device_id").read_text().strip()

    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    second = (home / "device_id").read_text().strip()
    assert first != second
```

- [ ] **Step 2: Run CLI tests — expect pass**

Run: `uv run pytest tests/test_cli_init.py -v`
Expected: 3 passed

- [ ] **Step 3: Run the entire non-slow test suite**

Run: `uv run pytest -v`
Expected: all tests pass, 0 failures.

- [ ] **Step 4: Run type-check and lint on everything**

Run: `uv run mypy src/brain_mcp && uv run ruff check .`
Expected: both clean

- [ ] **Step 5: Verify Phase 1 success criteria end-to-end**

Run `brain init` against a clean `BRAIN_HOME` and verify each ROADMAP.md success criterion by hand. For each, open a sqlite3 session and check:

```bash
rm -rf /tmp/brain-final && BRAIN_HOME=/tmp/brain-final \
    BRAIN_DB_PATH=/tmp/brain-final/brain.db uv run brain init
uv run sqlite3 /tmp/brain-final/brain.db "
    SELECT name FROM sqlite_master WHERE type='table' OR type='view'
"
```

Expected: `knowledge_items`, `rules`, `snippets`, `decisions`, `bug_lessons`, `knowledge_tags`, `knowledge_vec`, `vec_rowid_map`, `knowledge_fts`, `alembic_version`. Verify `PRAGMA journal_mode` returns `wal`.

Cleanup: `rm -rf /tmp/brain-final`

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli_init.py
git commit -m "test(cli): brain init CliRunner coverage"
```

- [ ] **Step 7: Final phase commit marker**

```bash
git commit --allow-empty -m "chore: phase 1 complete — storage + embedding foundation"
```

---

## Task Summary

| # | Task | Files Touched | Tests Added |
|---|---|---|---|
| 1 | Project scaffold | `pyproject.toml`, `.gitignore`, `README.md`, package/tests `__init__.py` | — |
| 2 | Error hierarchy | `src/brain_mcp/errors.py` | — |
| 3 | Path resolution | `src/brain_mcp/paths.py`, `tests/test_paths.py` | 6 |
| 4 | Pydantic schema | `src/brain_mcp/db/{__init__,schema}.py`, `tests/test_schema_models.py` | 8 |
| 5 | Connection helper | `src/brain_mcp/db/connection.py`, `tests/test_db_connection.py` | 7 |
| 6 | Alembic wiring | `alembic.ini`, `src/brain_mcp/db/migrations/*` | — |
| 7 | Migration 0001 | `0001_initial.py` | — |
| 8 | Migration + schema tests | `tests/conftest.py`, `tests/test_migrations.py`, `tests/test_db_schema.py` | 9 |
| 9 | Serializers | `src/brain_mcp/db/serializers.py`, `tests/test_serializers.py` | 5 |
| 10 | Chunker | `src/brain_mcp/embedding/{__init__,chunker}.py`, `tests/test_chunker.py` | 5 |
| 11 | FastEmbed wrapper | `src/brain_mcp/embedding/models.py` | — |
| 12 | EmbeddingService | `src/brain_mcp/embedding/service.py`, `tests/test_embedding_service.py` | 3 |
| 13 | Real integration | `tests/test_embedding_integration.py` | 1 (slow) |
| 14 | CLI + logging + __main__ | `src/brain_mcp/{logging.py,cli/*,__main__.py}` | — |
| 15 | CLI tests + verification | `tests/test_cli_init.py` | 3 |

**Total:** 15 tasks, ~47 unit/integration tests (+1 slow).

**Requirements covered (all 13 of Phase 1):**

| REQ-ID | Covered By |
|---|---|
| STOR-01 | Task 5 (WAL, pragmas), Task 14 (directory creation in `brain init`) |
| STOR-02 | Task 7 (knowledge_items DDL with all shared columns) |
| STOR-03 | Task 7 (rules, snippets, decisions, bug_lessons tables) |
| STOR-04 | Task 7 (knowledge_vec + vec_rowid_map) |
| STOR-05 | Task 7 (knowledge_fts + triggers), Task 8 (`test_db_schema.py` FTS trigger tests) |
| STOR-06 | Tasks 6, 7, 8 (Alembic env + migration + upgrade/downgrade cycle test) |
| STOR-07 | Task 7 (sync_id/device_id/synced_at columns present and NOT NULL where required) |
| EMB-01 | Task 11 (FastEmbedEmbedder without Ollama), Task 12 (EmbeddingService) |
| EMB-02 | Task 11 (lazy `_ensure_loaded`), Task 14 (cache dir from `model_cache_dir()`) |
| EMB-03 | Task 10 (`WholeTextChunker` + Chunker Protocol — AST deferred) |
| EMB-04 | Task 12 (task prefixes applied by `EmbeddingService`) |
| EMB-05 | Task 12 (`EmbeddingService.embed_*` returns `(vector, model_id)` tuple) + Task 14 (`_self_check` writes `embedding_model_id` to `vec_rowid_map`) |
| EMB-06 | Task 14 (`brain init` message before download) + Task 11 (clear message in model load path) |

---

*Phase 1 implementation plan — 2026-04-14*

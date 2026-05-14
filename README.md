# brain-mcp

> A local-first MCP server that acts as a shared "brain" for Claude and other AIs — storing and retrieving code knowledge (personal rules, snippets, decisions, bug lessons) via RAG, so that what you learn in one project is automatically reusable in every other.

**Core value:** never manually repeat the same rules, preferences and code patterns to an AI on every new project again. Knowledge is captured once and crosses project boundaries.

It is a personal developer tool: one user, multiple AI clients, knowledge that travels between projects.

## Why

Every time you start a new project, you re-teach the AI the same things: your conventions, your preferences, the bugs you already learned from, the snippets you keep rewriting. `brain` is the persistent memory layer that makes that one-time work.

## Design constraints

- **Local-first** — SQLite + embedded vector index. One file, one backup, one sync unit.
- **No external daemon** — embeddings run in-process via [`fastembed`](https://github.com/qdrant/fastembed) (ONNX Runtime, ~50MB, no PyTorch, no Ollama).
- **Private by default** — no data leaves your machine in v1. Zero operational cost, zero trust handoff.
- **MCP-standard** — works with Claude Code, Claude Desktop, Cursor, Windsurf and the SDK with no client-specific code.
- **Simple setup** — designed for daily use: `pip`/`uv` install + one MCP registration command.
- **Versioned schema** — Alembic migrations from day one, prepared for future sync.

## Tech stack

| Component | Choice | Why |
|---|---|---|
| MCP protocol | `mcp` (official Python SDK, FastMCP) | Full MCP spec compliance, stdio transport |
| Storage | SQLite (stdlib) | Portable, zero-install, WAL concurrent reads |
| Vector search | `sqlite-vec` | Embedded vector similarity, co-located with the data |
| Embeddings | `fastembed` + `nomic-embed-text-v1.5` (768d) | In-process ONNX inference, no daemon |
| Migrations | Alembic + SQLAlchemy 2.x | Versioned schema with SQLite batch mode |
| Validation | Pydantic 2.x | Typed knowledge models, free JSON schema |
| CLI | Typer | `brain` admin/debug commands |
| Secret scanning | `detect-secrets` | Knowledge entries are scanned; secret values are never echoed |
| Tooling | `uv`, `ruff`, `mypy --strict`, `pytest` | — |

## Status

Early development. Built phase-by-phase using the [GSD workflow](.planning/).

- **Phase 1 — Storage + Embedding Foundation** ✅ — SQLite schema, Alembic migrations, embedding service, chunker, CLI `init`
- **Phase 2 — Knowledge CRUD + Scoping + MCP Core** 🚧 — knowledge models, normalization, serializers, secret scanner, project-id resolution, MCP tool surface (`brain_save`, `brain_list`, `brain_search`)

See `.planning/` for full phase docs (discuss → brainstorm → plan → execute → verify).

## Knowledge model

`brain` stores typed knowledge items, each scoped as **personal** (applies everywhere) or **project** (applies to one project):

- **Rule** — a personal rule or preference (with optional topic)
- **Snippet** — a reusable code snippet (with language)
- **Decision** — an architectural/technical decision (with context)
- **Lesson** — something learned from a bug

Items are embedded for semantic retrieval and scanned for secrets before storage.

## Development

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
# Install deps (including dev extras)
uv sync --extra dev

# Run the test suite (skips the ~70MB model download)
uv run pytest

# Include slow tests that download the real fastembed model
uv run pytest -m slow

# Lint & type-check
uv run ruff check src tests
uv run mypy
```

## Layout

```
src/brain_mcp/
├── cli/          # Typer CLI — `brain init`, admin/debug commands
├── db/           # SQLite connection, schema, migrations, normalization, serializers
├── embedding/    # fastembed service, chunker, models
├── scanner/      # detect-secrets integration
├── scope/        # project-id resolution (MCP roots → .git walk → cwd)
├── service/      # serialization for embedding, content hashing
├── errors.py     # typed BrainError hierarchy
└── paths.py      # XDG-style path resolution
tests/            # pytest suite
.planning/        # GSD phase artifacts (discuss/brainstorm/plan/progress/verify)
```

## License

Personal project — not yet licensed.

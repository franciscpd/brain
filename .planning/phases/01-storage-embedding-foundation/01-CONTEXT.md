# Phase 1: Storage + Embedding Foundation — Context

**Gathered:** 2026-04-14
**Status:** Ready for research and planning

<domain>
## Phase Boundary

Phase 1 delivers the data layer and embedding service for `brain`:

- A local SQLite database (default `~/.brain/brain.db`) in WAL mode, with all tables, indexes, the `sqlite-vec` virtual table, the `vec_rowid_map` bridge, and an FTS5 index.
- Alembic migration 0001 that applies cleanly on a fresh DB and is idempotent on an existing one.
- An `EmbeddingService` backed by `fastembed` with `nomic-ai/nomic-embed-text-v1.5-Q` (quantized) as the default model, lazy-loaded on first use, with task-prefix handling and per-row `embedding_model_id` tagging.
- A `brain init` CLI command that creates the database, runs migrations, downloads the embedding model with visible progress, and validates the installation.
- A `Chunker` interface with a `WholeTextChunker` default implementation applied to all four knowledge types.

Scope is strictly the foundation. CRUD, MCP server, scoping, retrieval, session injection, capture, and lifecycle commands belong to later phases.

**Non-goals for this phase:**
- No MCP server wiring (Phase 2)
- No `KnowledgeService` / domain-level CRUD (Phase 2)
- No AST-aware chunking — deferred to a later phase, interface is pre-built now
- No second embedding model — interface supports it, but only one model ships
- No retrieval logic (Phase 3)

</domain>

<decisions>
## Implementation Decisions

### DB Access Layer

- **D-01:** Use raw `sqlite3` (stdlib) + thin helper functions to convert rows ↔ Pydantic domain models. Do not introduce SQLAlchemy (neither Core nor ORM).
  - Rationale: `sqlite-vec` virtual tables and FTS5 are hostile to ORM mapping; raw SQL stays explicit and readable; zero extra dependencies; matches the "local tool, zero magic" philosophy of the project.
  - Alembic is still used, but its migrations use raw SQL via `op.execute()` rather than SQLAlchemy metadata. Alembic runs against a raw `sqlalchemy.engine` wrapping the sqlite3 connection — this is the minimum integration Alembic needs.
  - Pydantic is used at the domain boundary: `Rule`, `Snippet`, `Decision`, `BugLesson` models with validation. The storage layer is responsible for (de)serializing these to/from SQLite rows.

### Chunking Strategy

- **D-02:** Ship a `Chunker` interface plus a single implementation, `WholeTextChunker`, which produces exactly one chunk per entry (no splitting).
  - All four knowledge types (`rule`, `snippet`, `decision`, `bug_lesson`) use `WholeTextChunker` in Phase 1.
  - AST-aware chunking (tree-sitter + per-language parsers) is deferred to a later phase and will be added as a new `Chunker` implementation without changing callers.
  - Snippets longer than the nomic-embed 8192-token context window are an accepted edge case in v1 — users curate short snippets by nature, and the schema supports multi-chunk entries via `vec_rowid_map` when we switch chunkers later.
  - Rationale: rules/decisions/bug_lessons rarely need splitting; only snippets benefit from AST awareness, and only when long; paying tree-sitter complexity in Phase 1 would bloat scope for marginal gain at personal scale.

### Embedding Service

- **D-03:** `EmbeddingService.embed(text: str, kind: KnowledgeKind) -> list[float]` with an internal type-dispatch table. In Phase 1, every `kind` dispatches to `nomic-ai/nomic-embed-text-v1.5-Q`.
  - The dispatch table exists from day one so that a future "code-specialized model for snippets" is a one-line addition to config, not a refactor of callers.
  - Every vector inserted into the store is tagged with `embedding_model_id` — this tag is computed from the dispatch decision, not hard-coded. Future model swaps only reindex affected entries.
  - Task prefixes are applied inside `EmbeddingService`: `"search_document: "` on write, `"search_query: "` on read. Callers never see prefixes. The service exposes `embed_document(...)` and `embed_query(...)` as the public surface to make the prefix choice explicit at the call site.
  - The model is lazy-loaded: the fastembed model object is created on the first `embed_document` or `embed_query` call, not at service instantiation.

### Model Variant & First-Run UX

- **D-04:** Default embedding model is `nomic-ai/nomic-embed-text-v1.5-Q` (INT8 quantized, ~70MB). The full `nomic-ai/nomic-embed-text-v1.5` (FP32, ~274MB) is opt-in via a `brain` config key (`embedding.model_variant: "quantized" | "full"`, default `"quantized"`).
  - Rationale: at personal scale, quantized quality is indistinguishable for rule/snippet recall, and the 4× smaller download dramatically improves first-run experience.
  - The `embedding_model_id` captured in the DB uses the exact fastembed model string, so full vs quantized is distinguishable at the row level if the user switches variants later.

- **D-05:** Ship a `brain init` CLI command as the explicit first-run entry point.
  - Responsibilities of `brain init`:
    1. Create `~/.brain/` directory if missing (or `$BRAIN_HOME` if set — see D-07).
    2. Create and open `brain.db`, enable WAL mode, set `busy_timeout`.
    3. Run `alembic upgrade head` against the database.
    4. Pre-download the embedding model with a visible progress indicator (use fastembed's built-in progress hooks, or a simple percentage readout if not available).
    5. Run a self-check: insert a probe row, compute an embedding, verify `vec_rowid_map` is populated, then roll the probe back or delete it.
    6. Print a success message showing DB path, model ID, and model cache path.
  - Fallback: if the user skips `brain init` and runs any command that requires the DB or the model, detect the missing state, print a clear message (`"brain is not initialized — running init automatically..."` or similar), and trigger the same initialization flow inline. Never leave the user staring at a silent hang.
  - README quickstart is exactly `uv tool install brain-server && brain init`.

### DB Path & Config

- **D-06:** Default database path is `~/.brain/brain.db`. Override precedence (highest wins): CLI flag (`--db-path`) on any command, env var `BRAIN_DB_PATH`, config file value, default.
- **D-07:** Default brain home is `~/.brain`. Override via env var `BRAIN_HOME`. All derived paths (`brain.db`, model cache, future logs) are resolved relative to this root.
- **D-08:** Model cache path is `{BRAIN_HOME}/models/` (passed to fastembed as `FASTEMBED_CACHE_PATH`). Keeps everything `brain`-related inside one directory for easy backup and uninstall.

### Schema Shape

- **D-09:** `knowledge_items` is the parent table with shared fields; four extension tables (`rules`, `snippets`, `decisions`, `bugs`) hold type-specific fields with a 1:1 FK to `knowledge_items.id`.
- **D-10:** Tags are stored as a normalized `knowledge_tags (item_id, tag)` table with a composite PK. Rationale: enables fast `WHERE tag IN (...)` filter queries and a future tag-autocomplete feature without JSON extraction. A tag-rollup view can be materialized later if needed.
- **D-11:** PKs are UUIDs (v4), stored as TEXT. Generated in Python (`uuid.uuid4().hex`), not by SQLite. Rationale: deterministic across sync contexts, no autoincrement collisions if multiple devices sync in the future.
- **D-12:** Timestamps are ISO 8601 UTC strings (`datetime.now(UTC).isoformat()`) stored as TEXT. Not Unix epoch. Rationale: human-readable in `sqlite3` CLI for debugging; trivial round-trip to `datetime`.
- **D-13:** `device_id` is generated once on `brain init`, stored in `{BRAIN_HOME}/device_id` as a raw UUID4 hex string, and loaded on every server start. Rationale: avoids cross-platform headaches of `/etc/machine-id` vs `ioreg` vs Windows equivalents; trivially reproducible; survives `rm -rf ~/.brain` (on purpose — that's a fresh install).
- **D-14:** `embedding_model_id` column on the vector/bridge row is a TEXT field holding the full fastembed model string (e.g., `"nomic-ai/nomic-embed-text-v1.5-Q"`). Not a normalized FK. Rationale: fastembed model IDs are stable strings; a separate `embedding_models` table adds a join without benefit at this scale.

### SQLite Configuration

- **D-15:** On every connection open: `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON`, then `sqlite_vec.load(conn)`.
- **D-16:** FTS5 virtual table indexes `content` and optionally `title` from `knowledge_items`. Tokenizer: `unicode61` (default, handles accents and non-ASCII — matters because the user writes in mixed languages). A contentless FTS5 table that references `knowledge_items` rowid via triggers keeps FTS in sync on insert/update/delete.

### Out of Phase 1, but Locked for Future Phases

- CRUD surface (`KnowledgeService`) is Phase 2.
- MCP server wiring is Phase 2.
- Secret scanner at write time (KNOW-06 from REQUIREMENTS.md) is Phase 2 — Phase 1 exposes no write path, so there is nothing to scan yet.
- `brain save` / `brain list` / `brain edit` user-facing commands are Phase 4/5. Phase 1 only ships `brain init`.

### Claude's Discretion

- Exact folder structure inside the package (`brain_server/db/`, `brain_server/embedding/`, etc.) — follow idiomatic Python package layout.
- Choice between `click` and `typer` for the CLI — pick one consistent with the rest of the codebase (none exists yet, so Claude picks). Mild preference for `typer` due to Pydantic-friendly signatures.
- Internal helper naming, file splitting, and test organization.
- Exact format of the `brain init` progress output (spinner vs percentage vs bar) — whatever fastembed makes easiest to wire up cleanly.
- Exact byte layout of vector insertion into `sqlite-vec` virtual table — follow the official `sqlite-vec` Python example (`struct.pack('f' * dim, *vector)` or the `sqlite_vec.serialize_float32` helper when available).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Artifacts
- `.planning/PROJECT.md` — Core value, key decisions, constraints. Especially the Key Decisions table.
- `.planning/REQUIREMENTS.md` §STOR-01..07, §EMB-01..06 — exact acceptance criteria this phase must satisfy.
- `.planning/ROADMAP.md` §Phase 1 — goal, success criteria, plan slots.

### Research Artifacts
- `.planning/research/STACK.md` — Locked stack: `mcp` 1.27.0, Python 3.10+, `fastembed` 0.8.0, `sqlite-vec` 0.1.9, Alembic, `uv`. Version compatibility notes.
- `.planning/research/ARCHITECTURE.md` — FastMCP lifespan pattern, sqlite-vec virtual table + bridge pattern, table-per-type schema with shared base, 1:1 extension FKs, sync-readiness columns.
- `.planning/research/PITFALLS.md` — Chunking as foundational failure mode, `embedding_model_id` requirement, SQLite WAL + busy_timeout, FTS5 setup pitfalls, tool schema token overhead, secret scanning.
- `.planning/research/SUMMARY.md` — Distilled roadmap implications, research flags carried into this phase.

### External Library Documentation (fetch at research or plan time)
- fastembed PyPI & GitHub — confirm `nomic-ai/nomic-embed-text-v1.5-Q` is in `TextEmbedding.list_supported_models()` and verify the download path / cache environment variable.
- `sqlite-vec` GitHub (`asg017/sqlite-vec`) — canonical Python usage: `sqlite_vec.load(conn)`, virtual table DDL, `vec0` distance operators, `sqlite_vec.serialize_float32` helper for insertion.
- Alembic docs §batch operations — SQLite ALTER limitations and how `op.batch_alter_table` + raw `op.execute` compose.
- Nomic Embed Text v1.5 model card — task prefix requirement (`search_document: ` / `search_query: `), Matryoshka dimension support, context window (8192 tokens).
- SQLite docs §WAL, §FTS5, §PRAGMA busy_timeout.

### To Read at Plan Time
- None outside the above — Phase 1 has no upstream code to read.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — this is the first implementation phase of a greenfield project. No existing code to reuse.

### Established Patterns
- None — Phase 1 establishes the patterns that every subsequent phase will inherit.

### Integration Points
- The entire `brain_server` Python package begins in Phase 1. Later phases (Phase 2 MCP server, Phase 3 retrieval) will import from the modules this phase creates:
  - `brain_server.db` — connection factory, Pragma setup, sqlite-vec loading
  - `brain_server.db.schema` — Pydantic domain models and row (de)serialization helpers
  - `brain_server.db.migrations` — Alembic env and migration scripts
  - `brain_server.embedding` — `EmbeddingService`, `Chunker` interface + `WholeTextChunker`
  - `brain_server.paths` — resolution of `BRAIN_HOME`, DB path, model cache path, device_id storage
  - `brain_server.cli` — `brain init` command entry point

</code_context>

<specifics>
## Specific Ideas

- User's cited preference for "runs on any machine" applies with teeth here: fastembed + ONNX Runtime is the only choice that satisfies this; do not substitute even if a "faster" option appears in research. No GPU dependency, no Ollama, no external service.
- User wants friction-free first run. The explicit `brain init` pattern is chosen specifically so there is a single predictable moment of setup cost, not a surprise inside a save command.
- The quantized variant as default was a deliberate trade: 70MB download beats 274MB for the `/gsd-discuss-phase 1` user, because the moment of first install is where adoption is won or lost. The full model is still available via config for users who want max quality later.

</specifics>

<deferred>
## Deferred Ideas

### Chunking
- AST-aware chunking via tree-sitter — deferred to a later phase. Must be revisited before any snippet longer than ~1000 tokens is saved in real use. Warning signs: retrieval quality on code snippets drops; searches return "wrong half" of a function.

### Second Embedding Model
- Code-specialized embedding model (`nomic-embed-code` or similar) for the `snippet` type — deferred. The `EmbeddingService` type-dispatch interface is built now specifically to make this a one-line change later, without reindexing rules/decisions/bug lessons.

### Sync
- Cloud or peer sync implementation — deferred to v2. Schema in Phase 1 includes `sync_id`, `synced_at`, `device_id` columns on `knowledge_items` so the future sync migration is additive, not a schema rewrite.

### Model Auto-Upgrade
- Automatic `brain reindex` when the default embedding model changes — deferred. Phase 5 ships `brain reindex` as a manual command (LIFE-04). Auto-upgrade behavior can come later if needed.

### First-Run Offline Install
- Shipping the model file in the package itself (offline install) — deferred. First-run download is acceptable; offline install is a secondary concern.

</deferred>

---

*Phase: 01-storage-embedding-foundation*
*Context gathered: 2026-04-14*

# Phase 2: Knowledge CRUD + Scoping + MCP Core — Context

**Gathered:** 2026-04-14
**Status:** Ready for research / planning

<domain>
## Phase Boundary

Build the service layer and MCP server surface on top of the Phase 1 storage + embedding foundation. After this phase, all four knowledge types (rule, snippet, decision, bug_lesson) can be created, read, updated, listed, and deleted through a working stdio MCP server — the full build loop is testable end-to-end in MCP Inspector.

Retrieval ranking (hybrid/vector/FTS fusion), session injection pipeline, and CLI capture are **out of scope** — those are Phases 3 and 4. This phase only needs the minimum read/list paths required to verify CRUD end-to-end. `brain_search` here is a structured lookup stub; semantic/hybrid ranking lands in Phase 3.

Requirements covered: KNOW-01..06, SCOPE-01..04, MCP-01..06 (16 total).

</domain>

<decisions>
## Implementation Decisions

### MCP Tool Surface

- **D-01:** Unified capture tool — `brain_capture(kind, ...)` accepts `kind ∈ {rule, snippet, decision, bug_lesson}` as a discriminator. One tool schema instead of four. Keeps the total tool count well under the MCP-06 ceiling of 8.
- **D-02:** Planned total MCP tool surface for Phase 2 (≤ 6, leaving headroom for Phase 3/4):
  1. `brain_capture(kind, …)` — create/update one knowledge item
  2. `brain_get(id)` — read by id
  3. `brain_list(kind?, scope?, tags?, limit, offset)` — list/browse
  4. `brain_update(id, …)` — partial update (content, tags, priority, topic, etc.)
  5. `brain_delete(id)` — hard delete
  6. `brain_search(query, kind?, scope?)` — Phase 2 stub: structured + substring lookup; Phase 3 upgrades to hybrid RRF
- **D-03:** One MCP **Resource** exposes session briefing (see D-12). Resources do not count against the 8-tool budget but do count against testing surface.

### Secret Scanning (KNOW-06)

- **D-04:** Use `detect-secrets` (Yelp). Python-native, plugin-based (AWS, JWT, private keys, Slack, base64 high-entropy, keyword). No external daemon, no binary dependency.
- **D-05:** Scanner runs on every write path (capture, update) **in the service layer**, before the Pydantic payload reaches the DB. One scanner instance is reused per process.
- **D-06:** On detection: write is blocked, error code `SECRET_DETECTED`, details carry the plugin name(s) and a redacted location hint (no secret value echoed back). Nothing is persisted.
- **D-07:** Allowlist strategy for false positives is **deferred** — if a legitimate snippet gets blocked, the user edits the content. An allowlist field on the request is a Phase 5 curation concern, not Phase 2.

### Project Identification (SCOPE-04)

- **D-08:** Primary path — MCP roots. When a client supplies roots, the first root is the project.
- **D-09:** Fallback (CLI, legacy client, no roots) — walk up from `cwd` until a `.git` directory is found, use the **basename of that directory** as the project id. If no `.git` is found, use `basename(cwd)`.
- **D-10:** The resolved project id is a plain slug (lowercase, hyphenized). Sync-stability across machines is explicitly **not** a v1 concern — a future sync migration can upgrade the id format without breaking schema (all stored values remain valid strings).

### Scope Model & Override (SCOPE-01..03)

- **D-11:** Three scope types: `global`, `project`, `language`. Stored as `(scope_type, scope_value)` on `knowledge_items` (already in schema from Phase 1).
- **D-12:** Scope is a **hard filter**, not a ranking signal. The service builds a `WHERE` clause: `scope_type='global' OR (scope_type='project' AND scope_value=:project_id) OR (scope_type='language' AND scope_value=:language)`. A rule saved to project A is literally never returned to project B.
- **D-13:** Override (SCOPE-03) is resolved via an **explicit `topic` slug field** on rules. When listing rules for a given scope context, if a `project`-scoped rule and a `global`-scoped rule share the same `topic`, the project rule **hides** the global one in the result set. Both rows still exist in storage — override is a read-time computation, not a mutation.
- **D-14:** `topic` is optional. Rules without a `topic` never override anything and are never overridden — they stack.
- **D-15:** Override logic lives in `ScopeResolver` (new module), called by `KnowledgeService.list` and by the session briefing resource. Not duplicated at call sites.

### CRUD Semantics

- **D-16:** `update` is **partial** — only provided fields change. Immutable fields: `id`, `kind`, `created_at`. Always-updated: `updated_at` (now UTC), `sync_id` (new uuid4).
- **D-17:** Re-embedding on update is **content-hash triggered**. The `knowledge_vec` row stores (or we derive from the source row) a `content_hash` (sha256 of the embedded text). On update, if `hash(new_content) != stored_hash`, re-embed and replace the vector; otherwise skip. Metadata-only updates (tags, priority, topic, scope) **do not** re-embed.
- **D-18:** `delete` is a **hard** delete. No soft-delete / tombstone in v1. Cascades to the extension table row and the `vec_rowid_map` entry (and `knowledge_vec` via that bridge).
- **D-19:** Tag normalization — Pydantic validator on the knowledge models: lowercase, strip whitespace, replace `_` and spaces with `-`, drop empties, dedup, sort. Stored as a canonical sorted list so diffs and tag-match queries are stable.
- **D-20:** Snippet `language` field — **free text, normalized** (lowercase, trim). Not an enum. New languages work day one. `SCOPE=language` filter does an exact match against the same normalization.

### MCP Server Wiring (MCP-01..06)

- **D-21:** Use `mcp.server.fastmcp.FastMCP` from the official SDK (already pinned in pyproject). Stdio transport. `stderr_only=True` logging — no `print()` anywhere in the server process (Phase 1 `logging.py` already enforces this; Phase 2 must not regress it).
- **D-22:** FastMCP **lifespan** context manager owns:
  - `connect()` the SQLite DB (reusing `db/connection.py` factory — including sqlite-vec load, WAL pragmas, FK on)
  - Lazy-loaded embedder handle (do not trigger the 270MB download at server startup — only on first capture/search call)
  - `detect-secrets` scanner instance
  - Exposes these on a typed `BrainContext` object that tool handlers receive
- **D-23:** Project id resolution happens **per request**, from MCP roots when available, falling back per D-09. Cached per-request, not globally — different requests might come from different roots in the same session.
- **D-24:** Tool descriptions are written as **LLM decision criteria**, not human docs (MCP-06). Each description answers "When should I call this?" and "What kind of input does this need?", in a sentence or two. Example target: `brain_capture` — "Save a new piece of knowledge (rule / reusable snippet / architectural decision / bug-fix lesson) so it is retrievable in future sessions. Use when the user explicitly says 'remember this', 'save this rule', etc. `kind` picks the knowledge type; content is required." Exact wording finalized in planning.

### Error Contract

- **D-25:** Tool handlers return `isError=True` MCP responses for all business errors. The `content` array contains one `text` block with a JSON string: `{"code": "SECRET_DETECTED"|"VALIDATION_ERROR"|"NOT_FOUND"|"SCOPE_INVALID"|..., "message": "<human readable>", "details": {...}}`.
- **D-26:** Internal exceptions (`BrainError` and subclasses from Phase 1) are caught at the tool boundary and translated into the contract above. `BrainError.code` maps 1:1 to the JSON `code`. No Python tracebacks in tool output.
- **D-27:** Unexpected exceptions (not `BrainError`) bubble up as protocol errors — FastMCP turns them into an `INTERNAL_ERROR` and the stderr log captures the full traceback. The server keeps running.

### Listing

- **D-28:** `brain_list` defaults: `limit=50`, `offset=0`, `order=updated_at DESC`. Maximum cap: `limit=500` (hard enforced — requests above 500 are clamped, not errored).
- **D-29:** Filters: `kind` (optional, one of the 4), `scope_type` (optional), `scope_value` (optional, paired with `scope_type`), `tags` (optional list; all must match — AND semantics, not OR).
- **D-30:** Override resolution (D-13) is applied **after** the SQL query, inside `ScopeResolver`, before pagination metadata is computed. If override hiding reduces the set below `limit`, we do not backfill — this is explicitly a read-time view, not a page-fill guarantee.

### Session Context Injection (MCP-05)

- **D-31:** Expose a single MCP **Resource** — URI pattern `brain://session/<project_id>/context`. Returns a Markdown briefing for the current project (global rules, project rules, high-priority decisions relevant to the project). Phase 2 produces a minimal version: structured SQL lookup only, no retrieval ranking. Phase 3 adds token-budget enforcement + decision inclusion logic (SESS-03).
- **D-32:** **No MCP Prompt** in v1. A Prompt would be a second copy of the same data with a different invocation path; the cost in tests + schema surface outweighs the compatibility gain. If a client later needs Prompt (no Resource support), we add it as a thin wrapper. Client-by-client strategy is documented in PKG-03 (Phase 5).
- **D-33:** SessionStart hook shim for Claude Code is **Phase 3** (SESS-02). Phase 2 just guarantees the Resource exists and returns correct data.

### Claude's Discretion

The planner / implementer may choose without asking:

- Module layout inside `src/brain_mcp/` (new packages like `service/`, `mcp/`, `scanner/`, `scope/`). Follow the pattern already established by `db/` and `embedding/`.
- Pydantic model file organization (split per kind vs single `models.py`). Phase 1 already has `db/schema.py` with knowledge domain models — extend it or split as fits.
- Test file layout and test doubles (fake embedder already exists in Phase 1 tests — reuse).
- Internal function signatures, parameter naming, logging verbosity inside services.
- Whether to use `sqlalchemy.text()` vs raw `sqlite3` cursors for service queries (Phase 1 uses raw cursors via `connect()` factory — follow that).
- Exact error message wording (D-25 fixes the codes and shape, not the English).
- Whether `brain_search` stub in Phase 2 does anything beyond structured SQL + LIKE — as long as the tool is callable and returns the documented result shape, Phase 3 can swap in hybrid retrieval without breaking clients.

</decisions>

<specifics>
## Specific Ideas

- User wants the MCP Inspector (`mcp dev brain_mcp.server`) to be the end-to-end validation target for Phase 2 — if the Inspector can save and retrieve all 4 kinds with scope filtering working, the phase is done.
- The secret scanner must return useful-but-not-leaky feedback — the AI client should be able to explain to the user "your snippet was blocked because it contains what looks like an AWS key on line 3", without the scanner (or brain) ever echoing the key value itself.
- Override semantics (D-13) were chosen specifically to keep scope filtering **auditable**: a user should be able to run `brain_list kind=rule scope=global` and also `brain_list kind=rule scope=project` and clearly see which rules are overriding which. Read-time override, not write-time mutation, preserves this.
- Project id should feel natural: working in `~/Projects/brain/` should produce `project_id="brain"` — not a hash, not a URL, not a UUID.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before researching or planning.**

### Project-wide
- `CLAUDE.md` — Workflow rules, planning structure, commit conventions, test commands
- `.planning/PROJECT.md` — Product vision, constraints, tech stack rationale
- `.planning/REQUIREMENTS.md` §KNOW, §SCOPE, §MCP — the 16 requirements this phase must satisfy
- `.planning/ROADMAP.md` §"Phase 2" — phase goal and success criteria
- `.planning/phases/01-storage-embedding-foundation/01-CONTEXT.md` — Phase 1 decisions that Phase 2 inherits (schema shape, embedding task prefixes, error hierarchy, logging stderr rule)
- `.planning/phases/01-storage-embedding-foundation/PLAN.md` — Phase 1 tasks, useful for understanding what is already built

### Phase 1 code that Phase 2 builds on
- `src/brain_mcp/db/connection.py` — `connect()` factory (WAL, FK, sqlite-vec, `transaction()` context manager). Phase 2 reuses this, does not re-open raw connections.
- `src/brain_mcp/db/schema.py` — Pydantic domain models for knowledge items. Phase 2 extends (adds `topic` field on rules, `content_hash` for update diffing) via the domain models and a Phase 2 Alembic migration.
- `src/brain_mcp/db/migrations/versions/0001_initial.py` — existing tables (`knowledge_items`, `rules`, `snippets`, `decisions`, `bug_lessons`, `vec_rowid_map`, `knowledge_vec`, `knowledge_fts`)
- `src/brain_mcp/embedding/service.py` — `EmbeddingService` with fastembed + task prefixes. Phase 2 calls `.embed_document(text)` for writes and `.embed_query(text)` for search.
- `src/brain_mcp/errors.py` — `BrainError` hierarchy (`SchemaError`, `EmbeddingError`, etc.). Phase 2 adds `SecretDetectedError`, `NotFoundError`, `ScopeError`, `ValidationError` as subclasses.
- `src/brain_mcp/logging.py` — `configure_logging(stderr_only=True)`. MCP server MUST use this.
- `src/brain_mcp/paths.py` — `BrainPaths` (brain home, db path, model cache). Phase 2 uses for CLI/project resolution plumbing.
- `src/brain_mcp/cli/init.py` — pattern for how a CLI entry point wires paths + connection + BrainError handling. Phase 2 MCP server `__main__` follows the same shape.

### External references
- MCP Python SDK — `mcp.server.fastmcp.FastMCP`, lifespan, tool/resource registration (https://github.com/modelcontextprotocol/python-sdk)
- MCP spec — tool `isError` contract, Resource URI pattern, roots capability
- `detect-secrets` — https://github.com/Yelp/detect-secrets (plugin list, `SecretsCollection` API)
- `sqlite-vec` — already loaded by `connect()`; Phase 2 does not add new vector ops beyond what Phase 1 provides

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `connect()` factory and `transaction()` context manager in `db/connection.py` — every service query uses these; never `sqlite3.connect()` directly.
- `EmbeddingService` from Phase 1 — lazy load, cached, task-prefix correct, model-id tagging. Phase 2 just calls it.
- `BrainError` hierarchy — Phase 2 extends; do not invent a parallel error class.
- `configure_logging(stderr_only=True)` — Phase 2 MCP server `__main__` must call this before anything else.
- Fake embedder test pattern (from `tests/test_cli_init.py`) — reuse for service + MCP tool tests so we do not pay the 270MB model download in CI.

### Established Patterns
- Raw `sqlite3` cursor queries via `connect()`, not SQLAlchemy ORM. Phase 1 chose this path; Phase 2 follows.
- `from __future__ import annotations` is inconsistently applied across modules — Phase 2 should standardize on using it in all new files (noted as a code quality item in Phase 1 review; Phase 2 can fix forward rather than retrofit).
- Alembic migrations live in `db/migrations/versions/`. Phase 2 adds `0002_phase2.py` for the `topic` column on `rules` and any `content_hash` column needed for update diffing (planner decides exact columns).
- Tests live in `tests/` mirroring `src/brain_mcp/` layout. Unit + integration; full suite currently 46 tests green.

### Integration Points
- MCP server entry point: new module (planner picks name — e.g. `src/brain_mcp/mcp/server.py`), wired as a `[project.scripts]` entry point `brain-server = "brain_mcp.mcp.server:main"` in `pyproject.toml`.
- CLI `brain init` stays the authoritative way to prepare `~/.brain/brain.db` — MCP server lifespan verifies the DB exists and errors out with a clear message telling the user to run `brain init` if not. No implicit auto-init in the server.
- `KnowledgeService`, `ScopeResolver`, and `SecretScanner` are all plain Python classes receiving a `sqlite3.Connection` + dependencies via constructor (dependency injection) — this is what makes fake-embedder tests trivial and is the pattern Phase 1 already uses in `EmbeddingService`.

</code_context>

<deferred>
## Deferred Ideas

- **Hybrid retrieval / ranking fusion** — Phase 3 (RET-01..06). Phase 2 `brain_search` is a stub.
- **Session briefing token budget + formatting polish** — Phase 3 (SESS-03).
- **SessionStart hook shim for Claude Code** — Phase 3 (SESS-02).
- **CLI `brain save` command** — Phase 4 (CAPT-02). Phase 2 only delivers the MCP write path.
- **Auto-capture Stop hook** — Phase 4 (AUTO-01..04).
- **Contradiction warning on write** — Phase 5 (LIFE-01). Not the same as override (D-13): override is read-time display, contradiction is write-time warning.
- **`brain list`, `brain edit`, `brain delete` CLI commands** — Phase 5 (LIFE-02). Phase 2 exposes only the MCP surface.
- **Allowlist for false-positive secrets** — Phase 5 curation.
- **Packaging polish, `uv tool install`, README quickstart** — Phase 5 (PKG-01..04).
- **Sync-stable project id (e.g. git remote based)** — v2 (SYNC-01). Noted in D-10.
- **MCP Prompt as an alternative to Resource** — not in v1; revisit if a client requires it.

</deferred>

---

*Phase: 02-knowledge-crud-scoping-mcp-core*
*Context gathered: 2026-04-14*

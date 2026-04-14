# Architecture Research

**Domain:** Python local-first MCP server with embedded RAG knowledge base
**Researched:** 2026-04-14
**Confidence:** HIGH (MCP SDK, sqlite-vec, fastembed all have current official docs; patterns verified)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          MCP CLIENT LAYER                                 │
│   Claude Code   │   Claude Desktop   │   Cursor/Windsurf   │   SDK        │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ MCP Protocol (stdio / SSE)
┌────────────────────────────▼─────────────────────────────────────────────┐
│                          MCP SERVER LAYER  (FastMCP)                      │
│                                                                           │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐ │
│  │  Resources  │  │      Tools       │  │         Prompts              │ │
│  │             │  │                  │  │                              │ │
│  │ brain://    │  │ save_rule()      │  │ summarize_session()          │ │
│  │ context/    │  │ save_snippet()   │  │                              │ │
│  │ {project}   │  │ save_decision()  │  │                              │ │
│  │             │  │ save_bug()       │  │                              │ │
│  │             │  │ search()         │  │                              │ │
│  │             │  │ get_rules()      │  │                              │ │
│  └──────┬──────┘  └────────┬─────────┘  └──────────────────────────────┘ │
│         │                  │                                              │
│  ┌──────▼──────────────────▼─────────────────────────────────────────┐   │
│  │                     Service Layer                                  │   │
│  │  KnowledgeService  │  RetrievalService  │  EmbeddingService        │   │
│  └──────────────────────────────┬─────────────────────────────────────┘   │
│                                 │ lifespan context                        │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────────┐
│                         STORAGE LAYER                                     │
│                                                                           │
│  ┌──────────────────────────────────────┐  ┌──────────────────────────┐  │
│  │        SQLite main.db                │  │  sqlite-vec extension    │  │
│  │                                      │  │                          │  │
│  │  knowledge_items (shared base)       │  │  vec_embeddings          │  │
│  │  rules (type-specific ext)           │  │  (virtual vec0 table)    │  │
│  │  snippets (type-specific ext)        │  │                          │  │
│  │  decisions (type-specific ext)       │  │  rowid → item_id JOIN    │  │
│  │  bugs (type-specific ext)            │  │                          │  │
│  │  schema_versions                     │  └──────────────────────────┘  │
│  └──────────────────────────────────────┘                                │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────────┐
│                        CAPTURE PIPELINE                                   │
│                                                                           │
│  Claude Code Hooks (shell scripts → HTTP → brain server)                 │
│                                                                           │
│  SessionStart → load_project_context()                                   │
│  Stop         → maybe_extract_learnings(transcript_path)                 │
│  PostToolUse  → maybe_capture_edit(tool_input, tool_response)            │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| MCP Resources | Expose read-only context blobs for session-start injection | FastMCP `@mcp.resource("brain://context/{project}")` |
| MCP Tools | Capture and search operations invoked by the AI | FastMCP `@mcp.tool()` decorated functions |
| MCP Prompts | Reusable structured prompts (e.g. session briefing template) | FastMCP `@mcp.prompt()` — optional v1 |
| KnowledgeService | CRUD for all 4 knowledge types; scope resolution | Pure Python, talks to SQLite via aiosqlite |
| RetrievalService | Two-stage retrieval: structured + semantic; result fusion | Python, uses KnowledgeService + EmbeddingService |
| EmbeddingService | Compute/cache embeddings; model lifecycle; re-embed support | fastembed TextEmbedding, lazy load on first use |
| SQLite DB | Authoritative persistent store for all knowledge items | aiosqlite + sqlite-vec extension |
| Hook Scripts | Thin shell shims that POST to brain's HTTP endpoint on lifecycle events | Bash scripts registered in `.claude/settings.json` |

---

## Recommended Project Structure

```
brain/
├── src/
│   └── brain/
│       ├── __init__.py
│       ├── server.py              # FastMCP app, lifespan, tool/resource registration
│       ├── config.py              # Paths, model name, DB location, env vars
│       ├── services/
│       │   ├── __init__.py
│       │   ├── knowledge.py       # KnowledgeService: CRUD, scope resolution
│       │   ├── retrieval.py       # RetrievalService: two-stage search, fusion
│       │   └── embedding.py       # EmbeddingService: fastembed wrapper, cache
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py        # DB init, connection management, sqlite-vec load
│       │   ├── migrations/        # Alembic migration scripts
│       │   │   ├── env.py
│       │   │   └── versions/
│       │   │       └── 0001_initial.py
│       │   └── schema.sql         # Reference DDL (source of truth, not used at runtime)
│       ├── models/
│       │   ├── __init__.py
│       │   └── knowledge.py       # Pydantic models: KnowledgeItem, Rule, Snippet, etc.
│       └── hooks/
│           ├── session_start.sh   # Hook script: POST project context request to brain
│           ├── post_stop.sh       # Hook script: POST transcript for auto-extraction
│           └── post_tool_use.sh   # Hook script: POST tool events for auto-capture
├── tests/
│   ├── test_knowledge.py
│   ├── test_retrieval.py
│   └── test_embedding.py
├── alembic.ini
├── pyproject.toml
└── README.md
```

### Structure Rationale

- **services/:** Business logic fully decoupled from MCP transport — testable without an MCP client
- **storage/:** All DB concerns isolated; migrations versioned from day one
- **hooks/:** Thin shell scripts kept separate from server code; they POST to the server, not import it
- **models/:** Pydantic models shared between MCP layer and service layer for validation

---

## Architectural Patterns

### Pattern 1: Table-Per-Type with Shared Base (Storage)

**What:** A `knowledge_items` table holds all shared fields. Four extension tables (`rules`, `snippets`, `decisions`, `bugs`) hold type-specific fields. One-to-one join via `item_id`.

**When to use:** When types share a large common surface (id, timestamps, scope, tags, source) but diverge on a few specific fields. Avoids sparse NULL columns across a fat single table.

**Trade-offs:** Requires a JOIN per read — acceptable at v1 scale (hundreds to low thousands of items). Cleaner than single-table-inheritance for future migrations. Each type can evolve independently.

**Schema:**

```sql
-- Shared base (all knowledge types)
CREATE TABLE knowledge_items (
    id          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    kind        TEXT NOT NULL CHECK (kind IN ('rule','snippet','decision','bug')),
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',   -- JSON array, fast enough at v1 scale
    scope_type  TEXT NOT NULL DEFAULT 'global'
                CHECK (scope_type IN ('global','project','language')),
    scope_value TEXT,                         -- NULL for global; project path or lang name
    source      TEXT NOT NULL DEFAULT 'manual'
                CHECK (source IN ('manual','auto_hook')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    -- Sync-readiness: added now, free columns, never break schema
    sync_id     TEXT UNIQUE,                  -- NULL until sync enabled; stable cross-device ID
    synced_at   TEXT,                         -- NULL until first sync
    device_id   TEXT                          -- NULL until sync enabled
);

-- Rule-specific fields
CREATE TABLE rules (
    item_id     TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    priority    INTEGER NOT NULL DEFAULT 50,  -- 1-100, higher = inject first
    always_load INTEGER NOT NULL DEFAULT 0    -- 1 = inject at every session start
);

-- Snippet-specific fields
CREATE TABLE snippets (
    item_id     TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    language    TEXT,
    context     TEXT   -- what problem does this solve
);

-- Decision-specific fields
CREATE TABLE decisions (
    item_id     TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    alternatives TEXT,  -- JSON: what else was considered
    outcome     TEXT    -- what happened as a result (can be filled later)
);

-- Bug-specific fields
CREATE TABLE bugs (
    item_id     TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    error_signature TEXT,   -- key part of the error message / stack trace
    root_cause  TEXT,
    fix_summary TEXT
);

-- Vector embeddings (sqlite-vec virtual table)
-- rowid aligns with a shadow table that maps rowid → item_id
CREATE VIRTUAL TABLE vec_embeddings USING vec0(
    embedding float[768]   -- nomic-embed-text-v1.5 dimension
);

-- rowid bridge: sqlite-vec vec0 uses implicit rowid, we need item_id lookup
CREATE TABLE vec_rowid_map (
    rowid   INTEGER PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    model   TEXT NOT NULL DEFAULT 'nomic-ai/nomic-embed-text-v1.5'
);

-- Schema versioning for Alembic / future sync
CREATE TABLE schema_versions (
    version     TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Indexes
CREATE INDEX idx_ki_kind       ON knowledge_items(kind);
CREATE INDEX idx_ki_scope      ON knowledge_items(scope_type, scope_value);
CREATE INDEX idx_ki_tags       ON knowledge_items(tags);           -- JSON, use JSON extract in queries
CREATE INDEX idx_ki_always_load ON rules(always_load) WHERE always_load = 1;
```

### Pattern 2: Two-Stage Hybrid Retrieval

**What:** Stage 1 — structured SQL lookup for rules (by scope, tags, always_load flag). Stage 2 — vector cosine similarity search for snippets, decisions, and bugs. Results merged with a simple priority/rank weighting, no reranker needed at v1 scale.

**When to use:** Rules are curated, few, and should be retrieved exactly — tags and scope are reliable signals. Snippets/decisions/bugs are larger in number and benefit from semantic "what does this remind me of" retrieval.

**Trade-offs:** Keeps retrieval logic simple. No BM25 sparse index needed at v1 (hundreds of items). If item count grows to tens of thousands, add BM25 via FTS5 virtual table before resorting to a full reranker.

**Retrieval flow:**

```python
# Stage 1: Rules — structured lookup
rules = db.execute("""
    SELECT ki.*, r.priority, r.always_load
    FROM knowledge_items ki
    JOIN rules r ON r.item_id = ki.id
    WHERE ki.kind = 'rule'
      AND (ki.scope_type = 'global'
           OR (ki.scope_type = 'project' AND ki.scope_value = ?)
           OR (ki.scope_type = 'language' AND ki.scope_value = ?))
    ORDER BY r.priority DESC
    LIMIT 20
""", [project_path, detected_language])

# Stage 2: Semantic search — snippets, decisions, bugs
query_vec = embedding_service.embed(query_text)
candidates = db.execute("""
    SELECT vm.item_id, ve.distance
    FROM vec_embeddings ve
    JOIN vec_rowid_map vm ON vm.rowid = ve.rowid
    JOIN knowledge_items ki ON ki.id = vm.item_id
    WHERE ki.kind IN ('snippet','decision','bug')
      AND ki.scope_type IN ('global', ?)    -- project or global
    ORDER BY ve.distance                     -- cosine distance ascending
    LIMIT 10
""", [project_path])

# Fusion: rules always included; semantic results ranked by similarity
# Simple threshold: drop candidates with distance > 0.4
results = rules + [c for c in candidates if c.distance < 0.4]
```

**When to use each retrieval path:**
- Session start: Stage 1 only (rules with `always_load=1` + project-scoped rules)
- On-demand `search()` tool: Stage 1 + Stage 2, merged
- Tag/scope lookup tool: Stage 1 only
- Semantic-only search: Stage 2 only, when query is a natural language description

### Pattern 3: Scoping Model

**What:** Three scope levels, encoded as two columns `(scope_type, scope_value)` rather than a hierarchy table.

**When to use:** Simple and query-friendly. A "global" rule has `scope_type='global', scope_value=NULL`. A project rule has `scope_type='project', scope_value='/home/user/Projects/myapp'`. A language rule has `scope_type='language', scope_value='python'`.

**Why not a hierarchy/path key:** A dot-separated key like `global.project.lang` creates parsing complexity and makes partial-match queries harder. Two columns with a CHECK constraint are simpler, indexed, and extend cleanly to future scope types without schema change.

**Query pattern:**

```sql
-- "Give me everything relevant to this project session"
WHERE scope_type = 'global'
   OR (scope_type = 'project' AND scope_value = '/home/user/Projects/brain')
   OR (scope_type = 'language' AND scope_value = 'python')
```

**Future scope types** (no schema change needed — just add new CHECK values or relax constraint):
- `scope_type='team'` with `scope_value='team-id'` — post-sync
- `scope_type='framework'` with `scope_value='fastapi'`

### Pattern 4: Embedding Pipeline

**What:** Embeddings are computed synchronously at write time. No async queue in v1.

**Rationale:** At v1 scale (hundreds of items), embedding one item takes 20-100ms with fastembed on CPU. This is acceptable in a synchronous write path. The complexity of an async queue (worker process, retry logic, queue storage) is not justified until batch imports are needed.

**Re-embed strategy:** When the embedding model changes, a migration CLI command re-embeds all items. The `vec_rowid_map.model` column records which model produced each embedding, so re-embedding can be targeted and verified.

**fastembed lazy-load pattern:**

```python
class EmbeddingService:
    _model: TextEmbedding | None = None

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            # Downloads ~270MB on first call, cached in FASTEMBED_CACHE_PATH
            self._model = TextEmbedding(model_name="nomic-ai/nomic-embed-text-v1.5")
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._get_model()
        return next(model.embed([text])).tolist()
```

**Model:** `nomic-ai/nomic-embed-text-v1.5` — 768 dimensions, ~270MB ONNX, CPU-only, no Ollama dependency. Set `FASTEMBED_CACHE_PATH=~/.brain/models` to keep cache in a predictable location.

### Pattern 5: Session-Start Context Injection via MCP Resources

**What:** The AI client reads a MCP resource at session start to receive relevant context (rules, recent decisions) without the user doing anything.

**How:** Claude Code's `SessionStart` hook fires a shell script that calls a tool on the brain server. The tool returns a formatted context blob. The AI client reads this content and prepends it to its working context.

Alternatively, expose a Resource at `brain://context/{project_path}` that returns a Markdown-formatted brief. The MCP client can be configured to read this resource automatically in its system prompt or initialization.

**Preferred v1 approach:** Use a `get_session_context()` MCP tool (not a resource) called by the hook script, because:
- Hook scripts can POST to an HTTP endpoint on the brain server more easily than implementing a full resource read flow
- Claude Code hooks do not natively "read MCP resources" — they run shell commands
- The AI can also call `get_session_context()` directly if it wants to refresh context mid-session

**Hook implementation:**

```bash
# .claude/hooks/session_start.sh
#!/bin/bash
PROJECT=$(cat | jq -r '.cwd // "global"')
curl -s -X POST http://localhost:7832/mcp/call \
  -H "Content-Type: application/json" \
  -d "{\"tool\": \"get_session_context\", \"args\": {\"project\": \"$PROJECT\"}}" \
  | jq -r '.content' \
  | head -c 4000   # keep context injection bounded
```

**Alternative (cleaner):** Register brain as MCP server, configure Claude Code to always include `brain://context/{cwd}` as a resource in its context. This is the intended MCP resource pattern and requires no hook script. Verify Claude Code resource auto-injection support before relying on this path — it may require client-side configuration.

---

## Data Flow

### Flow A: New Rule Saved (Manual Capture)

```
AI calls save_rule(title, content, scope, tags, priority)
    │
    ▼
MCP Tool Handler (server.py)
    │  validates via Pydantic model
    ▼
KnowledgeService.save_rule()
    │  inserts into knowledge_items (kind='rule')
    │  inserts into rules (priority, always_load)
    ▼
EmbeddingService.embed(title + "\n" + content)
    │  fastembed computes 768-dim vector (~50ms CPU)
    ▼
DB: INSERT INTO vec_embeddings  (gets rowid N)
DB: INSERT INTO vec_rowid_map (rowid=N, item_id=..., model=...)
    │
    ▼
Returns: { id, title, scope, created_at }
```

### Flow B: New Session Start in a Project

```
Claude Code SessionStart hook fires
    │
    ▼
session_start.sh executes
    │  reads cwd from hook JSON input
    │  POSTs to brain HTTP or calls MCP tool
    ▼
get_session_context(project="/home/user/Projects/myapp")
    │
    ▼
RetrievalService.get_session_context(project_path)
    │
    ├── Stage 1a: Rules with always_load=1 (global + project)
    │     SQL: kind='rule' AND (scope global OR scope=project) AND always_load=1
    │     → sorted by priority DESC, LIMIT 30
    │
    ├── Stage 1b: Recent decisions for this project (last 10)
    │     SQL: kind='decision' AND scope_type='project' AND scope_value=project
    │     → ORDER BY created_at DESC LIMIT 10
    │
    └── Format as Markdown brief
          "## Active Rules\n- ...\n## Recent Decisions\n- ..."
    │
    ▼
Hook script outputs formatted text to stdout
Claude Code injects into session context (via additionalContext in hook output)
```

### Flow C: On-Demand Search During a Task

```
AI calls search(query="how do I handle auth errors in FastAPI", kind=["snippet","bug"])
    │
    ▼
RetrievalService.search(query, kind_filter, project)
    │
    ├── Stage 2: Semantic search
    │     EmbeddingService.embed(query) → query_vec
    │     sqlite-vec KNN query:
    │       SELECT rowid, distance FROM vec_embeddings
    │       WHERE embedding MATCH query_vec ORDER BY distance LIMIT 20
    │     JOIN vec_rowid_map → item_ids
    │     JOIN knowledge_items WHERE kind IN (kind_filter) AND scope matches project
    │     Filter: distance < 0.4 threshold
    │
    ├── Stage 1 (if kind_filter includes 'rule'):
    │     SQL tag/scope lookup for rules matching query terms
    │
    └── Merge: deduplicate by item_id, semantic results ranked by distance
          Rules always ranked above semantic results
    │
    ▼
Returns: list of KnowledgeItem (max 10), each with title, content, kind, tags
AI uses results to inform its response
```

### Flow D: Auto-Capture via Hook (PostToolUse)

```
Claude Code PostToolUse fires after Write/Edit tool succeeds
    │
    ▼
post_tool_use.sh executes
    │  reads tool_name, tool_input, tool_response, cwd from hook JSON
    │  filters: only process Write/Edit with substantial content
    │
    ▼
POST to brain: auto_capture_candidate(tool_event_json)
    │
    ▼
KnowledgeService.evaluate_capture_candidate()
    │  Heuristic: is this a config file? a solution pattern? a migration?
    │  → if ambiguous: return None (don't capture noise)
    │  → if clearly a reusable pattern: draft KnowledgeItem, mark source='auto_hook'
    │
    ▼
brain returns suggested_item or None
    │
    ▼
If suggested_item: hook injects it as additionalContext to Claude:
    "I noticed a reusable pattern. Want me to save it? Call save_snippet() to confirm."
    │
    ▼
AI decides whether to call save_snippet() explicitly (human in the loop)
```

**Note:** Full auto-save without confirmation is an anti-pattern — it produces noise. The Stop hook (reading the full transcript) is a better trigger for auto-capture than PostToolUse, because the transcript provides full context for evaluating what was learned.

---

## Component Boundaries

| Boundary | Communication | Contract |
|----------|---------------|----------|
| MCP Client ↔ MCP Server | MCP protocol over stdio (or SSE for HTTP) | MCP spec — tools, resources, prompts |
| Hook Scripts ↔ MCP Server | HTTP POST to localhost:7832 | JSON request/response (same as MCP tool calls but over HTTP) |
| MCP Server ↔ Services | Direct Python function calls | Pydantic models as DTOs |
| Services ↔ Storage | aiosqlite async queries | SQL + sqlite-vec virtual table |
| EmbeddingService ↔ fastembed | In-process function call | numpy array → list[float] |

**Key constraint:** Hook scripts must communicate with the server via HTTP (not by importing the Python module), because hooks run as separate processes. This means the brain server must expose a lightweight HTTP endpoint alongside the MCP stdio/SSE transport. FastMCP supports running both simultaneously.

---

## Build Order

Dependencies flow strictly forward. Each phase depends on all previous phases.

```
Phase 1: Storage Foundation
    SQLite schema + sqlite-vec setup + Alembic migrations
    → Nothing works without this
    Produces: DB init, migration framework, base models

Phase 2: Embedding Service
    fastembed wrapper, model download/cache, embed() function
    → Cannot store or retrieve anything without embeddings
    Produces: EmbeddingService, tested with nomic-embed-text-v1.5

Phase 3: Knowledge CRUD (KnowledgeService)
    Insert/read/update/delete for all 4 types, scope resolution
    → Depends on Phase 1 (storage) + Phase 2 (embedding at write time)
    Produces: KnowledgeService with full CRUD, end-to-end "save rule" working

Phase 4: Retrieval Service
    Two-stage retrieval, structured SQL + sqlite-vec KNN, fusion
    → Depends on Phase 1 + 2 + 3 (needs items in DB to search)
    Produces: RetrievalService, search() working end-to-end

Phase 5: MCP Server Layer
    FastMCP app, lifespan (DB init, model lazy-load), tool registration
    → Depends on Phase 3 + 4 (services must exist before tools wrap them)
    Produces: Functional MCP server, tools testable with MCP Inspector

Phase 6: Session-Start Context + Hook Scripts
    get_session_context() tool, SessionStart/Stop hook scripts, HTTP endpoint
    → Depends on Phase 4 (retrieval) + Phase 5 (server running)
    Produces: Fully working capture + retrieval loop

Phase 7: Auto-Capture Pipeline (optional v1)
    Stop hook transcript analysis, auto_capture_candidate() heuristics
    → Depends on Phase 6 (hooks working)
    Produces: Hands-free capture suggestions
```

**Critical path:** Phase 1 → Phase 2 → Phase 3 → Phase 5 gets you "save a rule, retrieve it manually" which proves core value. Phase 4 adds semantic search. Phase 6 makes it zero-friction.

---

## Schema Versioning and Sync-Readiness

### Alembic from Day One

Alembic manages all schema changes via migration scripts stored in `storage/migrations/versions/`. The `schema_versions` table is redundant with Alembic's `alembic_version` table — use only one (Alembic's). Initialize on first server start if the DB doesn't exist.

SQLite has a limitation: ALTER TABLE cannot drop columns or modify constraints. Alembic's `batch` mode handles this by recreating tables. Always use `with op.batch_alter_table(...)` for SQLite migrations.

### Sync-Ready Without Implementing Sync

Three columns added to `knowledge_items` now that cost nothing but prevent a breaking migration later:

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `sync_id` | TEXT UNIQUE | NULL | Stable UUID for cross-device identity (different from `id` which is local) |
| `synced_at` | TEXT | NULL | Last sync timestamp; NULL = never synced |
| `device_id` | TEXT | NULL | Which device created this item |

When sync is implemented:
- `sync_id` is populated on first sync per item (or at write time if device knows it's syncing)
- Conflict resolution uses `updated_at` as last-write-wins baseline
- No schema migration needed — columns already exist

**What is deferred to post-v1:**
- Sync transport (CRDTs vs last-write-wins vs operational transforms)
- Device registration and key exchange
- Conflict UI
- Cloud storage backend (S3, Cloudflare R2, or self-hosted)

**What must NOT be painted into a corner:**
- `id` must remain a UUID string (not an autoincrement INTEGER) — integers create conflicts on merge
- `created_at` / `updated_at` must be ISO 8601 UTC strings — enables cross-device comparison without timezone issues
- Tag storage as JSON array (not a normalized tags table) — avoids cross-device ID conflicts for tags

---

## Scaling Considerations

This is a personal tool targeting one user, hundreds to low thousands of items. Scaling analysis is brief by design.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0 - 2,000 items | Current design. No changes. sqlite-vec KNN is fast at this size. |
| 2,000 - 20,000 items | Add FTS5 virtual table for BM25 sparse search. Hybrid BM25 + vector with RRF fusion. |
| 20,000+ items | HNSW index (sqlite-vec supports ANN), or migrate vector store to LanceDB. |
| Multi-user (post-v1) | Separate DB per user or row-level tenant_id. Sync layer on top. |

**First performance bottleneck:** Embedding generation on CPU (50-150ms per item). At bulk import time this matters. Mitigation: batch fastembed's `embed()` call (it accepts a list, not just single strings) and process imports in batches of 32.

---

## Anti-Patterns

### Anti-Pattern 1: Storing Embeddings as BLOBs in the Main Table

**What people do:** Add an `embedding BLOB` column to `knowledge_items` and serialize numpy arrays there.

**Why it's wrong:** sqlite-vec's `vec0` virtual table is required for KNN queries — you cannot do `ORDER BY cosine_distance(embedding, ?)` on a BLOB column without loading all rows into Python. The `vec0` virtual table uses FAISS-style indexing internally.

**Do this instead:** Use the `vec_embeddings` virtual table + `vec_rowid_map` bridge pattern shown in the schema above.

### Anti-Pattern 2: Auto-Saving Everything from PostToolUse

**What people do:** Hook every Write/Edit event and save the file content as a snippet.

**Why it's wrong:** Produces thousands of low-quality, noisy entries. The retrieval quality degrades because every search returns irrelevant items. The capture becomes indistinguishable from a file history tool.

**Do this instead:** Use the Stop hook to analyze the full session transcript, identify patterns that were explicitly praised or reused, and suggest (not auto-save) them. Keep capture intentional.

### Anti-Pattern 3: One Fat Table for All 4 Knowledge Types

**What people do:** Single `knowledge` table with 20+ columns, most NULL for any given row.

**Why it's wrong:** Type-specific fields (e.g., `error_signature` for bugs, `always_load` for rules) are sparse and misleading. Queries become complex. Adding a field to one type requires migrating all rows.

**Do this instead:** Shared base table + type extension tables (one-to-one FK). JOIN cost is negligible at v1 scale.

### Anti-Pattern 4: Synchronous Embedding Model Load at Server Startup

**What people do:** Initialize fastembed model in server `__init__` or module-level code.

**Why it's wrong:** Model download (~270MB) happens on first use and takes 10-30 seconds. If done at startup, every server restart blocks. If the model is already cached, startup still loads it into memory unnecessarily if no embedding operations happen.

**Do this instead:** Lazy-load the model in `EmbeddingService._get_model()` on first `embed()` call. Cache the instance. Log a clear message when model download starts so the user knows what's happening.

### Anti-Pattern 5: Using INTEGER Primary Keys

**What people do:** `id INTEGER PRIMARY KEY AUTOINCREMENT` — the SQLite default.

**Why it's wrong:** When sync is added, integer IDs from two devices collide (both start at 1). Rewriting PKs across all relations when sync lands is a breaking migration.

**Do this instead:** UUID strings (`lower(hex(randomblob(16)))` or Python's `uuid.uuid4()`) as TEXT PKs from day one.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Claude Code | Hook scripts (command type) in `.claude/settings.json` | SessionStart, Stop, PostToolUse hooks POST to brain HTTP |
| Claude Desktop | MCP server registration in `claude_desktop_config.json` | stdio transport; no hook support in Desktop |
| Cursor / Windsurf | MCP server registration (per-IDE config) | stdio transport; hooks not available |
| fastembed ONNX models | In-process library call, ONNX Runtime | First call downloads model to `FASTEMBED_CACHE_PATH` |
| sqlite-vec | SQLite extension loaded via `sqlite3.load_extension()` | Must enable extension loading: `conn.enable_load_extension(True)` |

### Internal Boundaries

| Boundary | Communication | Considerations |
|----------|---------------|----------------|
| MCP Tools ↔ KnowledgeService | Direct async function call | Same process; no serialization overhead |
| Hook Scripts ↔ Server | HTTP POST to localhost:7832 | Must handle server-not-running gracefully (hook should not fail Claude Code) |
| EmbeddingService ↔ sqlite-vec | Serialize list[float] to binary via `struct.pack` | sqlite-vec accepts JSON array or compact binary; binary is faster |
| Alembic ↔ aiosqlite | Alembic uses sync SQLAlchemy; run in sync context at startup | Run migrations before starting the async server loop |

---

## Deferred to Post-v1 (Must Not Paint Into a Corner)

| Feature | Why Deferred | What Preserves Future Option |
|---------|-------------|------------------------------|
| Sync / multi-device | Unvalidated complexity | `sync_id`, `device_id`, `synced_at` columns already in schema |
| Multi-user | Out of scope v1 | UUID PKs, no hardcoded user references |
| Cloud embeddings (OpenAI) | Cost + privacy | EmbeddingService is an interface; swap provider without changing callers |
| BM25 hybrid search | Not needed at v1 scale | FTS5 virtual table is additive; no schema change to existing tables |
| GUI / web UI | v1 is MCP + CLI | All business logic in services, not in MCP layer — UI can call same services |
| GSD integration | Keep independent | brain has no GSD imports; GSD can call brain as a client |

---

## Sources

- [MCP Python SDK — GitHub](https://github.com/modelcontextprotocol/python-sdk) — HIGH confidence
- [FastMCP Context Injection docs](https://gofastmcp.com/servers/context) — HIGH confidence
- [MCP Resource & Prompt patterns — DeepWiki](https://deepwiki.com/modelcontextprotocol/python-sdk/2.3-tools-resources-and-prompts) — HIGH confidence
- [FastMCP Lifespan — DeepWiki](https://deepwiki.com/modelcontextprotocol/python-sdk/2.5-context-injection-and-lifespan) — HIGH confidence
- [sqlite-vec — GitHub (asg017)](https://github.com/asg017/sqlite-vec) — HIGH confidence
- [sqlite-vec usage guide — DEV Community](https://dev.to/stephenc222/how-to-use-sqlite-vec-to-store-and-query-vector-embeddings-58mf) — MEDIUM confidence
- [fastembed — GitHub (qdrant)](https://github.com/qdrant/fastembed) — HIGH confidence
- [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks) — HIGH confidence (official Anthropic docs)
- [Claude Code Hooks — all events (Pixelmojo)](https://www.pixelmojo.io/blogs/claude-code-hooks-production-quality-ci-cd-patterns) — MEDIUM confidence
- [Alembic batch operations for SQLite](https://alembic.sqlalchemy.org/en/latest/batch.html) — HIGH confidence (official Alembic docs)
- [Hybrid RAG retrieval patterns — VectorHub](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking) — MEDIUM confidence

---
*Architecture research for: brain — Python local-first MCP server with embedded RAG*
*Researched: 2026-04-14*

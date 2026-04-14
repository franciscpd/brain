# Roadmap: brain

## Overview

Brain is a local-first MCP server that acts as a persistent knowledge layer across AI sessions. The build order follows strict dependency chains: storage schema decisions are the most expensive to retrofit, so the foundation lands first. Once data can be stored correctly, CRUD and the MCP surface are built on top. Retrieval and session injection follow — this is the moment the core value ("never repeat yourself") becomes real. Manual and auto-capture pipelines come next, scaling the value loop. Lifecycle tooling and packaging close out v1, making the tool shippable and maintainable.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Storage + Embedding Foundation** - SQLite schema, sqlite-vec, FTS5, Alembic migrations, and embedded fastembed service
- [ ] **Phase 2: Knowledge CRUD + Scoping + MCP Core** - All four knowledge types, scope model, secret scanner, and the full MCP tool surface
- [ ] **Phase 3: Retrieval + Session Injection** - Hybrid retrieval pipeline and session-start context briefing — the core value delivered
- [ ] **Phase 4: Capture — Manual + Auto** - CLI and MCP capture paths, Stop hook pipeline, quality gates, and user review flow
- [ ] **Phase 5: Lifecycle, Packaging + Polish** - Contradiction detection, curation CLI, stats/reindex, and installable package

## Phase Details

### Phase 1: Storage + Embedding Foundation
**Goal**: The data layer is correctly structured and the embedding service is ready — every architectural decision that is expensive to retrofit lands here
**Depends on**: Nothing (first phase)
**Requirements**: STOR-01, STOR-02, STOR-03, STOR-04, STOR-05, STOR-06, STOR-07, EMB-01, EMB-02, EMB-03, EMB-04, EMB-05, EMB-06
**Success Criteria** (what must be TRUE):
  1. Running `brain-server` creates `~/.brain/brain.db` in WAL mode with all tables, indexes, and the sqlite-vec extension loaded — no manual setup required
  2. Schema contains UUID text PKs, ISO 8601 UTC timestamps, `sync_id`, `device_id`, and `embedding_model_id` on every vector row — a future sync migration requires no breaking changes
  3. Saving a snippet causes the EmbeddingService to compute and store a vector with the correct task prefix and associated model ID — observable via a `SELECT` on `vec_rowid_map`
  4. On first run, the user sees a clear message about the ~270MB model download before it starts — no silent hang
  5. Alembic `alembic upgrade head` applies migration 0001 cleanly on a fresh DB and is idempotent on an existing one
**Plans**: TBD

Plans:
- [ ] 01-01: SQLite schema, WAL mode, Alembic migration 0001 (knowledge_items + extension tables + vec bridge + FTS5)
- [ ] 01-02: EmbeddingService — fastembed lazy-load, model cache, AST-aware chunker, task prefixes, model-ID tagging, first-run UX

### Phase 2: Knowledge CRUD + Scoping + MCP Core
**Goal**: All four knowledge types can be saved, retrieved, listed, updated, and deleted through a fully functional MCP server surface — the build loop is testable end-to-end in MCP Inspector
**Depends on**: Phase 1
**Requirements**: KNOW-01, KNOW-02, KNOW-03, KNOW-04, KNOW-05, KNOW-06, SCOPE-01, SCOPE-02, SCOPE-03, SCOPE-04, MCP-01, MCP-02, MCP-03, MCP-04, MCP-05, MCP-06
**Success Criteria** (what must be TRUE):
  1. A rule saved as `scope=project, project=brain` is returned in search results when queried from the `brain` project directory, and never returned when queried from an unrelated project directory
  2. Attempting to save an entry containing a secret (API key, password) via any write path — MCP tool or CLI — returns an error and nothing is persisted
  3. `brain_search` tool called from MCP Inspector returns structured results for all four knowledge types with correct metadata
  4. The MCP server process starts, exposes all tools and resources, and handles requests without emitting any `print()` output to stdout
  5. Total MCP tool schema count is 8 or fewer — measurable with `mcp dev`
**Plans**: TBD

Plans:
- [ ] 02-01: KnowledgeService — CRUD for all 4 types, Pydantic models, secret scanner integration (KNOW-01..06)
- [ ] 02-02: Scope model — three scope types, hard-filter enforcement, project identification via MCP roots (SCOPE-01..04)
- [ ] 02-03: MCP server — FastMCP app, lifespan, tool registration, resource/prompt for session context, tool descriptions (MCP-01..06)

### Phase 3: Retrieval + Session Injection
**Goal**: The brain's primary value is live — rules and context are injected at session start without user action, and the AI can search the knowledge store on demand
**Depends on**: Phase 2
**Requirements**: RET-01, RET-02, RET-03, RET-04, RET-05, RET-06, SESS-01, SESS-02, SESS-03, SESS-04
**Success Criteria** (what must be TRUE):
  1. Opening a new Claude Code session in any project directory automatically injects the relevant global rules and project-specific rules into the context — the AI uses them without the user saying anything
  2. Calling `brain_search "handle payment webhook"` from within a Claude Code session returns the relevant snippet, decision, or bug lesson from a different project — cross-project retrieval works
  3. A rule saved as `scope=project, project=A` never appears in search results when the session is in project B — scope is a hard filter, not a ranking signal
  4. The session briefing respects the configured token budget — it does not inject more tokens than the limit even when the knowledge store is large
  5. Exact identifier lookup (e.g., `DATABASE_URL`, `handle_payment_webhook`) returns the relevant entry even when semantic similarity is low — FTS5 covers what vectors miss
**Plans**: TBD

Plans:
- [ ] 03-01: RetrievalService — structured SQL search, KNN vector search, FTS5, hybrid RRF fusion, recency decay, scope hard-filter, top-k limits (RET-01..06)
- [ ] 03-02: Session injection — get_session_context(), MCP Resource/Prompt, SessionStart hook shim, token budget enforcement, end-to-end validation (SESS-01..04)

### Phase 4: Capture — Manual + Auto
**Goal**: Knowledge can be captured without friction from both CLI and Claude Code, and the Stop hook extracts session lessons automatically after user opt-in
**Depends on**: Phase 3
**Requirements**: CAPT-01, CAPT-02, CAPT-03, AUTO-01, AUTO-02, AUTO-03, AUTO-04
**Success Criteria** (what must be TRUE):
  1. Typing `brain save rule "always use ruff format"` from a terminal completes in under 10 seconds including secret scan and embedding — the entry is visible in subsequent searches
  2. Asking Claude Code to "save this as a rule" triggers the `brain_capture` tool and stores the entry — the user receives confirmation without leaving the conversation
  3. After opting in, ending a Claude Code session causes the Stop hook to present a list of capture candidates — the user can accept, reject, or skip each before anything is persisted
  4. No entry containing credentials, tokens, or passwords is persisted by any capture path (manual or auto) — the secret scanner blocks the write and reports what it found
**Plans**: TBD

Plans:
- [ ] 04-01: Manual capture — `brain save` CLI command, CAPT-01 MCP tool path, <10s friction validation (CAPT-01..03)
- [ ] 04-02: Auto-capture pipeline — Stop hook transcript analysis, quality gate (length filter, blocklist, secret scan, dedup), opt-in config, confirm-before-save review flow (AUTO-01..04)

### Phase 5: Lifecycle, Packaging + Polish
**Goal**: The brain is installable from a single command, knowledge stays healthy through contradiction warnings and curation tools, and the project is ready for daily use
**Depends on**: Phase 4
**Requirements**: LIFE-01, LIFE-02, LIFE-03, LIFE-04, PKG-01, PKG-02, PKG-03, PKG-04
**Success Criteria** (what must be TRUE):
  1. `uv tool install brain-server` on a clean machine installs the server and makes `brain-server` and `brain` available as commands — no manual steps required
  2. Saving a rule that contradicts an existing rule in the same scope triggers a warning with both rules shown — nothing is auto-merged or silently overwritten
  3. `brain list`, `brain edit`, `brain delete`, `brain stats`, and `brain reindex` all work correctly from the terminal
  4. The README quickstart takes a new user from install to seeing their first saved rule injected into a Claude Code session — end-to-end, no prior knowledge of the codebase required
**Plans**: TBD

Plans:
- [ ] 05-01: Contradiction detection — pre-save similarity check, user-facing conflict alert (LIFE-01)
- [ ] 05-02: Curation CLI — `brain list/edit/delete`, `brain stats`, `brain reindex` (LIFE-02..04)
- [ ] 05-03: Packaging — pyproject.toml + uv, console_scripts, MCP registration docs, README quickstart (PKG-01..04)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Storage + Embedding Foundation | 0/2 | Not started | - |
| 2. Knowledge CRUD + Scoping + MCP Core | 0/3 | Not started | - |
| 3. Retrieval + Session Injection | 0/2 | Not started | - |
| 4. Capture — Manual + Auto | 0/2 | Not started | - |
| 5. Lifecycle, Packaging + Polish | 0/3 | Not started | - |

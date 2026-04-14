# Requirements: brain

**Defined:** 2026-04-14
**Core Value:** Never again having to manually repeat the same rules, preferences, and coding patterns to the AI in every new project.

## v1 Requirements

Requirements for the initial release. Each maps to a phase in the roadmap.

### Storage & Schema (STOR)

- [ ] **STOR-01**: Local SQLite database created at a configurable path (default `~/.brain/brain.db`), in WAL mode with `busy_timeout` set
- [ ] **STOR-02**: `knowledge_items` schema with shared fields (id UUID, kind, scope_type, scope_value, tags, content, created_at, updated_at, embedding_model_id, sync_id, synced_at, device_id)
- [ ] **STOR-03**: Type-specific extension tables (`rules`, `snippets`, `decisions`, `bugs`) linked 1:1 to `knowledge_items`
- [ ] **STOR-04**: `sqlite-vec` virtual table (`knowledge_vec`) + bridge table (`vec_rowid_map`) for KNN search via cosine distance
- [ ] **STOR-05**: FTS5 index over `content` and relevant fields for exact text search and BM25 ranking
- [ ] **STOR-06**: Migrations managed via Alembic from the initial migration (batch mode for SQLite compatibility)
- [ ] **STOR-07**: Schema prepared for future sync (UUID PKs, ISO 8601 UTC timestamps, device_id, sync_id) — without implementing sync

### Embedding Service (EMB)

- [ ] **EMB-01**: Embedded embedding service using `fastembed` with model `nomic-ai/nomic-embed-text-v1.5` — no dependency on Ollama or external APIs
- [ ] **EMB-02**: Model loaded lazily (on first call), cached at `~/.brain/models/` via `FASTEMBED_CACHE_PATH`
- [ ] **EMB-03**: AST-aware chunker for code snippets (respects function/class boundaries), with token-count chunker fallback for free text
- [ ] **EMB-04**: Task prefixes applied correctly (`search_document: ` on write, `search_query: ` on read) as required by nomic-embed
- [ ] **EMB-05**: Every vector stored with its associated `embedding_model_id` — a future model upgrade only reindexes affected entries
- [ ] **EMB-06**: First run communicates the model download (~270MB) to the user clearly

### Knowledge CRUD (KNOW)

- [ ] **KNOW-01**: Create, read, update, and delete **personal rules** (type: `rule`) with fields: title, content, tags, scope, priority
- [ ] **KNOW-02**: Create, read, update, and delete **reusable snippets/solutions** (type: `snippet`) with fields: title, code, language, usage context, tags, scope
- [ ] **KNOW-03**: Create, read, update, and delete **architectural decisions** (type: `decision`) with fields: title, context, decision, rationale, considered alternatives, scope
- [ ] **KNOW-04**: Create, read, update, and delete **bug/error lessons** (type: `bug_lesson`) with fields: title, symptom, root cause, fix, prevention, tags, scope
- [ ] **KNOW-05**: List entries by type, filtered by scope (global/project/language) and tags
- [ ] **KNOW-06**: Every write passes through a secret scanner (`detect-secrets` or equivalent) — writes are blocked if credentials are detected

### Scoping (SCOPE)

- [ ] **SCOPE-01**: Three scope types supported: `global` (applies in any context), `project` (applies only within the identified project), `language` (applies to a specific language)
- [ ] **SCOPE-02**: Retrieval filters apply scope as a hard filter (not just ranking) — rules from project A never leak into project B
- [ ] **SCOPE-03**: `global` rules can be overridden by `project` rules on the same topic (override via tag/topic)
- [ ] **SCOPE-04**: Current-project identification via MCP roots, with working directory as a documented fallback

### MCP Server (MCP)

- [ ] **MCP-01**: Working stdio MCP server using the official SDK (`mcp` with FastMCP), with no `print()` on the JSON-RPC stream
- [ ] **MCP-02**: Lifespan pattern used for DB initialization and lazy-loading of the embedding model
- [ ] **MCP-03**: MCP Tools exposed for capture (one tool per knowledge type, or a unified tool with a `kind` parameter)
- [ ] **MCP-04**: `brain_search` MCP Tool for on-demand AI-driven search — with a description clear enough that the AI knows when to call it
- [ ] **MCP-05**: MCP Resource or Prompt exposing relevant rules for the current project, for session-start injection
- [ ] **MCP-06**: Tool descriptions follow best practices (decision criteria for an LLM, not human documentation) — target < 8 tools total to minimize schema overhead

### Retrieval (RET)

- [ ] **RET-01**: Structured search by type + tags + scope + textual substring (fast, exact)
- [ ] **RET-02**: Semantic search via `sqlite-vec` KNN for snippets/decisions/bugs
- [ ] **RET-03**: Hybrid retrieval: FTS5 (BM25) + vector search with result fusion (RRF or weighted sum)
- [ ] **RET-04**: Recency decay applied to ranking (recent entries get a mild boost; per-type values configurable)
- [ ] **RET-05**: Rules are retrieved primarily via structured lookup (the main path does not depend on vector RAG)
- [ ] **RET-06**: Configurable result cap and maximum payload size — prevents poisoning the client's context window

### Session Context Injection (SESS)

- [ ] **SESS-01**: Endpoint/resource returning a contextual briefing for the current project (global rules + project rules + relevant decisions)
- [ ] **SESS-02**: Injection at Claude Code session start via SessionStart hook or MCP Resource (whichever the client supports — choice documented per client)
- [ ] **SESS-03**: Briefing formatted as concise Markdown, respecting a configurable token budget
- [ ] **SESS-04**: Manual validation in the Claude Code CLI that rules are loaded and respected by the AI

### Capture — Manual (CAPT)

- [ ] **CAPT-01**: Manual capture via MCP tools — the AI can save a rule/snippet/decision/bug when the user asks
- [ ] **CAPT-02**: `brain save` CLI command for direct user capture without going through the AI (`brain save rule "use ruff format"`)
- [ ] **CAPT-03**: The capture workflow takes <10 seconds between intent and confirmation ("zero friction")

### Capture — Automatic (AUTO)

- [ ] **AUTO-01**: Claude Code Stop hook extracts candidates (declared rules, useful snippets, decisions made, bugs resolved) from the session transcript
- [ ] **AUTO-02**: Candidates pass a quality gate (secret scan + semantic dedup + minimum relevance) before being saved
- [ ] **AUTO-03**: Auto-capture is opt-in per project — disabled by default until the user trusts the distillation
- [ ] **AUTO-04**: The user can review candidates before persistence in a "confirm before save" mode

### Lifecycle & Quality (LIFE)

- [ ] **LIFE-01**: Contradiction detection on write — if a new rule conflicts with an existing rule in the same scope, warn the user (do not auto-resolve)
- [ ] **LIFE-02**: `brain list/edit/delete` CLI commands for manual curation
- [ ] **LIFE-03**: `brain stats` CLI command shows counts by type, scope, and index size
- [ ] **LIFE-04**: `brain reindex` CLI command regenerates embeddings (useful when switching models in the future)

### Packaging & Install (PKG)

- [ ] **PKG-01**: Project packaged with `pyproject.toml` + `uv`, exposing console_script entry points (`brain-server`, `brain`)
- [ ] **PKG-02**: Installation via `uv tool install brain-server` or `pip install brain-server`
- [ ] **PKG-03**: MCP registration command documented for Claude Code, Claude Desktop, Cursor/Windsurf, and direct SDK
- [ ] **PKG-04**: README quickstart: install → register → save first rule → see the rule used in a new session

## v2 Requirements

Deferred to future releases. Tracked but out of current scope.

### Sync & Multi-Device (SYNC)

- **SYNC-01**: Sync across multiple machines belonging to the same user (schema already prepared)
- **SYNC-02**: Conflict resolution on sync (last-write-wins vs merge)
- **SYNC-03**: Client mode connecting to a remote brain server

### Collaboration (COLL)

- **COLL-01**: Read-only knowledge sharing between devs on a team
- **COLL-02**: Export/import of curated rule sets

### Advanced Capture (ADV)

- **ADV-01**: Auto-capture using PostToolUse hooks with finer heuristics
- **ADV-02**: Proactive suggestions to the user ("save this rule?") based on repeated patterns
- **ADV-03**: Automated mining of existing repositories to extract implicit rules

### Cloud Embeddings (CLOUD)

- **CLOUD-01**: Option to use OpenAI/Voyage embeddings for maximum quality (configurable, not default)
- **CLOUD-02**: Code-specialized model (`nomic-embed-code`, `voyage-code-3`) as an alternative to general-purpose

### UX (UX)

- **UX-01**: Web/TUI interface for visual knowledge curation
- **UX-02**: Visual diff when a contradiction is detected between rules

## Out of Scope

Explicit exclusions. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Project documentation (README, API docs) | That lives in the repository; brain does not replace formal docs |
| Ticket/task system (Linear/Jira) | Brain does not manage pending work, only consolidated knowledge |
| Conversation memory / session summaries | Brain is for actionable patterns, not chat recall |
| Generic knowledge base (Notion/Obsidian) | Strictly focused on code/development |
| Cloud sync in v1 | Schema is prepared, but implementation is deferred to v2 |
| Multi-user / team sharing in v1 | v1 scope is strictly personal |
| GSD integration | Brain is cross-tool; GSD is a per-project workflow |
| Cloud embeddings in v1 | Local-first is a deliberate decision; cloud becomes a future option |
| Web interface / GUI in v1 | v1 is MCP + CLI; UI is post-v1 |
| TTL/automatic knowledge expiration | Personal rules do not expire; time-based expiration is an anti-pattern for this use case |
| Auto-capture on by default | Quality gates need to mature; starts opt-in |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STOR-01 | Phase 1 | Pending |
| STOR-02 | Phase 1 | Pending |
| STOR-03 | Phase 1 | Pending |
| STOR-04 | Phase 1 | Pending |
| STOR-05 | Phase 1 | Pending |
| STOR-06 | Phase 1 | Pending |
| STOR-07 | Phase 1 | Pending |
| EMB-01 | Phase 1 | Pending |
| EMB-02 | Phase 1 | Pending |
| EMB-03 | Phase 1 | Pending |
| EMB-04 | Phase 1 | Pending |
| EMB-05 | Phase 1 | Pending |
| EMB-06 | Phase 1 | Pending |
| KNOW-01 | Phase 2 | Pending |
| KNOW-02 | Phase 2 | Pending |
| KNOW-03 | Phase 2 | Pending |
| KNOW-04 | Phase 2 | Pending |
| KNOW-05 | Phase 2 | Pending |
| KNOW-06 | Phase 2 | Pending |
| SCOPE-01 | Phase 2 | Pending |
| SCOPE-02 | Phase 2 | Pending |
| SCOPE-03 | Phase 2 | Pending |
| SCOPE-04 | Phase 2 | Pending |
| MCP-01 | Phase 2 | Pending |
| MCP-02 | Phase 2 | Pending |
| MCP-03 | Phase 2 | Pending |
| MCP-04 | Phase 2 | Pending |
| MCP-05 | Phase 2 | Pending |
| MCP-06 | Phase 2 | Pending |
| RET-01 | Phase 3 | Pending |
| RET-02 | Phase 3 | Pending |
| RET-03 | Phase 3 | Pending |
| RET-04 | Phase 3 | Pending |
| RET-05 | Phase 3 | Pending |
| RET-06 | Phase 3 | Pending |
| SESS-01 | Phase 3 | Pending |
| SESS-02 | Phase 3 | Pending |
| SESS-03 | Phase 3 | Pending |
| SESS-04 | Phase 3 | Pending |
| CAPT-01 | Phase 4 | Pending |
| CAPT-02 | Phase 4 | Pending |
| CAPT-03 | Phase 4 | Pending |
| AUTO-01 | Phase 4 | Pending |
| AUTO-02 | Phase 4 | Pending |
| AUTO-03 | Phase 4 | Pending |
| AUTO-04 | Phase 4 | Pending |
| LIFE-01 | Phase 5 | Pending |
| LIFE-02 | Phase 5 | Pending |
| LIFE-03 | Phase 5 | Pending |
| LIFE-04 | Phase 5 | Pending |
| PKG-01 | Phase 5 | Pending |
| PKG-02 | Phase 5 | Pending |
| PKG-03 | Phase 5 | Pending |
| PKG-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 54 total
- Mapped to phases: 54/54 ✓
- Unmapped: 0

| Phase | Requirements | Count |
|-------|-------------|-------|
| Phase 1 — Storage + Embedding Foundation | STOR-01..07, EMB-01..06 | 13 |
| Phase 2 — Knowledge CRUD + Scoping + MCP Core | KNOW-01..06, SCOPE-01..04, MCP-01..06 | 16 |
| Phase 3 — Retrieval + Session Injection | RET-01..06, SESS-01..04 | 10 |
| Phase 4 — Capture (Manual + Auto) | CAPT-01..03, AUTO-01..04 | 7 |
| Phase 5 — Lifecycle, Packaging + Polish | LIFE-01..04, PKG-01..04 | 8 |

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after roadmap creation (traceability populated)*

# Project Research Summary

**Project:** brain — personal local-first MCP server with embedded RAG
**Domain:** Cross-project AI code knowledge persistence (rules, snippets, decisions, bugs)
**Researched:** 2026-04-14
**Confidence:** HIGH

---

## Executive Summary

Brain occupies a genuine gap in the current AI developer tooling ecosystem: no existing tool combines structured knowledge types, local-first storage with real embeddings, cross-project scope, and hybrid capture/retrieval in a single MCP server. The closest competitors (mem0, Copilot Memory, claude-mem, Cursor rules) each solve one or two of these dimensions but fail on the others — mem0 is cloud-only, Copilot Memory is repo-locked, claude-mem captures noise indiscriminately, Cursor rules require manual authoring with no retrieval. Brain's core value proposition is "save a rule once, get it everywhere, without repeating yourself to every AI client."

The recommended implementation approach is: Python 3.11+, official MCP SDK (FastMCP interface), SQLite with `sqlite-vec` for unified metadata and vector storage, `fastembed` with `nomic-embed-text-v1.5` for local ONNX-based embeddings, `alembic` for schema migrations from day one, and `uv` for packaging and distribution. This stack is intentionally minimal — no daemons, no heavy ML frameworks, no network dependencies. The entire system installs from a single `uvx brain-server` command and runs in-process.

The primary risk is retrieval quality degradation from architectural choices made early: chunking strategy, embedding model selection, scope enforcement, and top-k limits are all expensive to retrofit once knowledge is stored. The schema must also be sync-ready from day one (UUID PKs, ISO 8601 timestamps, `sync_id`/`device_id` columns) to avoid a breaking migration when multi-device support is eventually added. Build order is strict: storage foundation → embedding service → knowledge CRUD → retrieval → MCP layer → session injection hooks. Skipping ahead breaks dependencies.

---

## Key Findings

### Recommended Stack

| Library | Version | Why |
|---------|---------|-----|
| `mcp` (official Python SDK) | 1.27.0 | FastMCP 1.0 merged in; `mcp.server.fastmcp.FastMCP` is the decorator API. stdio transport, tool/resource/prompt support, Pydantic v2 integrated. |
| Python | 3.11+ | Required by mcp + fastembed; 3.11 recommended for performance |
| `fastembed` | 0.8.0 | ONNX Runtime (not PyTorch). ~50MB install. In-process, no daemon. Model cached after first download. Meets "runs on any machine" constraint. |
| `sqlite-vec` | 0.1.9 | Embedded vector KNN inside SQLite. Single .so extension, loaded at runtime. Brute-force fast enough for <10K vectors. Co-located with metadata — one file, one backup. |
| SQLite (stdlib) | bundled | Zero install friction, WAL mode for concurrent reads, file-portable, versionable schema. Row-oriented access pattern is the right fit (DuckDB is columnar/wrong). |
| `alembic` + `SQLAlchemy` | 1.15+ / 2.x | Schema migrations from day one. Batch mode handles SQLite ALTER limitations. Avoids broken upgrade paths as schema evolves. |
| `pydantic` | 2.x | MCP SDK requires v2. Use for knowledge entry models — free JSON schema generation for tool parameters. |
| `uv` | latest | Official MCP tooling standard. `uvx brain-server` installs-and-runs. Lockfile for reproducible installs. |

**Default embedding model:** `nomic-ai/nomic-embed-text-v1.5` (768 dims, ~270MB ONNX, 86%+ MTEB). Requires `"search_document: "` prefix on storage and `"search_query: "` prefix on queries. Fallback: quantized `-Q` variant (~70MB, still excellent quality).

**What to avoid (high-cost decisions):** Ollama (daemon dependency), `sqlite-vss` (archived), `sentence-transformers` (PyTorch, 2GB install), `all-MiniLM-L6-v2` (56% Top-1 accuracy), SSE transport (deprecated June 2025), `print()` in stdio server (corrupts JSON-RPC stream), integer PKs (block sync), ChromaDB (500MB, wrong scale).

### Expected Features

**Table stakes (broken without these):**

1. `brain_capture` — save entry with type, content, tags, scope; minimum capture path
2. `brain_search` — semantic search via local embeddings; primary AI-driven retrieval
3. `brain_list` — list with type/scope/tag filters; auditable knowledge store
4. `brain_delete` / `brain_update` — stale/wrong knowledge is worse than no knowledge; curation is a feature
5. Global + project scope — cross-project is the core differentiator; without it, brain is just another per-project rules file
6. 4 structured knowledge types (rules, snippets, decisions, bugs) — different retrieval lifecycles; a generic "bag of text" degrades
7. Session context injection at startup — rules must reach AI without user action; directly solves the primary pain (repeating rules to every session)
8. Local SQLite + embedded vector index — privacy non-negotiable; offline-capable; zero cost

**Differentiators (competitive advantage):**

1. Hybrid retrieval: structured SQL injection (rules at session start) + on-demand semantic search — no competitor does both
2. Type-aware retrieval scoring — bugs are noise for "implement auth"; rules always relevant; types influence ranking
3. Claude Code Stop hook auto-capture — AI extracts lessons at session end; catches what user forgets to save
4. Tagging with multi-tag support — organizes without forcing strict hierarchies
5. Source attribution — `source_project`, `created_at`, `updated_at` on every entry; traceability for v1.x features
6. Contradiction flag on capture — pre-save similarity check surfaces conflicts rather than silently accumulating contradictions

**Defer to v2+:**
- Cloud sync / multi-device (adds auth + conflict resolution before value is validated)
- Team sharing / multi-user (different threat model entirely)
- Web UI (CLI sufficient for developer users)
- Knowledge freshness decay scoring (over-engineering at launch scale)

**Anti-features (deliberately excluded):**
- Full-conversation auto-capture (62% of auto-captured memories are wrong or irrelevant — research finding)
- Session history / replay (explicitly out of scope; use claude-mem if needed)
- Cloud embeddings as default (privacy + offline constraints)
- Time-based expiry (rules do not expire; user curates)
- Automatic deduplication without confirmation (semantic similarity is not semantic equivalence)

### Architecture Overview

Brain is a 5-layer system. The MCP Client Layer (Claude Code, Claude Desktop, Cursor) communicates via MCP stdio protocol to the MCP Server Layer (FastMCP app with tools, resources, and prompts). The Server Layer delegates to a Service Layer (KnowledgeService for CRUD, RetrievalService for two-stage hybrid search, EmbeddingService for fastembed wrapper). The Storage Layer is a single SQLite file with the `sqlite-vec` extension loaded at runtime — a shared-base table `knowledge_items` with four type-extension tables (rules, snippets, decisions, bugs) joined one-to-one, plus a `vec_embeddings` virtual table bridged to items via `vec_rowid_map`. The Capture Pipeline consists of thin shell hook scripts (SessionStart, Stop, PostToolUse) that POST to a lightweight HTTP endpoint the brain server exposes alongside its MCP transport.

Retrieval is two-stage: Stage 1 uses structured SQL to inject rules by scope and `always_load` flag (session start path); Stage 2 uses sqlite-vec KNN for semantic search of snippets, decisions, and bugs. Results merge by type priority (rules first) and distance threshold (drop candidates above 0.4 cosine distance). FTS5 full-text search is layered in for exact identifier lookup — function names, error codes, env var names cannot be reliably retrieved by vector similarity alone. Embeddings are computed synchronously at write time (20–100ms per item on CPU is acceptable at v1 scale); the model is lazy-loaded on first use and kept in memory for the server process lifetime.

**Build order (strict dependency chain):**
1. Storage foundation (SQLite schema + sqlite-vec + FTS5 + Alembic)
2. Embedding service (fastembed wrapper, lazy-load, model cache)
3. Knowledge CRUD — KnowledgeService (all 4 types, scope resolution)
4. Retrieval service (two-stage SQL + KNN + FTS5, scope enforcement, fusion)
5. MCP server layer (FastMCP app, lifespan, 4–6 tool registration with precise descriptions)
6. Session-start context + hook scripts (get_session_context, HTTP endpoint, hook shims)
7. Auto-capture pipeline (Stop hook transcript analysis — optional v1, defer if time-constrained)

**Critical path for core value:** Phases 1 → 2 → 3 → 5 delivers "save a rule, retrieve it manually" — proves the loop. Phase 4 adds semantic search. Phase 6 makes it zero-friction.

### Critical Pitfalls

The following pitfalls are expensive to retrofit — they shape schema and retrieval architecture and must be addressed in Phase 1.

1. **Integer primary keys** — Block sync implementation. Use UUID TEXT PKs (`lower(hex(randomblob(16)))`) from the first migration. Changing PKs across all relations post-facto is a breaking migration with cascading rewrites.

2. **Missing `embedding_model_id` on stored vectors** — When the model changes, mixed embedding spaces produce garbage results with high confidence scores (silent failure). Store model ID on every vector row; treat model upgrades as migration events, not config changes.

3. **No WAL mode + missing FTS5 virtual table** — `PRAGMA journal_mode=WAL` prevents `SQLITE_BUSY` errors under concurrent Claude Code sessions (two terminals = two concurrent writers). FTS5 is needed for exact identifier lookup (`DATABASE_URL`, `handle_payment_webhook`). Both must be configured at table creation — retroactive addition is disruptive.

4. **Scope as soft ranking signal instead of hard filter** — Global rules silently outrank project-specific rules when scope is just a weighted input. Scope must be a SQL WHERE clause applied before vector search, not a score modifier applied after. Query order: project-local first, expand to global only if sparse. Never `project_id=None` as "search everything."

5. **Tool schema bloat** — Each MCP tool injects its schema into every message (unavoidable MCP protocol overhead). 8+ tools = 2,000–5,000 tokens of constant per-turn tax before any retrieval happens. Target 4–6 tools maximum. Combine operations via parameters (e.g., one `brain_search` with a `type` filter, not four separate search tools). Measure schema token cost with `mcp dev` before shipping.

6. **Top-k too large + no return size limit** — Default top-k of 10 at ~500 tokens/chunk = 5,000 tokens injected per retrieval call. Research confirms retrieval quality peaks then declines as chunk count increases. Default to top-k=3, max 5. Add `maxResultSizeChars` annotation to all tools.

7. **Auto-capture without quality gates** — After a week, the brain fills with WIP commit messages, temp debug snippets, and half-formed notes. Retrieval degrades invisibly. Non-negotiable gates before any auto-capture is enabled: content length filter (>50 chars), commit message pattern blocklist, `detect-secrets` scanner, deduplication check. Build gates before enabling auto-capture.

---

## Implications for Roadmap

### Suggested Phase Structure

**Phase 1: Storage + Embedding Foundation**
- Rationale: Every other component depends on schema decisions made here. PKs, metadata fields, scope model, FTS5, WAL mode, and sync-readiness columns are the highest-cost changes to make retroactively.
- Delivers: SQLite DB with correct schema, sqlite-vec extension loaded, FTS5 virtual table, WAL mode, Alembic migration 0001, EmbeddingService with lazy-load fastembed, `sync_id`/`device_id`/`synced_at` columns in place, `vec_rowid_map` bridge table.
- Must avoid: Integer PKs, missing `embedding_model_id`, missing sync columns, skipping WAL mode, BLOB embeddings in main table.
- Research flag: Standard patterns — no additional research needed. All tools have official documentation.

**Phase 2: Knowledge CRUD + MCP Core**
- Rationale: KnowledgeService is the prerequisite for retrieval. MCP tools are thin wrappers over services — build services first, wrap second. This phase proves the full capture path works.
- Delivers: KnowledgeService (save/get/update/delete for all 4 types, scope resolution), Pydantic models, 4–6 MCP tools registered with decision-criteria descriptions (not generic summaries), MCP Inspector testable end-to-end.
- Must avoid: Vague tool descriptions (Claude will not call tools it cannot reason about when to use), too many tools (schema token budget), one fat table for all types (use shared-base + extension tables).
- Research flag: Standard patterns. MCP SDK docs are authoritative.

**Phase 3: Retrieval + Session Injection**
- Rationale: Two-stage hybrid retrieval is the brain's primary capability. Session injection (rules at startup without user action) directly solves the stated primary user pain. Both are needed before the tool is genuinely useful in daily work.
- Delivers: RetrievalService with SQL+KNN+FTS5 hybrid search, scope enforcement as hard pre-filter, top-k=3 default with 0.4 cosine distance threshold, `get_session_context()` tool, SessionStart hook script, HTTP endpoint for hook communication.
- Must avoid: Vector-only retrieval (misses exact identifiers), scope as soft ranking signal, top-k too large, no return size limits.
- Research flag: Light research recommended on SQLite-specific BM25+vector RRF fusion. Most hybrid retrieval examples use separate systems; the FTS5+sqlite-vec in-query merge pattern is less documented.

**Phase 4: Capture Quality + Auto-Capture Pipeline**
- Rationale: Manual capture proves the value loop; auto-capture scales it. Quality gates must exist before auto-capture — noise is harder to remove than to prevent. The Stop hook (full transcript) is a better trigger than PostToolUse (single event with no context).
- Delivers: Quality gate pipeline (length filter, blocklist, `detect-secrets` scanner, deduplication check), Stop hook transcript analysis, auto-capture suggestions presented to user for confirmation (not auto-save), capture friction reduction.
- Must avoid: Auto-save without confirmation (high noise rate), no secret scanner (credentials leak into brain), PostToolUse hook saving everything indiscriminately.
- Research flag: Verify Claude Code hook output format for `additionalContext` injection — JSON schema may differ from documentation in current SDK version.

**Phase 5: Knowledge Lifecycle + Polish**
- Rationale: After weeks of daily use, contradiction detection and staleness become the dominant failure modes. This phase is additive — it does not block launch but is needed for sustained quality.
- Delivers: Contradiction warning on capture (pre-save similarity search, cosine > 0.85 threshold), `brain_get` by ID for inspection workflows, CLAUDE.md importer for onboarding existing rules, `last_accessed_at` access tracking, `brain audit` CLI command surfacing stale items.
- Must avoid: Silent auto-merge of contradicting rules — surface conflicts and require user resolution.
- Research flag: Standard patterns. Lower complexity, entirely additive to existing schema.

### Phase Ordering Rationale

- Phase 1 is non-negotiable first: schema decisions (PKs, metadata, scope model, FTS5) are the highest-cost retroactive changes. Every subsequent phase depends on the storage contract.
- Phase 2 before retrieval: KnowledgeService is a dependency of RetrievalService. You cannot search what is not stored or modeled.
- Phase 3 before auto-capture: The retrieval pipeline and quality baseline must exist before auto-capture feeds into it. Noise captured before retrieval is tuned is invisible and degrades the baseline.
- Phase 4 deferred but not cut from v1: manual capture validates the value loop; auto-capture scales it once the loop is proven.
- Phase 5 is additive and addresses post-launch failure modes without blocking delivery.

### Research Flags

- **Phase 3:** Needs targeted research on SQLite FTS5 + sqlite-vec BM25/vector fusion in a single query.
- **Phase 4:** Verify current Claude Code hook `additionalContext` output JSON schema against live SDK docs before implementing hook scripts.
- **All phases:** Measure MCP tool schema token counts empirically with `mcp dev` before shipping each phase. Do not estimate.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified against official docs and PyPI. Versions confirmed current as of 2026-04-14. Embedding benchmark figures are MEDIUM — MTEB leaderboard should be checked at implementation time. |
| Features | HIGH | Cross-verified against 7 live competitor tools. Competitor feature gaps are well-documented. The "62% wrong memories" figure is directional (single source). |
| Architecture | HIGH | MCP SDK, sqlite-vec, fastembed, Alembic all have current official documentation. Build order confirmed by dependency analysis. Hook HTTP endpoint pattern needs empirical validation. |
| Pitfalls | HIGH | Most pitfalls are structural with well-understood failure modes (PKs, schema, scope, embedding model versioning). Conflict detection threshold (0.85) is empirical and will need tuning. |

**Overall confidence: HIGH**

### Gaps to Address

- **One vs two embedding models (rules/decisions vs code snippets):** PITFALLS.md recommends a code-tuned model (`nomic-embed-code`) for snippet type; STACK.md recommends a single model (`nomic-embed-text-v1.5`). Resolution: build `EmbeddingService` with a `model_for_type()` dispatch interface from day one (costs nothing), ship with one model, add code model in v1.x when users report poor snippet retrieval. Do not defer the interface.

- **Hook-to-server communication pattern:** Two options — HTTP POST to localhost:7832 (reliable, requires HTTP endpoint) or MCP resource auto-injection (cleaner, depends on client support). Verify whether Claude Code natively auto-reads MCP resources at session start before committing to the HTTP approach. The HTTP approach is the safe fallback.

- **Contradiction detection threshold:** Cosine similarity > 0.85 as a conflict flag is an empirical starting value. Build the infrastructure in Phase 5, tune threshold post-launch based on real false positive/negative rate.

---

## Sources

### Primary (HIGH confidence)
- MCP Python SDK GitHub (modelcontextprotocol/python-sdk) — version 1.27.0, FastMCP, stdio transport, logging gotcha
- fastembed GitHub (qdrant/fastembed) + PyPI — version 0.8.0, ONNX Runtime, model list, task prefixes
- sqlite-vec GitHub (asg017/sqlite-vec) + PyPI — version 0.1.9, Python API, vec0 virtual table
- Alembic official docs — batch mode for SQLite ALTER
- Claude Code Hooks reference (official Anthropic docs) — hook event types, JSON schema, additionalContext
- Claude Code MCP registration docs — user-scope registration, uvx pattern
- MCP resource/prompt/tool patterns — MCP SDK DeepWiki

### Secondary (MEDIUM confidence)
- Competitor feature analysis: mem0, Copilot Memory, claude-mem, Cursor rules, Continue.dev, Letta — current as of research date
- Embedding benchmark figures (nomic vs MiniLM accuracy) — multiple blog sources, directional signal
- FastMCP 2.0 announcement — clarifies community vs official SDK split
- Hybrid RAG retrieval patterns (BM25+vector, RRF) — VectorHub/Superlinked

### Tertiary (LOW confidence / validate before use)
- "62% wrong memories" figure — single Medium article; treat as directional
- Hook `additionalContext` output format specifics — needs empirical verification against current Claude Code SDK version

---

*Research completed: 2026-04-14*
*Ready for roadmap: yes*

# Feature Research

**Domain:** Personal MCP "brain" server — persistent cross-project code knowledge for AI clients
**Researched:** 2026-04-14
**Confidence:** HIGH (verified against multiple live tools: mem0, Copilot Memory, claude-mem, Claude memory tool, Letta, Continue.dev, Cursor rules)

---

## Ecosystem Survey

### How Existing Tools Handle Persistent Cross-Session/Cross-Project Knowledge

**mem0 (MCP):** Exposes 8 tools — `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`, `delete_memory`, `delete_all_memories`, `list_entities`. Scopes by user/agent/app/run. Cloud-hosted; no local-first option in the standard server. Good at semantic search, poor at structured rule injection.

**Claude memory tool (Anthropic API):** File-system-based tool giving Claude a `/memories` directory with `view`, `create`, `str_replace`, `insert`, `delete`, `rename` commands. AI decides proactively when to read/write. System prompt instructs "ALWAYS VIEW MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE." Per-agent, not cross-project.

**claude-mem:** MCP plugin capturing tool usage and file operations per session. 5-stage lifecycle: context injection at startup → prompt logging → tool observation capture → AI-powered learning extraction → session summarization. Retrieves previous 10 sessions automatically at start. Stores in SQLite + FTS5. Focuses on session replay, not curated rules.

**claude-memory-compiler:** Uses Claude Code Stop hook → flush.py → extracts decisions/lessons → compiles into cross-referenced markdown articles. At personal scale (50-500 articles) index.md + LLM reading outperforms vector similarity. No structured knowledge types — everything is "articles." No MCP server, just files.

**Copilot Memory (GitHub):** Auto-captures repository-specific facts (coding conventions, architectural patterns, cross-file dependencies) as Copilot works. Validates citations against current codebase before use. 28-day expiration unless reused. Strictly repo-scoped — cannot cross project boundaries. No manual capture path.

**Cursor rules (.cursor/rules/*.mdc):** File-based, project-scoped. Supports glob-based conditional activation (e.g., `src/**/*.ts` triggers TypeScript rules). No capture — entirely manual authoring. No retrieval — always injected when glob matches. No versioning or tagging.

**Claude Code (CLAUDE.md hierarchy):** Three tiers: `~/.claude/CLAUDE.md` (global) → `./CLAUDE.md` (project) → subdirectory CLAUDE.md. Always injected at session start. No capture, no search, no structured types. The baseline that brain must surpass.

**Continue.dev rules:** Markdown files in `.continue/rules/`. Glob-triggered (similar to Cursor). Session-based memory only — memory tools available but not built-in persistence. No cross-project capability.

**Letta (MemGPT):** Tiered memory hierarchy — in-context core memory (RAM analogue) + archival/recall (disk analogue). Agent manages its own memory movement. Stateful agent model with Agent File (.af) format. Complex infrastructure, not a developer knowledge tool per se.

**Key insight from survey:** No existing tool combines (1) structured knowledge types, (2) local-first with embeddings, (3) cross-project scope, (4) hybrid capture (auto + manual), and (5) hybrid retrieval (injection + on-demand). This is the gap brain fills.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the tool is broken without. Maps to which knowledge type(s) each applies to.

| Feature | Why Expected | Knowledge Types | Complexity | Notes |
|---------|--------------|-----------------|------------|-------|
| `brain_capture` tool — save a knowledge entry | Without explicit save, nothing gets in. Manual path is minimum viable | Rules, Snippets, Decisions, Bugs | LOW | Must accept: content, type, optional tags, optional project scope |
| `brain_search` tool — semantic search by query | Primary way AI retrieves relevant knowledge on-demand. All competitors have this | Rules, Snippets, Decisions, Bugs | MEDIUM | Vector similarity via fastembed/nomic-embed-text. Returns ranked results |
| `brain_list` tool — list entries with filters | Audit and discover what's stored. Without this the store is a black box | All types | LOW | Filter by type, scope, tags. Pagination for large stores |
| `brain_delete` tool — remove an entry by ID | Stale/wrong knowledge is worse than no knowledge. Users must be able to curate | All types | LOW | Hard delete. Consider soft-delete for recovery window |
| `brain_update` tool — edit existing entry | Rules evolve. "Don't use `any`" may later be "use `any` sparingly" | Rules, Decisions | LOW | Update content + re-embed. Preserve original created_at, update updated_at |
| Global scope — entries available across all projects | Directly addresses #1 pain (stop repeating rules). Without cross-project, brain is just another per-project rules file | Rules (primary), Snippets, Decisions | LOW | Default scope for rules. stored without project binding |
| Project scope — entries tied to a specific project | Users have project-specific conventions. Must isolate context correctly | All types | LOW | Scoped by project identifier (path or name). Retrieved only in that project's sessions |
| Session context injection at startup | Rules must reach AI without the user having to ask. The CLAUDE.md baseline behavior. Without this the #1 pain is unsolved | Rules (primary) | MEDIUM | MCP server exposes a `brain://rules` Resource (or prompt) read at session start. Injects global + current-project rules |
| 4 structured knowledge types (rules, snippets, decisions, bugs) | Each type has different retrieval pattern and lifecycle. A generic "bag of text" loses semantic structure | Rules, Snippets, Decisions, Bugs | LOW | `type` field on every entry. Filters in list/search. Drives retrieval scoring |
| Local-first storage (SQLite + local vector index) | Privacy non-negotiable for personal dev tool. Zero cost. Offline-capable | All types | MEDIUM | SQLite for metadata; embedded vector index (usearch/hnswlib/faiss-cpu). No external APIs |
| Local embeddings without Ollama dependency | "Works on any machine after install" is a hard constraint. Ollama being down can't block captures | All types | MEDIUM | fastembed with nomic-embed-text (~270MB download on first run). Model bundled in process |

### Differentiators (Competitive Advantage)

Features that distinguish brain from "just another rules file" or "just another memory tool."

| Feature | Value Proposition | Knowledge Types | Complexity | Notes |
|---------|-------------------|-----------------|------------|-------|
| Claude Code Stop hook auto-capture | AI itself extracts lessons at session end without user lifting a finger. Catches things user forgets to save manually | Bugs (primary), Decisions, Snippets | MEDIUM | Hook calls `brain-extract` script → Claude summarizes session transcript → saves structured entries. Inspired by claude-memory-compiler pattern |
| Hybrid retrieval: injection + on-demand | Rules injected at session start (zero-friction for #1 pain). Other types retrieved by AI when it decides it needs them. Best of both worlds. No competitor does both | Rules (injection), Snippets/Decisions/Bugs (on-demand) | MEDIUM | MCP Resource for session injection of rules. `brain_search` tool for AI-driven on-demand retrieval |
| Type-aware retrieval scoring | A bug lesson retrieved for "implement auth" is noise. Rules are always relevant. Decisions are relevant when touching the same domain. Types should influence ranking | All types | MEDIUM | Retrieval filters by type when appropriate. Rules get boosted in initial injection. Bugs/snippets prefer semantic similarity |
| Tagging with multi-tag support | Organizes knowledge without forcing strict hierarchies. "python", "async", "error-handling" on one entry. Cursor rules do glob activation — brain does tag activation | All types | LOW | Tags as array. Filter by one or more tags in search/list. No forced taxonomy — user defines |
| Scope filtering in search | "Show me only rules that apply to this project" without manual tracking. Competitors either scope everything (Copilot Memory) or scope nothing (CLAUDE.md global) | All types | LOW | `scope` param in `brain_search`: global, project-specific, or both (default) |
| Source attribution (which project/session produced this) | Knowing *where* a rule came from matters. If the `django-api` project produced a convention, you can trace it | All types | LOW | `source_project`, `source_session_id`, `created_at` fields stored on every entry |
| `brain_get` — fetch single entry by ID | Source attribution + manual review workflows. User inspects an entry before updating or deleting | All types | LOW | By ID. Returns full entry with metadata |
| Explicit contradiction flag on capture | When saving a rule that contradicts an existing one, surface the conflict rather than silently accumulating contradictions. Memory systems that just append lead to 62% wrong memories (per research) | Rules (primary), Decisions | HIGH | On `brain_capture`, embed and search for similar existing entries. If semantic similarity > threshold AND content conflicts, return conflict warning before saving |
| MCP Prompt primitive for rules injection | MCP Prompt (not just Tool) lets clients inject rules via the standard MCP prompt-fetching mechanism. Cleaner than tool-call-at-startup | Rules | MEDIUM | Expose `brain://rules/inject` as MCP Prompt that returns current global + project rules formatted for context injection |

### Anti-Features (Deliberately NOT Built)

Features that seem useful but actively hurt this use case. Informed by PROJECT.md out-of-scope + competitor failures observed in research.

| Anti-Feature | Why Requested | Why Problematic | What to Do Instead |
|--------------|---------------|-----------------|--------------------|
| Automatic full-conversation capture (every message saved) | "More data = more useful" intuition | Context bloat: 62% of auto-captured memories are wrong or irrelevant (research finding). claude-mem captures everything and becomes noise. Semantic search degrades as low-quality entries proliferate | Selective capture only: auto-capture at session END via Stop hook (distilled, not raw), plus explicit manual saves. Curation is the feature |
| Session history / conversation replay | "I want to find what I said last Tuesday" | Brain's purpose is actionable patterns, not episodic memory. SESSION HISTORY IS EXPLICITLY OUT OF SCOPE (PROJECT.md). Grows unboundedly. Conflicts with local-first size constraints | Use claude-mem if you want session replay. Brain stores only extracted, curated knowledge |
| Cloud sync in v1 | "Access from multiple machines" | Adds auth, conflict resolution, network dependency, privacy concerns. Invalidates zero-cost and offline-capable constraints. Complexity spike before value is validated | Schema designed for future sync (sync_id, updated_at fields). Implementation deferred post-v1 validation |
| Multi-user / team sharing | "Share team rules" | Completely different threat model, permission system, and conflict resolution. Multi-user is explicitly out of scope | v1 is strictly personal. Team use = separate product design |
| Web UI / dashboard | "I want to browse my knowledge" | Adds frontend build pipeline, JS dependency, port management. `brain_list` + `brain_search` via any MCP client is sufficient for v1 | CLI output from `brain_list` is sufficient. GUI is post-v1 if usage proves need |
| Cloud embeddings (OpenAI/Voyage) as default | "Better quality vectors" | External API dependency. Cost per entry. Privacy: code snippets sent to third party. Breaks offline-capable requirement | Local nomic-embed-text is proven excellent quality for code+text at personal scale. Cloud embeddings optional later |
| Time-based memory expiration (like Copilot's 28-day TTL) | "Stale memories auto-clean" | Rules don't expire. "Use TypeScript strict" is still true next year. Expiry makes sense for auto-captured memories tied to a specific codebase state, not for curated user rules | Manual delete for rules. Optional staleness metadata field. User curates; tool doesn't auto-delete |
| Automatic deduplication without user confirmation | "No duplicate rules" | Semantic similarity is not semantic equivalence. Auto-merging "use async/await" and "never use callbacks" could silently destroy important distinction | Surface duplicates as warnings on capture. Let user decide. Never merge silently |
| Generic knowledge base (notes, meetings, research) | "One brain to rule them all" | Dilutes retrieval relevance. Non-code entries pollute semantic search for code queries. Explicitly out of scope (PROJECT.md: "not Notion/Obsidian") | Strict content focus: code and development only. Each entry must be actionable for coding |
| GSD workflow integration | "My planning tool and my brain should be connected" | GSD is project workflow, brain is cross-project knowledge. Coupling them would bind brain to one tool and prevent it working in projects that don't use GSD | Keep independent. Both are MCP servers; Claude connects both when needed |

---

## Feature Dependencies

```
[session_context_injection]
    └──requires──> [global_scope]
    └──requires──> [brain_capture (rules)]
    └──requires──> [MCP Resource or Prompt primitive]

[brain_search (on-demand)]
    └──requires──> [local_embeddings]
    └──requires──> [vector_index]

[local_embeddings]
    └──requires──> [fastembed + nomic-embed-text]
    └──blocks──> [cloud_embeddings_option (post-v1)]

[auto_capture via Stop hook]
    └──requires──> [brain_capture tool]
    └──requires──> [Claude Code hooks mechanism]
    └──enhances──> [bugs knowledge type]
    └──enhances──> [decisions knowledge type]

[contradiction_flag]
    └──requires──> [brain_search] (to find similar existing entries)
    └──requires──> [local_embeddings]
    └──enhances──> [brain_capture] (pre-save check)

[project_scope]
    └──requires──> [global_scope] (project scope is additive)
    └──enhances──> [session_context_injection] (injects global + project rules)

[tagging]
    └──enhances──> [brain_list] (filter by tag)
    └──enhances──> [brain_search] (tag filter)

[brain_update] ──conflicts──> [auto_deduplication]
    (user controls updates; system must not silently merge)
```

### Dependency Notes

- **session_context_injection requires brain_capture (rules):** Without at least some saved rules, injection returns nothing and the #1 pain isn't addressed. Rules must be captured first — either by user or via import from existing CLAUDE.md.
- **auto_capture requires brain_capture tool:** The Stop hook is a wrapper that calls `brain_capture` internally. The tool must exist before the hook can work.
- **contradiction_flag requires brain_search:** The pre-save duplicate/conflict check is a semantic search against existing entries. Vector index must be built and queryable.
- **project_scope enhances session_context_injection:** At session start, injection merges global rules + rules scoped to the current project. The project identifier is derived from working directory or passed by the MCP client.

---

## MVP Definition

### Launch With (v1)

Minimum viable to solve the #1 pain (stop repeating rules) and the three secondary pains.

- [ ] `brain_capture` tool — explicit save with type, content, tags, scope — **solves primary capture path**
- [ ] `brain_search` tool — semantic search via local embeddings — **solves on-demand retrieval**
- [ ] `brain_list` tool — list with type/scope/tag filters — **solves discoverability/audit**
- [ ] `brain_delete` tool — remove entry by ID — **solves knowledge decay problem**
- [ ] `brain_update` tool — edit content of existing entry — **rules evolve; update must exist**
- [ ] Global scope + project scope — **cross-project is the core differentiator**
- [ ] 4 knowledge types as structured field — **prevents "bag of text" degradation**
- [ ] Session context injection of global rules via MCP Resource/Prompt — **directly solves #1 pain (repeating rules)**
- [ ] Local SQLite + embedded vector index (usearch or faiss-cpu) — **local-first constraint**
- [ ] Local fastembed with nomic-embed-text — **no external dependency constraint**
- [ ] Tagging (multi-tag per entry) — **organizes without forcing taxonomy**
- [ ] Source attribution fields (source_project, created_at, updated_at) — **traceability; needed for v1.x features**

### Add After Validation (v1.x)

Add when v1 is in daily use and these pains surface concretely.

- [ ] Claude Code Stop hook auto-capture — trigger: user reports "I forget to save lessons from sessions"
- [ ] Contradiction/duplicate warning on capture — trigger: user finds conflicting rules in their store after a few weeks
- [ ] `brain_get` tool (single entry by ID) — trigger: user wants to inspect/edit specific entry found in list
- [ ] Import from existing CLAUDE.md — trigger: users want to migrate existing rules without manual re-entry
- [ ] MCP Prompt primitive for rules injection (alongside Resource) — trigger: client compatibility issues with Resource-only approach

### Future Consideration (v2+)

Defer until personal usage validates the direction.

- [ ] Cloud sync (multi-machine) — defer: adds auth/conflict complexity before value is proven
- [ ] Cloud embeddings as optional backend — defer: local quality is sufficient at personal scale
- [ ] Team sharing / multi-user — defer: different product; different threat model
- [ ] Web UI for browsing knowledge — defer: CLI sufficient for developer user
- [ ] Knowledge confidence scoring / freshness decay — defer: at hundreds of entries this matters; at launch it's over-engineering

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `brain_capture` tool | HIGH | LOW | P1 |
| Session context injection (rules) | HIGH | MEDIUM | P1 |
| `brain_search` tool | HIGH | MEDIUM | P1 |
| Global + project scope | HIGH | LOW | P1 |
| Local SQLite storage | HIGH | LOW | P1 |
| Local embeddings (fastembed) | HIGH | MEDIUM | P1 |
| 4 structured knowledge types | HIGH | LOW | P1 |
| `brain_list` tool | MEDIUM | LOW | P1 |
| `brain_delete` tool | MEDIUM | LOW | P1 |
| `brain_update` tool | MEDIUM | LOW | P1 |
| Tagging | MEDIUM | LOW | P1 |
| Source attribution | MEDIUM | LOW | P1 |
| Auto-capture via Stop hook | HIGH | MEDIUM | P2 |
| Contradiction warning on capture | HIGH | HIGH | P2 |
| `brain_get` by ID | LOW | LOW | P2 |
| Import from CLAUDE.md | MEDIUM | LOW | P2 |
| MCP Prompt primitive | MEDIUM | MEDIUM | P2 |
| Cloud sync | MEDIUM | HIGH | P3 |
| Knowledge freshness/decay | LOW | HIGH | P3 |
| Web UI | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | mem0 MCP | Copilot Memory | claude-mem | Cursor Rules | Claude CLAUDE.md | brain (planned) |
|---------|----------|----------------|------------|--------------|------------------|-----------------|
| Cross-project scope | YES (user-scoped) | NO (repo-locked) | NO (per-session) | NO (per-project) | PARTIAL (global CLAUDE.md) | YES |
| Structured knowledge types | NO (generic memories) | PARTIAL (auto-detected) | NO | NO | NO | YES (4 types) |
| Semantic search | YES (cloud) | NO (validation only) | YES (FTS5 + limited vector) | NO | NO | YES (local) |
| Local-first / no cloud dependency | NO | NO | YES | YES (files) | YES (files) | YES |
| Session context injection | NO | YES (auto) | YES (last 10 sessions) | YES (glob-triggered) | YES (always) | YES (rules only) |
| On-demand tool-call retrieval | YES | NO | YES | NO | NO | YES |
| Explicit manual capture | YES | NO (auto-only) | NO | YES (file editing) | YES (file editing) | YES |
| Auto-capture via hooks | NO | YES | YES (all observations) | NO | NO | YES (Stop hook, distilled) |
| Tagging / filtering | YES | NO | NO | YES (glob) | NO | YES |
| Contradiction detection | NO | NO | NO | NO | NO | YES (v1.x) |
| Privacy (no data leaves machine) | NO (cloud API) | NO (GitHub cloud) | YES | YES | YES | YES |
| Works across Claude Code + Desktop + Cursor | YES | NO (GitHub only) | YES | NO | PARTIAL | YES (standard MCP) |

---

## Sources

- mem0 MCP tools: https://github.com/mem0ai/mem0-mcp
- mem0 MCP docs: https://docs.mem0.ai/platform/mem0-mcp
- Claude memory tool (Anthropic): https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- Copilot Memory: https://docs.github.com/en/copilot/concepts/agents/copilot-memory
- Copilot Memory release: https://github.blog/changelog/2026-03-04-copilot-memory-now-on-by-default-for-pro-and-pro-plus-users-in-public-preview/
- claude-memory-compiler: https://github.com/coleam00/claude-memory-compiler
- claude-mem: https://docs.claude-mem.ai/introduction
- Continue.dev rules: https://docs.continue.dev/customize/deep-dives/rules
- Cursor rules guide: https://federicocalo.dev/en/blog/cursor-rules-configure-ai-project-standards
- Letta/MemGPT agent memory: https://www.letta.com/blog/agent-memory
- AI memory crisis (62% wrong memories): https://medium.com/@mohantaastha/the-ai-memory-crisis-why-62-of-your-ai-agents-memories-are-wrong-792d015b71a4
- MCP Resources vs Tools: https://medium.com/@laurentkubaski/mcp-resources-explained-and-how-they-differ-from-mcp-tools-096f9d15f767
- MCP memory servers ecosystem: https://glama.ai/mcp/servers/categories/knowledge-and-memory
- State of AI Agent Memory 2026: https://mem0.ai/blog/state-of-ai-agent-memory-2026
- RAG update strategies: https://particula.tech/blog/update-rag-knowledge-without-rebuilding

---

*Feature research for: personal MCP brain server — cross-project AI knowledge persistence*
*Researched: 2026-04-14*

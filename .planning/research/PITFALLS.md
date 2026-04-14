# Pitfalls Research

**Domain:** Personal MCP brain server — local RAG over code/rules/decisions/snippets
**Researched:** 2026-04-14
**Confidence:** HIGH (cross-verified across multiple sources; most are structural/architectural, not framework-specific)

---

## Critical Pitfalls

### Pitfall 1: Mid-Function Chunking — Code RAG's Original Sin

**What goes wrong:**
Fixed-size token splitting cuts functions in half, separates docstrings from implementations, and severs the docstring-to-body connection. A chunk containing the top half of a 60-line function is semantically useless — neither the signature alone nor the body alone retrieves correctly, and the LLM receives incomplete code that it cannot use.

**Why it happens:**
Developers copy chunking patterns from text/document RAG tutorials and apply them directly to code. Fixed-size splitting is the default in most RAG libraries (LangChain's `RecursiveCharacterTextSplitter`, etc.) and works adequately for prose but catastrophically for code.

**How to avoid:**
Use AST-aware chunking from day one. Parse code files with tree-sitter or Python's `ast` module before chunking. The unit of a code chunk is: one function/method + its docstring + its immediate class context (if a method). Never split on raw character count for code. For rule/decision documents, split on semantic sections (headers, bullet groups) not character count.

**Warning signs:**
- Retrieval returns a function signature but the body is missing
- Retrieved snippet references a variable defined outside the chunk
- Queries for "how does X work" return fragments that don't answer the question
- Embeddings of obviously related code score low similarity

**Phase to address:** Phase 1 (core RAG pipeline) — chunking strategy is foundational; changing it later requires full re-embedding of all existing knowledge.

---

### Pitfall 2: General Embedding Model for Code — Wrong Tool, Wrong Domain

**What goes wrong:**
Using a general-purpose embedding model (e.g., `all-MiniLM-L6-v2`, `text-embedding-3-small`) for code snippets causes semantic similarity to be computed on surface-level text patterns rather than code structure, variable dependencies, or control flow. Two snippets that do the same thing with different variable names score low similarity. A natural language query "retry with backoff" may fail to retrieve the relevant function named `_retry_request`.

**Why it happens:**
General models are the easiest to reach for. They're on Hugging Face, they're in tutorial code, and they work for the other knowledge types (rules, decisions, notes). Developers use one model for everything without benchmarking code-specific retrieval.

**How to avoid:**
Use a code-tuned model for code snippets: `nomic-ai/nomic-embed-code` (local, strong on CoIR benchmark, rivals closed-source models) or `Qodo-Embed-1` (smaller footprint, SOTA on CoIR). Use a general model (`nomic-embed-text`, `BAAI/bge-small-en-v1.5`) for rules, decisions, and notes. This means two embedding models in the system — manage this explicitly. Store which model produced each vector as metadata on every row.

**Warning signs:**
- Code snippet queries return rules/notes but not the relevant function
- Similarity scores for obviously identical logic patterns are unexpectedly low
- Users report "it never finds the snippet I'm looking for"

**Phase to address:** Phase 1 (embedding layer) — embedding model choice is locked in with the stored vectors. Changing requires full re-embedding of all code-type knowledge.

---

### Pitfall 3: Missing Metadata — Recall Silently Degrades

**What goes wrong:**
Without rich metadata on each stored chunk, retrieval cannot filter by project, knowledge type, recency, or source. Every query searches globally. A React rule retrieved for a Python project. A decision from a deprecated project surfaces as the most relevant. A snippet from 2 years ago outranks one saved yesterday.

**Why it happens:**
Metadata feels like overhead during MVP. The embedding + similarity search feels like the whole pipeline. But without structured filtering on top of vector similarity, precision collapses as knowledge grows.

**How to avoid:**
Enforce a metadata schema on every stored item at write time. Minimum required fields: `project_id` (or `global`), `knowledge_type` (rule/snippet/decision/note), `created_at`, `updated_at`, `source_file` (if captured from code), `language` (for snippets), `embedding_model_id` (for migration safety), `is_deprecated` (boolean), `confidence` (float, if applicable). All retrievals should support metadata pre-filtering before vector search — this is faster and more precise.

**Warning signs:**
- No way to ask "show me all rules for project X"
- Cannot purge or audit knowledge by project
- Adding a new project causes old, unrelated results to pollute queries

**Phase to address:** Phase 1 (schema design) — metadata schema is the hardest thing to migrate retroactively. Get it right before any knowledge is stored.

---

### Pitfall 4: Semantic-Only Retrieval for Code Identifiers

**What goes wrong:**
Exact identifiers — function names, class names, error codes, API endpoint paths, environment variable names — are poorly retrieved by semantic/vector search alone. Searching for `DATABASE_URL` or `handle_payment_webhook` as a concept returns semantically similar topics but may miss the exact chunk that uses that identifier. The brain becomes useless for "where did I define X?" queries.

**Why it happens:**
RAG tutorials focus on semantic search because it's the novel part. BM25/keyword search is treated as legacy. Developers ship vector-only retrieval.

**How to avoid:**
Implement hybrid retrieval from the start: parallel BM25 (full-text) + vector search, merged with Reciprocal Rank Fusion (RRF). sqlite-vec handles vector search; FTS5 (SQLite's built-in full-text search) handles BM25 — both are in the same database file. No extra infrastructure needed. Weight the merge: for queries that look like identifiers (contain underscores, camelCase, dots), increase BM25 weight. For natural language queries, increase vector weight.

**Warning signs:**
- Can't find a snippet by its function name
- Searching for an exact string returns nothing despite the string being stored
- Users must remember to use exact wording to find things

**Phase to address:** Phase 1 (retrieval layer) — easier to add at foundation than to retrofit; FTS5 needs to be enabled when tables are created.

---

### Pitfall 5: Tool Descriptions That Claude Never Calls

**What goes wrong:**
MCP tools with vague or generic descriptions get ignored. Claude reads tool descriptions to decide which tool to invoke. If `search_knowledge` has description "Search the brain for information" and `query_brain` has description "Query stored knowledge," Claude has no signal for when to use either vs. just reasoning from its own training data. Result: the brain exists but is never consulted.

**Why it happens:**
A 2025 ecosystem analysis found that 97.1% of MCP tool descriptions have at least one quality issue and over half have unclear purpose statements. Developers write descriptions for humans reading docs, not for an LLM deciding which tool to call.

**How to avoid:**
Write descriptions as decision criteria, not feature summaries. Include: what triggers this tool (specific situations), what it returns, and what it does NOT cover. Example: "Retrieve project-specific coding rules, architectural decisions, and code snippets from the brain. Call this before writing code for a project, when asked about conventions, or when uncertain about project-specific patterns. Returns ranked results with confidence scores. Does NOT contain general programming knowledge." Keep descriptions under 200 words. Test by prompting Claude with realistic queries and checking whether it calls the right tool.

**Warning signs:**
- Claude reasons through answers without calling any brain tools
- Claude calls a brain tool on every query regardless of relevance
- Claude picks the wrong tool for the knowledge type (calls snippet tool for rules)

**Phase to address:** Phase 1 (MCP tool layer) — and revisit in every subsequent phase as tools are added.

---

### Pitfall 6: Tool Schema Overhead Consuming Context Budget

**What goes wrong:**
Each connected MCP server injects its tool schemas into every message before Claude processes the actual prompt. A brain server with 8+ tools can consume 2,000–5,000 tokens of overhead per turn before any retrieval happens. With multiple MCP servers connected simultaneously, total overhead reaches 10,000–18,000 tokens per message — this is constant, unavoidable tax on every Claude interaction, not just brain queries.

**Why it happens:**
MCP spec requires tool schemas in every request. Developers add tools generously during development without accounting for per-turn token cost.

**How to avoid:**
Keep tool count to the minimum viable set — prefer fewer, well-scoped tools over many specialized ones. Aim for 4–6 tools maximum. Combine related operations (e.g., one search tool with a `knowledge_type` parameter rather than four separate search tools). Keep tool schemas lean: no optional parameters with elaborate descriptions, no examples embedded in the schema JSON. Return concise responses — prefer a summary + offer to expand rather than dumping full content. Set `anthropic/maxResultSizeChars` annotation on all tools.

**Warning signs:**
- Context exhaustion on complex tasks with multiple tools connected
- Claude truncates responses or loses early conversation context
- Tool schemas alone exceed 5,000 tokens (measure this explicitly)

**Phase to address:** Phase 1 (tool design) — the tool count/schema architecture is difficult to change without breaking existing integrations.

---

### Pitfall 7: Noisy Auto-Capture — Saving Everything Saves Nothing

**What goes wrong:**
Auto-capture hooks (post-commit, file-save, shell history) capture everything without quality gates. After a week of use, the brain contains: every WIP commit message ("fix tests again"), every temporary debugging snippet, every half-formed note. Retrieval quality collapses because high-signal knowledge drowns in noise. The brain becomes a trash heap that happens to be searchable.

**Why it happens:**
Auto-capture feels like automation nirvana. High capture rate looks like success. The failure mode is invisible until retrieval quality degrades, which takes days or weeks to notice.

**How to avoid:**
Apply a capture quality filter before storage. Minimum viable filter: (1) minimum content length (reject under 50 characters), (2) commit message pattern filter (reject "fix", "wip", "temp", "test"), (3) file-extension allowlist for code capture (only capture from known source file types), (4) explicit deduplication check (compare new content against recent stored items). For manual capture, prefer explicit tagging over background scanning. Implement a "capture confidence" score and surface low-confidence captures for human review rather than silently storing them. Build the review queue in Phase 2 even if auto-capture comes later.

**Warning signs:**
- Storage grows faster than the user's actual knowledge creation rate
- "Retrieve X" returns multiple near-duplicate results from different days
- Users report results feel noisy or irrelevant after a few weeks of use

**Phase to address:** Phase 2 (capture pipeline) — quality gates must be designed before any auto-capture is enabled.

---

### Pitfall 8: Credentials and Secrets Leaking Into the Brain

**What goes wrong:**
Auto-capture from shell history, `.env` files, commit diffs, or config files inadvertently stores API keys, passwords, tokens, and machine-local paths into the brain's SQLite database. These then surface in retrieval results and get injected into Claude's context window. AI service secrets leaks grew 81% year over year in 2025; RAG ingestion pipelines are identified as a primary vector.

**Why it happens:**
Capture hooks run on file changes or git events without inspecting content. A developer stores a "snippet" of a `.env` file setup. A shell command with an embedded token gets captured as a "how-to." The brain does not know what it's storing.

**How to avoid:**
Implement a secret scanner on every capture path before write. Use `detect-secrets` (Python library, maintained by Yelp) as a pre-storage filter — it detects API keys, tokens, passwords, connection strings with high recall. Any item that triggers a secret detection hit is rejected with a logged warning. Additionally: never auto-capture from `.env`, `.envrc`, `*.pem`, `*.key`, `*secret*`, `*credential*` file patterns. Never store shell commands that contain `=` adjacent to uppercase strings (common pattern for env var assignment with value). Sanitize stored paths: replace `$HOME` and absolute paths with placeholders before storage.

**Warning signs:**
- Brain contains items with `sk-`, `ghp_`, `AKIA`, or other common key prefixes
- Captured snippets contain file paths like `/home/username/`
- Users discover that a retrieval result contains an actual password

**Phase to address:** Phase 2 (capture pipeline) — the scanner must be in place before any auto-capture functionality is enabled. Non-negotiable gate.

---

### Pitfall 9: Stale Knowledge Outranking Fresh — No Recency Signal

**What goes wrong:**
Pure vector similarity has no concept of time. A decision made in 2023 that was superseded in 2024 retrieves with the same or higher score than the current decision, because it was written with more detail. The brain confidently returns outdated guidance. An LLM that follows it produces code or decisions that violate current project standards.

**Why it happens:**
Vector similarity is the only ranking signal implemented. Recency weighting requires score post-processing that feels like unnecessary complexity during early development.

**How to avoid:**
Apply a recency decay function to all retrieval scores before ranking: `final_score = similarity_score * time_decay(age_days, half_life=180)`. Use a configurable half-life (180 days is reasonable for project rules; longer for architectural decisions). Store `created_at` and `updated_at` on every item. Provide an explicit "superseded_by" field that creates a hard link between old and new versions — retrieval filters on `is_deprecated=False` first, then applies recency decay to the survivors. Surface the creation date in all retrieval results so Claude can reason about freshness.

**Warning signs:**
- Two conflicting rules both appear in retrieval results for the same query
- Users discover the brain gave guidance based on a decision that was reversed
- Newest knowledge items consistently score lower than older, more verbose items

**Phase to address:** Phase 2 (retrieval scoring) — recency weighting can be added without schema migration if `created_at` was stored from Phase 1.

---

### Pitfall 10: Contradicting Knowledge With No Resolution Path

**What goes wrong:**
Two stored rules conflict. "Always use async/await for database calls" stored in January. "Use synchronous DB calls in background tasks to avoid event loop issues" stored in March. Both retrieve at high similarity for database-related queries. Claude receives both and either hedges ("some guidelines suggest X, others Y") or silently picks one. The user has no idea the brain contains a contradiction.

**Why it happens:**
Knowledge is only ever written in, never curated. The brain has no concept of conflict detection. RAG retrieval is designed to return relevant items, not to surface inconsistencies.

**How to avoid:**
On every write, run a similarity search against existing stored items of the same type and project scope. If a new item scores above a conflict threshold (e.g., cosine similarity > 0.85) against an existing item but has different semantic content, flag it as a potential conflict and require resolution before storage. Implement a `supersedes` field: when a new rule is added that updates an existing one, explicitly mark the old one `is_deprecated=True`. Build a "conflicts review" command as an MCP tool so Claude can surface contradictions on demand. Store contradictions as a first-class state, not an error condition.

**Warning signs:**
- Multiple rules for the same topic return in a single retrieval
- LLM output contradicts itself across different sessions for the same project
- Users discover the brain "changed its mind" without them having changed anything

**Phase to address:** Phase 3 (knowledge management) — conflict detection can be added after the core pipeline exists, but the data model (`supersedes`, `is_deprecated`) must be planned in Phase 1.

---

### Pitfall 11: SQLite Lock Contention From Multiple Claude Sessions

**What goes wrong:**
Multiple simultaneous Claude Code sessions (e.g., two terminal windows, a background task, and a foreground conversation) all write to the same SQLite brain database. SQLite's default locking is database-level and write-serializing. Concurrent writes produce `SQLITE_BUSY` errors. These surface as MCP tool failures, which Claude silently swallows or retries, resulting in knowledge that was never actually stored.

**Why it happens:**
Personal tools "feel like" they'll only have one user at a time. In practice, modern AI-assisted development involves many concurrent sessions. SQLite's single-writer constraint is a well-documented but frequently ignored limitation.

**How to avoid:**
Enable WAL mode (Write-Ahead Log) at database creation: `PRAGMA journal_mode=WAL`. This allows concurrent reads alongside a single write, which handles the common case (many reads, occasional writes). Set a generous busy timeout: `PRAGMA busy_timeout=5000` (5 seconds). For writes, implement a retry loop with exponential backoff rather than failing immediately. Keep write transactions short — do not hold a write transaction open during embedding computation (compute embedding, then open transaction, write, close). Consider a write queue: a single background writer process that accepts write requests via a Unix domain socket, serializing all writes through one process.

**Warning signs:**
- Occasional MCP tool errors that resolve on retry
- Missing knowledge that the user is certain they saved
- Database file grows a `.wal` file that never gets checkpointed (stale WAL)

**Phase to address:** Phase 1 (database layer) — WAL mode must be set at database creation. Retroactively enabling it on an existing database is possible but requires caution.

---

### Pitfall 12: Embedding Model Loaded on Every Tool Call

**What goes wrong:**
The embedding model (even a small one like `nomic-embed-text` at ~274MB) is loaded from disk into memory on every MCP tool invocation if the server is implemented naively as a stateless subprocess. At personal scale with frequent queries, this adds 1–3 seconds of cold-start latency to every retrieval and repeatedly spikes RAM.

**Why it happens:**
Simple MCP server implementations are stateless scripts that run, respond, and exit. Embedding is done inline. This pattern works but wastes model load time on every call.

**How to avoid:**
Run the MCP server as a long-lived process (the MCP stdio transport inherently keeps the process alive during a Claude session). Load the embedding model once at server startup and keep it in memory for the session lifetime. Use a model server if multiple sessions need embeddings: `ollama` serves embedding models over HTTP and handles the keep-alive, queuing, and memory management. For the embedding model, prefer smaller models that fit in RAM without GPU: `nomic-embed-text` (274MB), `BAAI/bge-small-en-v1.5` (134MB), `e5-small-v2` (134MB). For code: `nomic-embed-code` (~550MB). These are manageable even on machines with 8GB RAM.

**Warning signs:**
- Retrieval takes 2+ seconds when the model should be fast
- RAM spikes on every tool call instead of staying flat
- System memory pressure during heavy coding sessions

**Phase to address:** Phase 1 (server architecture) — the process model decision affects the entire server design.

---

### Pitfall 13: Vector Index Corruption on Embedding Model Change

**What goes wrong:**
When the embedding model is changed (to a better one, or because the original was deprecated), all existing stored vectors become meaningless — they live in a different embedding space with potentially different dimensions. Searches against the mixed index return wrong results with high confidence scores, because the query vector is in model-B's space while stored vectors are in model-A's space. The brain appears to work but returns garbage.

**Why it happens:**
The model upgrade feels like a drop-in replacement. The developer changes the model, re-embeds new items, but doesn't re-embed existing ones. The database now contains a mix of embedding spaces. Dimension mismatches (e.g., 768 vs. 1536) will at least error visibly — but same-dimension models with different training are the silent failure.

**How to avoid:**
Store the `embedding_model_id` as a non-nullable column on every stored vector. On query, assert that the query embedding model matches the stored vectors' model. Implement a migration tool that re-embeds all vectors when the model changes — this is a known cost. Design the schema to support versioning: a `model_version` table tracks which model is "current" and all vectors link to it. Treat a model upgrade as a migration event, not a configuration change. Use lazy re-embedding as a fallback: query with new model, fall back to items embedded with old model only if the new model's index has no results.

**Warning signs:**
- Retrieval results suddenly become irrelevant after a config change
- Dimension mismatch errors appear in logs (the visible failure)
- Similarity scores cluster around unexpected values (0.2 instead of 0.7+)

**Phase to address:** Phase 1 (schema) — `embedding_model_id` column must exist from the first migration. Phase 3 (tooling) — build the re-embedding migration utility.

---

### Pitfall 14: Knowledge Drift — The Brain Decays While You're Not Looking

**What goes wrong:**
Decisions, rules, and snippets stored in the brain become wrong over time. A framework upgrades with a breaking API change. A project switches from REST to gRPC. A rule that was correct in 2024 now causes bugs in 2025. The brain has no decay, no expiry, no signal that knowledge is old. The longer the brain is used, the worse retrieval quality gets — not because the brain grows, but because the stale-to-fresh ratio increases.

**Why it happens:**
Knowledge is treated as write-once. There's no mechanism for the brain to ask "is this still true?" and no signal that something should be reviewed. Developers capture at time of learning and forget the item exists.

**How to avoid:**
Implement a staleness heuristic: flag any item that is over N days old (configurable per knowledge type: snippets may need review sooner than architectural decisions) and has not been accessed or updated. Provide a `brain review` command that surfaces potentially stale items for confirmation or archival. Use access tracking: `last_accessed_at` column, updated on every retrieval hit. Items that are never retrieved are either perfectly fresh or completely irrelevant — both warrant review. When a user explicitly updates a knowledge item, always set `updated_at` and consider creating a new version rather than mutating in place. Build an audit mode: `brain audit --project X` lists all knowledge, sorted by staleness.

**Warning signs:**
- Brain items reference library versions, APIs, or project structures that no longer exist
- Users regularly correct the brain's output because "that changed"
- Retrieval returns items with `created_at` from 12+ months ago for active projects

**Phase to address:** Phase 3 (knowledge lifecycle) — staleness tracking requires `last_accessed_at` and `access_count` fields planned in Phase 1 schema.

---

### Pitfall 15: Global Rules Leaking Into Wrong Project Context

**What goes wrong:**
Global rules (e.g., "always use conventional commits") correctly apply everywhere. But as global rules accumulate, project-specific queries retrieve them ahead of project-specific rules. A Django project query surfaces a React rule because both are stored globally. A project override ("this project uses tabs, not spaces") is overridden by a global rule ("always use spaces") because the global item has better semantic similarity.

**Why it happens:**
Scope is hard to implement correctly in a flat vector index. A naive retrieval searches across all items and returns the most similar, ignoring that scope should be a hard constraint, not a soft ranking signal.

**How to avoid:**
Scope is a hard filter, not a ranking input. Query execution order: (1) filter by scope: project-local items only, (2) if project-local results are sparse, expand to global, (3) never let global items outscore project-local items for project-specific queries. Implement scope priority: `project_local > project_default > global`. Add an `override_global` flag on project-local rules that suppresses any matching global rule from retrieval. All retrieval queries must accept a `project_id` parameter and apply it as a SQL WHERE clause before vector search. Never pass `project_id=None` as "search everything."

**Warning signs:**
- Project-specific queries return rules from other projects
- A project-level override appears to have no effect
- Users explicitly say "that's not how this project works" about retrieved rules

**Phase to address:** Phase 1 (schema + retrieval) — scope must be a first-class data model concept, not a filter added later.

---

### Pitfall 16: Capture Friction Kills the Tool

**What goes wrong:**
If saving knowledge to the brain requires more than one explicit action, developers stop doing it. A tool that requires the user to copy text, run a CLI command with five flags, and write a description gets used for two weeks and then abandoned. The brain stays empty. No knowledge means no value. No value means the tool is uninstalled.

**Why it happens:**
Builders optimize for features (what can be stored) over ergonomics (how hard it is to store). The primary user pain is invisible to the developer who built the tool — they know all the shortcuts.

**How to avoid:**
Design for zero-argument capture first. The gold standard: `brain save` with no arguments infers everything from context (current git repo = project, clipboard content = knowledge, content heuristics = knowledge type). Build the MCP capture tool so Claude can capture on behalf of the user mid-conversation ("I'll save that decision to your brain"). Provide a Claude Code hook that triggers after certain patterns ("save to brain? [y/N]") without breaking workflow. Measure time-to-save: if it takes more than 10 seconds from "I want to save this" to "it's saved," reduce that. Auto-capture with quality gates (Pitfall 7) is the long-term solution — but capture friction must be addressed in Phase 1.

**Warning signs:**
- User has been using the tool for a week and fewer than 10 items are stored
- All stored items were saved in the first 24 hours (novelty effect, then abandoned)
- User asks Claude to find things that "should be in the brain" but weren't saved

**Phase to address:** Phase 1 (MCP tool UX) — a single `capture` tool with smart defaults; revisit in Phase 2 (auto-capture).

---

### Pitfall 17: Returning Too Much Context — Window Poisoning

**What goes wrong:**
A brain retrieval returns 10 chunks averaging 500 tokens each = 5,000 tokens injected into the context window. Combined with tool schema overhead (2,000–5,000 tokens) and the actual conversation, Claude's effective reasoning window is severely constrained. Worse: irrelevant retrieved chunks actively confuse Claude. Research confirms that retrieval performance peaks and then declines as retrieved document count increases — too many chunks is worse than fewer, better-ranked ones.

**Why it happens:**
More results feels safer ("I won't miss anything"). Top-k is set to a generous number during development and never tuned. No reranking step is implemented.

**How to avoid:**
Default top-k to 3 for most queries, 5 maximum. Implement a reranking step after retrieval: retrieve 10 candidates, rerank with a cross-encoder or score combination, return top 3. Use `maxResultSizeChars` annotation on MCP tools to enforce return size at the protocol level. Return a summary + offer-to-expand pattern: "Found 3 relevant rules (showing top 2): [content]. 1 more available — ask to see it." Never return raw chunk text without metadata context (project, type, age) — this adds minimal tokens but allows Claude to reason about relevance.

**Warning signs:**
- Responses feel confused or self-contradictory after brain retrieval
- Claude ignores retrieved knowledge and reasons from training data instead
- Context usage hits limits on moderately complex tasks

**Phase to address:** Phase 1 (retrieval layer) — top-k and return size must be tuned from the first implementation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single embedding model for all knowledge types | Simpler infrastructure, one model to manage | Code retrieval quality is 20–40% worse; users stop trusting code lookups | Never — two models is minimal overhead for significant quality gain |
| No `embedding_model_id` on stored vectors | Simpler schema | Model upgrade requires wiping and re-embedding all knowledge | Never — add this column in the first migration |
| Fixed-size chunking for code | Works out of the box with standard libraries | Function splits destroy retrieval; requires full re-embed to fix | Never — use AST chunking from day one for code |
| Skip WAL mode on SQLite | No configuration | `SQLITE_BUSY` errors in multi-session use | Never — two lines of SQL at startup, no downside |
| No metadata pre-filtering (vector-only search) | Simpler retrieval code | Cannot scope by project; all queries search everything | MVP only if single-project, single-user, < 100 items |
| No recency decay in scoring | Simpler scoring | Stale knowledge outranks fresh knowledge | Never for production; acceptable for first-week testing |
| No secret scanner on capture | Faster capture implementation | Credentials end up in the brain | Never — use `detect-secrets` from day one |
| Top-k = 10 with no reranker | "Safe" coverage | Context window saturation; retrieval quality paradox | Never in production |
| In-process embedding on every call | Simpler code, no model server | 1–3s cold-start latency if process restarts | Only during local development/testing |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| sqlite-vec + FTS5 | Treating them as separate systems requiring separate queries | Use SQLite's ability to join vector results with FTS5 results in one query; run parallel and merge with RRF |
| MCP stdio transport | Restarting the server process on each tool call (e.g., using subprocess per call) | Keep the server as a long-lived process; stdio transport holds it open for the session |
| Ollama embedding endpoint | Making synchronous HTTP calls that block the MCP event loop | Use `asyncio` + `httpx` async client; never block the MCP server's event loop |
| Git post-commit hooks | Hook fires during rebase, merge commits, squash — capturing noise | Check `$GIT_REFLOG_ACTION` and skip if not a regular commit; check commit parent count |
| Claude Code MCP connection | Adding too many tools from multiple servers simultaneously | Each server's schemas add per-turn overhead; keep total cross-server tool count under 15 |
| detect-secrets scanner | Running it only on first capture, not on updates | Re-scan on every write, including updates to existing items |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N-nearest-neighbor full scan (no index) | Retrieval time grows linearly with item count | Use sqlite-vec's vector index (HNSW); it's on by default for KNN queries | ~500 items in a naive scan implementation |
| Re-embedding on every update | Save operations take 2–5 seconds | Only re-embed if content actually changed (hash check before embedding) | Every save in an auto-capture scenario |
| Loading full vectors into Python RAM for comparison | Memory spike on every retrieval | Let sqlite-vec do KNN in-process; never SELECT all vectors into Python | ~1,000 items |
| Synchronous disk writes holding the MCP response | Tool calls feel slow (500ms+) | WAL mode + async write with write-queue | First concurrent session |
| Chunking large files all at once | Memory spike on big file capture | Stream-chunk large files (> 1MB) in segments | Files > 1MB |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Auto-capturing `.env`, `*.key`, `*.pem` files | API keys, certificates, passwords stored in brain | Explicit file-extension blocklist before capture; never auto-capture dot-files |
| Storing absolute paths without sanitization | Machine-specific paths leak; knowledge not portable | Replace `$HOME` with `{HOME}` placeholder at store time; resolve at read time |
| No input validation on MCP tool arguments | Prompt injection via crafted tool inputs could modify stored knowledge | Validate all input lengths, types; reject inputs with unusual Unicode or control characters |
| SQLite database file world-readable | Other local processes can read all knowledge | Set file permissions to `0600` at creation (`chmod 600`) |
| Embedding API calls over cleartext HTTP | Knowledge content intercepted (if using remote embedding) | Use local embedding only — this is the correct architecture for a local-first tool |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Brain returns results without source context | User cannot verify where a rule came from | Always include `project`, `type`, `created_at`, `source_file` in every retrieval result |
| No way to delete or deprecate knowledge | Brain accumulates wrong/outdated items with no path to clean them | Implement `brain deprecate <id>` and `brain delete <id>` from Phase 1 |
| Retrieval fails silently with no results | Claude invents an answer instead of saying "nothing found" | Return an explicit "no results found for X in project Y" response; Claude can then ask the user |
| No distinction between "not found" and "found but low confidence" | User can't tell if the brain is ignorant or uncertain | Include a confidence score and result count in every response |
| Captured knowledge never surfaced unless explicitly queried | Knowledge accumulates but is never useful | Implement proactive surfacing: at session start, check for highly relevant recent items |

---

## "Looks Done But Isn't" Checklist

- [ ] **Chunking:** AST-based chunking implemented for code — verify by checking that no stored chunk cuts mid-function (run a validator that parses all stored code chunks)
- [ ] **Secret scanning:** `detect-secrets` running on every write path — verify by attempting to capture a fake API key and confirming rejection
- [ ] **WAL mode:** `PRAGMA journal_mode=WAL` confirmed active — verify with `PRAGMA journal_mode;` returning `wal`
- [ ] **Metadata completeness:** Every stored item has non-null `project_id`, `knowledge_type`, `created_at`, `embedding_model_id` — verify with `SELECT COUNT(*) FROM knowledge WHERE embedding_model_id IS NULL`
- [ ] **Scope isolation:** Queries for project A do not return items from project B — verify with a cross-project retrieval test
- [ ] **Recency decay:** Older items score lower than newer items with equal semantic relevance — verify with a synthetic test inserting identical content at different timestamps
- [ ] **Top-k enforced:** No retrieval path returns more than 5 items — verify by checking all retrieval code paths
- [ ] **Tool descriptions tested:** Claude actually calls the right tool for representative queries — verify manually with 10 test prompts

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong chunking strategy (need to fix mid-function splits) | HIGH | Re-chunk all stored code items; delete old vectors; re-embed; this requires full re-processing of all captured code knowledge |
| Wrong embedding model (mixed embedding spaces) | HIGH | Full re-embed of all items; if model dimensions differ, must drop and recreate vector index |
| Credentials in the brain | HIGH | Audit all stored items for secret patterns; delete matching items; rotate any exposed credentials immediately |
| SQLite corruption (missing WAL checkpoint) | MEDIUM | `PRAGMA wal_checkpoint(TRUNCATE);` to force checkpoint; if corrupt, restore from backup — always maintain a nightly copy |
| Knowledge contradiction accumulation | MEDIUM | Run conflict detection scan over all items; manually review and mark deprecated; consider `brain doctor` command |
| Context window saturation from tool overhead | LOW | Reduce tool count; lower top-k; add `maxResultSizeChars` annotations — no data migration required |
| Stale knowledge crisis | LOW | Run `brain audit --older-than 90d`; mass-deprecate untouched items; selectively re-verify high-usage items |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Mid-function chunking | Phase 1 — Core RAG pipeline | Parse all stored code chunks; assert zero mid-function splits |
| Wrong embedding model for code | Phase 1 — Embedding layer | Benchmark code retrieval with code-specific vs. general model; > 70% recall @3 for code queries |
| Missing metadata schema | Phase 1 — Schema design | All required columns exist and are non-nullable; migration enforces constraints |
| Semantic-only retrieval | Phase 1 — Retrieval layer | Exact identifier queries return correct chunk in top-3 |
| Bad MCP tool descriptions | Phase 1 — Tool design | 10-query test suite; Claude calls correct tool for each |
| Tool schema context overhead | Phase 1 — Tool design | Total tool schema tokens measured and under 3,000 |
| Noisy auto-capture | Phase 2 — Capture pipeline | Quality gate rejects test noise inputs; storage growth rate is bounded |
| Credentials leaking | Phase 2 — Capture pipeline | Secret scanner in place before any auto-capture enabled |
| No recency decay | Phase 2 — Retrieval scoring | Synthetic recency test passes |
| Contradiction handling | Phase 3 — Knowledge lifecycle | Conflict detection scan runs on write; `supersedes` field exists |
| SQLite lock contention | Phase 1 — Database layer | WAL mode enabled at creation; concurrent write test passes |
| Model cold-start latency | Phase 1 — Server architecture | Long-lived process; model loaded once; retrieval < 300ms steady-state |
| Embedding model migration corruption | Phase 1 (schema) + Phase 3 (tooling) | `embedding_model_id` on all rows; migration utility tested |
| Knowledge drift / staleness | Phase 3 — Knowledge lifecycle | `last_accessed_at` tracked; audit command surfaces old items |
| Global rule scope leak | Phase 1 — Schema + retrieval | Cross-project query test confirms isolation |
| Capture friction | Phase 1 — MCP tool UX | Time-to-save measured under 10 seconds from intent to confirmation |
| Context window poisoning | Phase 1 — Retrieval layer | Top-k ≤ 5; total retrieval response under 2,000 tokens |

---

## Sources

- Databricks: Chunking Strategies for RAG — https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089
- Stack Overflow Blog: Breaking Up Is Hard To Do (chunking) — https://stackoverflow.blog/2024/12/27/breaking-up-is-hard-to-do-chunking-in-rag-applications/
- Modal: 6 Best Code Embedding Models Compared — https://modal.com/blog/6-best-code-embedding-models-compared
- Qodo: State-of-the-Art Code Retrieval — https://www.qodo.ai/blog/qodo-embed-1-code-embedding-code-retrieval/
- blog.lakshminp.com: Why Your MCP Server Will Die in Obscurity — https://blog.lakshminp.com/p/mcp-server-tool-descriptions
- DEV: MCP Tool Design — Why Your AI Agent Is Failing — https://dev.to/aws-heroes/mcp-tool-design-why-your-ai-agent-is-failing-and-how-to-fix-it-40fc
- MindStudio: Claude Code MCP Server Token Overhead — https://www.mindstudio.ai/blog/claude-code-mcp-server-token-overhead-2
- Scott Spence: Optimising MCP Server Context Usage — https://scottspence.com/posts/optimising-mcp-server-context-usage-in-claude-code
- nb-data.com: 23 RAG Pitfalls and How to Fix Them — https://www.nb-data.com/p/23-rag-pitfalls-and-how-to-fix-them
- we45 Blogs: RAG Systems Are Leaking Sensitive Data — https://www.we45.com/post/rag-systems-are-leaking-sensitive-data
- GitGuardian: State of Secrets Sprawl 2026 — https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/
- AWS Security: Securing the RAG Ingestion Pipeline — https://aws.amazon.com/blogs/security/securing-the-rag-ingestion-pipeline-filtering-mechanisms/
- Elastic: Context Poisoning in LLMs — https://www.elastic.co/search-labs/blog/context-poisoning-llm
- ICLR 2025: Long-Context LLMs Meet RAG — https://proceedings.iclr.cc/paper_files/paper/2025/file/5df5b1f121c915d8bdd00db6aac20827-Paper-Conference.pdf
- Redis: Full-Text Search for RAG (BM25 + hybrid) — https://redis.io/blog/full-text-search-for-rag-the-precision-layer/
- Medium: Different Embedding Models, Hidden Cost of Model Upgrades — https://medium.com/data-science-collective/different-embedding-models-different-spaces-the-hidden-cost-of-model-upgrades-899db24ad233
- SQLite Official: File Locking and Concurrency V3 — https://sqlite.org/lockingv3.html
- aiida-core GitHub Issue: SQLite BUSY with multiple processes — https://github.com/aiidateam/aiida-core/issues/6532
- DEV: Embedded Intelligence — sqlite-vec for local AI — https://dev.to/aairom/embedded-intelligence-how-sqlite-vec-delivers-fast-local-vector-search-for-ai-3dpb
- Marco Bambini: State of Vector Search in SQLite — https://marcobambini.substack.com/p/the-state-of-vector-search-in-sqlite

---
*Pitfalls research for: Personal MCP brain server — local RAG, Python, SQLite + sqlite-vec, personal scale*
*Researched: 2026-04-14*

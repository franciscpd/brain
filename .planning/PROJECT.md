# brain

## What This Is

`brain` is a local-first MCP server that acts as a shared "brain" for Claude and other AIs — storing and retrieving code patterns (personal rules, snippets, architectural decisions, bug lessons) via RAG, so that knowledge accumulated in one project is automatically reusable in every other project.

It is a personal developer tool: a single user, multiple AI clients, and knowledge that travels across projects.

## Core Value

**Never again having to manually repeat the same rules, preferences, and coding patterns to the AI in every new project.** If brain gets this right, everything else is a bonus.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Functional MCP server exposing tools for knowledge capture and retrieval
- [ ] Local-first storage (SQLite + embedded vector store), prepared for future sync
- [ ] Locally-embedded embeddings (no dependency on Ollama or external APIs) — runs on any machine after install
- [ ] Capture and retrieval of **personal rules** (priority #1 — attacks the main pain point)
- [ ] Capture and retrieval of **reusable snippets/solutions**
- [ ] Capture and retrieval of **architectural decisions**
- [ ] Capture and retrieval of **bug/error lessons**
- [ ] Hybrid capture: automatic (via Claude Code hooks) + manual (via explicit commands/tools)
- [ ] Hybrid retrieval: relevant context injected at session start + on-demand search via tool call
- [ ] Works as an MCP client in Claude Code (CLI), Claude Desktop, Cursor/Windsurf, and direct SDK
- [ ] Knowledge scope isolable per project/global (global rules vs contextual rules)
- [ ] Friction-free capture experience — saving something takes seconds

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Project documentation (README, API docs)** — that lives in the repository; brain does not replace formal docs
- **Ticket/task system (Linear/Jira)** — brain does not manage pending work, only consolidated knowledge
- **Conversation memory / session summaries** — brain does not keep chat history; it exists for actionable patterns, not contextual recall
- **Generic knowledge base (Notion/Obsidian)** — strictly focused on code and development; not a place for life notes, research, or meetings
- **Cloud sync in v1** — schema is prepared for sync, but the implementation is deferred until personal use is validated
- **Multi-user / team sharing** — v1 scope is strictly personal
- **Integration with GSD (get-shit-done)** — brain is cross-tool and independent; GSD is a per-project workflow. Keep them separate.
- **Cloud embeddings (OpenAI/Voyage) in v1** — cost and quality do not justify an external dependency for personal use; may become a future option
- **Web interface / GUI** — v1 is MCP + CLI. Any UI is post-v1.

## Context

**Motivation:** The user notices they repeat the same instructions to the AI in every new project ("use TypeScript strict", "no `any`", commit conventions, directory structure, etc). Every new project starts from zero in terms of preference context. When a bug occurs that was already solved elsewhere, the AI has no way to remember. When an elegant solution appears, it is trapped inside the project where it was born.

**Technical ecosystem:**
- MCP (Model Context Protocol) is already natively supported by Claude Code, Claude Desktop, Cursor, Windsurf, and other IDEs — one MCP server serves all these clients with the same code
- Local-embedding RAG matured in 2024–2025: models like `nomic-embed-text` run on CPU with excellent quality
- Libraries like `fastembed` allow running embeddings without a separate Ollama server (model loaded inside the process)
- The official MCP Python SDK is mature and well-documented

**Relevant prior experience:**
- User already uses Claude Code heavily across multiple projects
- Already feels the pain of maintaining similar CLAUDE.md files
- Wants a daily-use tool, not an academic experiment

## Constraints

- **Tech stack**: Python — mature official MCP SDK, complete ML/embeddings ecosystem (fastembed, sentence-transformers), simple install via pip/uv
- **Embeddings**: Locally embedded, no Ollama or external API dependency — requirement: "runs on any machine"
- **Storage**: Local-first (SQLite + embedded vector index); schema must be versioned and prepared for future sync
- **Privacy**: No user data leaves the machine in v1 — trust and zero-operational-cost requirement
- **v1 scope**: Strictly personal (single user) — hundreds to low thousands of entries; multi-user optimization is deferred
- **MCP compatibility**: Must follow standard MCP protocol so it works in Claude Code, Desktop, Cursor, Windsurf, and direct SDK with no client-specific code
- **Setup**: Install and configuration must be simple enough for daily use — ideally `pip install` + one MCP registration command

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Local-first with SQLite + embedded embeddings | Privacy, zero cost, works offline, matches personal scope; sync can be added without changing the data model | — Pending |
| Python as implementation language | Mature official MCP SDK + most complete ML/embeddings ecosystem + trivial install via pip/uv | — Pending |
| Embedded local embeddings via fastembed/Candle (not Ollama) | Zero external dependency — user installs and runs, no separate Ollama process required | — Pending |
| nomic-embed-text as default model | Sweet spot in the 2025 RAG community: ~270MB, excellent quality for code+text, runs on CPU | — Pending |
| 4 distinct knowledge types (rules, snippets, decisions, bugs) | Each type has a different usage pattern; modeling them explicitly avoids a "generic bag of text" | — Pending |
| Structured rules + vector RAG in layers | Rules are few and curated — exact/tag lookup is enough; RAG adds value for the other 3 types | — Pending |
| Hybrid capture (automatic via hooks + manual via commands) | Automatic capture catches what goes unnoticed; manual ensures intentional curation | — Pending |
| Hybrid retrieval (session-start context + on-demand tool call) | Initial context eliminates friction for global rules; tool call lets the AI search when it actually needs to | — Pending |
| Brain independent of GSD | Brain is cross-tool, GSD is a per-project workflow — mixing scopes would hurt both | — Pending |
| v1 is personal; sync / multi-user is post-v1 | Validate the value of personal use before paying the complexity cost of sync | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-14 after initialization*

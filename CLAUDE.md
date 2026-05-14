## .planning/ — Single Source of Truth

All planning artifacts MUST go in `.planning/`. Never outside it.

```
.planning/
└── phases/
    └── {N}-{slug}/          ← one folder per GSD phase (e.g. 01-auth)
        ├── DISCUSS.md        ← gsd:discuss output
        ├── BRAINSTORM.md     ← superpowers:brainstorm output
        ├── PLAN.md           ← superpowers:write-plan output
        ├── PROGRESS.md       ← superpowers:execute-plan tracking
        └── VERIFY.md         ← superpowers:requesting-code-review output
```

Before writing any artifact, MUST identify the active GSD phase and resolve its folder: `.planning/phases/{N}-{slug}/`. Create the folder if it does not exist. All Superpowers outputs for that phase go inside it.

---

## Workflow — Follow This Order Exactly

```
gsd:discuss → brainstorm → write-plan → execute-plan → gsd:verify
```

> `$PHASE` = active GSD phase folder, e.g. `.planning/phases/01-auth`

### Phase 1 — discuss
- Trigger: any new feature, task or bug with unclear scope
- MUST capture: requirements, scope, what's out of scope, priority
- MUST save output to `$PHASE/DISCUSS.md`
- MUST NOT proceed without explicit user approval

### Phase 2 — brainstorm
- Trigger: automatically after discuss approval
- MUST invoke `/superpowers:brainstorm` using `$PHASE/DISCUSS.md` or `$PHASE/{N}-CONTEXT.md` as context
- Focus: technical approach, architecture, trade-offs, Laravel patterns
- MUST save output to `$PHASE/BRAINSTORM.md`
- MUST NOT proceed without explicit user approval

### Phase 3 — write-plan
- Trigger: automatically after brainstorm approval
- MUST invoke `/superpowers:write-plan` using `$PHASE/DISCUSS.md` or `$PHASE/{N}-CONTEXT.md` + `$PHASE/BRAINSTORM.md` as input
- Output MUST include: affected files, atomic tasks, verify commands, commit messages
- MUST save output to `$PHASE/PLAN.md`
- MUST NOT proceed without explicit user approval

### Phase 4 — execute-plan
- Trigger: automatically after plan approval
- MUST invoke `/superpowers:execute-plan` using `$PHASE/PLAN.md`
- MUST follow TDD: write failing test → implement → pass (RED → GREEN → REFACTOR)
- MUST track progress in `$PHASE/PROGRESS.md`
- MUST commit atomically per logical task immediately after verify passes

### Phase 5 — verify
- Trigger: automatically after execute-plan completes
- MUST invoke `/superpowers:requesting-code-review`
- MUST run `php artisan test && php artisan pint` — nothing is done without passing evidence
- MUST save output to `$PHASE/VERIFY.md`


## Skip Rules

| Situation | Skip |
|---|---|
| Scope is already clear | Skip discuss, start at brainstorm |
| Approach is already clear | Skip brainstorm, start at write-plan |
| Small well-defined task | Skip discuss + brainstorm, start at write-plan |
| Known bug with clear fix | Use `/superpowers:systematic-debugging` directly |

---

## Commits

```
type(scope): description
```
Types: `feat | fix | refactor | test | docs | style | chore`
One commit per logical task. Never commit broken code.

---

## Rules

- Bugs before features. Max 2–3 WIP tasks.
- Never deploy without explicit approval.
- Never skip phases without a skip rule justifying it.
- Always ask when scope or approach is unclear.


<!-- GSD:project-start source:PROJECT.md -->
## Project

**brain**

`brain` é um servidor MCP local-first que funciona como um "cérebro" compartilhado para Claude e outras IAs — armazenando e recuperando padrões de código (regras pessoais, snippets, decisões, lições de bugs) via RAG, de modo que o conhecimento acumulado em um projeto seja automaticamente reutilizável em todos os outros.

É uma ferramenta pessoal de desenvolvedor: um só usuário, múltiplas IAs clientes, conhecimento que atravessa projetos.

**Core Value:** **Nunca mais precisar repetir manualmente as mesmas regras, preferências e padrões de código para a IA em cada novo projeto.** Se o brain fizer isso bem, tudo o mais é bônus.

### Constraints

- **Tech stack**: Python — SDK MCP oficial maduro, ecossistema ML/embeddings completo (fastembed, sentence-transformers), instalação simples via pip/uv
- **Embeddings**: Locais embutidos, sem dependência de Ollama ou API externa — requisito: "funciona em qualquer máquina"
- **Armazenamento**: Local-first (SQLite + vector index embutido); schema deve ser versionado e preparado para sync futuro
- **Privacidade**: Nenhum dado sai da máquina do usuário no v1 — requisito de confiança e de zero custo operacional
- **Escopo v1**: Estritamente pessoal (um usuário) — centenas a poucos milhares de entradas; otimização para multi-usuário fica para depois
- **Compatibilidade MCP**: Deve seguir protocolo MCP padrão para funcionar em Claude Code, Desktop, Cursor, Windsurf e SDK sem código específico por cliente
- **Setup**: Instalação e configuração devem ser simples o bastante para uso diário — idealmente `pip install` + comando de registro MCP
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `mcp` (official Python SDK) | 1.27.0 | MCP server protocol, tool/resource/prompt definitions | Official Anthropic SDK. FastMCP 1.0 was merged into it; available as `mcp.server.fastmcp.FastMCP`. Single package handles full MCP spec compliance, connection lifecycle, stdio transport. |
| Python | 3.10+ | Runtime | Required by both `mcp` SDK and `fastembed`. 3.11 recommended for performance; 3.12 stable and well-tested. |
| SQLite (stdlib `sqlite3`) | bundled | Structured knowledge storage — entries, metadata, tags, scopes | Built into Python, zero install friction, file-based (portable), WAL mode enables concurrent reads. Perfect for single-user, hundreds-to-low-thousands of entries. Versionable schema. |
| `fastembed` | 0.8.0 | Local embedding inference, no external daemon | Uses ONNX Runtime, NOT PyTorch. ~50MB install (no GBs of torch). Model downloaded once to cache on first run, then runs entirely in-process. Zero external dependency — no Ollama, no API. The "runs on any machine" requirement is met by design. |
| `sqlite-vec` | 0.1.9 | Embedded vector similarity search inside SQLite | Single SQLite extension (.so/.dll), loaded at runtime via `sqlite_vec.load()`. Brute-force ANN search is fast enough for <100K vectors. Keeps vector store co-located with metadata store — one file, one backup, one sync unit. No separate process. |
| `uv` | latest | Dependency management, packaging, distribution | De-facto standard for Python MCP servers (official MCP docs use `uv add`). `uvx brain-server` installs and runs without venv activation. `uv tool install` supports offline .whl installs. `[project.scripts]` entry points work natively. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `alembic` | 1.x (1.15+) | SQLite schema migrations | Use from day 1. Brain's local DB will evolve across versions; without migrations, schema changes break existing installations. Use batch mode for SQLite's ALTER limitations. |
| `SQLAlchemy` | 2.x | ORM + Alembic integration | Optional but recommended if using Alembic. Provides typed model definitions and migration target. Core mode (not ORM) acceptable for simplicity. |
| `pydantic` | 2.x | Input/output validation for MCP tools | The MCP SDK uses Pydantic v2 for tool parameter schemas. Use it for knowledge entry models to get free JSON schema generation. |
| `rich` | latest | CLI output for admin/debug commands | Nice-to-have for `brain status`, `brain list`, etc. Not required for MCP operation. |
| `pytest` + `pytest-asyncio` | latest | Testing async MCP tool handlers | MCP tool handlers are async; pytest-asyncio is required. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| `mcp[cli]` | MCP Inspector — interactive test UI | Install via `uv add "mcp[cli]"`. Run `mcp dev brain/server.py` to open browser-based inspector. Use during development to test tools without a full AI client. |
| `uv` | Venv, deps, build, publish | `uv init`, `uv add`, `uv build`, `uvx`. Replace pip entirely. Official MCP docs use uv exclusively. |
## Detailed Rationale by Dimension
### 1. MCP Python SDK — `mcp` package, FastMCP via official SDK
### 2. Local Storage — SQLite
### 3. Vector Index — `sqlite-vec`
| Option | Verdict | Reason |
|--------|---------|--------|
| `sqlite-vec` | RECOMMENDED | Pure C, no deps, ships as Python package, co-located with SQLite DB, brute-force is fast enough for <10K entries |
| `sqlite-vss` | AVOID | Predecessor to sqlite-vec, archived by author, replaced by sqlite-vec |
| ChromaDB | AVOID for v1 | Heavy dependencies (hnswlib, clickhouse-connect), embeds fine but installs ~500MB; overkill for a personal tool with thousands of entries |
| LanceDB | Consider for v2 | Excellent embedded library (0.30.2, March 2026), no server required, but uses Lance columnar format — a separate data file from SQLite. Good if you need million-scale or multimodal embeddings later. Alpha stability classification. |
| Qdrant embedded | AVOID | Requires Rust binary, heavier footprint |
# Creates virtual table: CREATE VIRTUAL TABLE vec_entries USING vec0(embedding float[768])
### 4. Embedding Runner — `fastembed`
| Option | Verdict | Reason |
|--------|---------|--------|
| `fastembed` | RECOMMENDED | ONNX Runtime (not PyTorch), ~50MB install, runs in-process, model cached after first download, no daemon |
| `sentence-transformers` | AVOID for this use case | Requires PyTorch (~2GB install on some platforms), slower cold start, more memory. Excellent library but wrong tool when the constraint is "no heavy deps, runs anywhere." |
| `llama.cpp` Python bindings | AVOID | Designed for LLM inference, not embeddings; requires C++ compilation on install, fragile on some platforms |
| Candle (Rust/Python) | AVOID | Immature Python bindings, harder to install, less community testing |
| Ollama | EXPLICITLY EXCLUDED | Requires running a separate daemon — violates the "no external daemon" constraint. Good tool, wrong fit. |
- Install size: ~50MB (onnxruntime) vs ~2GB (torch on some platforms)
- Cold start: milliseconds vs seconds
- No CUDA setup required; CPU inference is the fast path by design
- Models are pre-quantized to INT8/FP16 for CPU
### 5. Default Embedding Model — `nomic-ai/nomic-embed-text-v1.5`
| Model | Dims | Size | Quality | CPU Speed | Verdict |
|-------|------|------|---------|-----------|---------|
| `nomic-ai/nomic-embed-text-v1.5` | 768 | ~270MB | Excellent (86%+ MTEB) | Good | RECOMMENDED |
| `nomic-ai/nomic-embed-text-v1.5-Q` | 768 | ~70MB quantized | Very Good | Better | Alternative if size matters |
| `BAAI/bge-small-en-v1.5` | 384 | ~130MB | Good | Excellent | Use if CPU speed is critical |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | ~90MB | Acceptable (56% Top-5 in recent benchmarks) | Fastest | Do not recommend — quality gap is significant |
### 6. Packaging and MCP Registration
# Install from local source
# Or register with absolute path
## Installation
# Create project
# Core dependencies
# Dev dependencies
# Build distribution
# → dist/brain-0.1.0-py3-none-any.whl
# Install as tool (for registration)
## Alternatives Considered
| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| Vector store | `sqlite-vec` | LanceDB | If entries grow to 100K+ or multimodal embeddings needed (v2+) |
| Vector store | `sqlite-vec` | ChromaDB | If you already have a ChromaDB-heavy stack and don't mind the heavier install |
| Embedding runner | `fastembed` | `sentence-transformers` | If you're already in a PyTorch environment (e.g., running GPU-accelerated ML work) |
| Embedding model | `nomic-embed-text-v1.5` | `nomic-embed-text-v1.5-Q` (quantized) | If download size is constrained or machine is very low-spec |
| Embedding model | `nomic-embed-text-v1.5` | `BAAI/bge-small-en-v1.5` | If CPU speed for embedding is more important than retrieval quality |
| Migrations | Alembic | Manual `PRAGMA user_version` | Never — Alembic's batch mode handles SQLite ALTER limitations cleanly |
| MCP high-level API | `mcp.server.fastmcp.FastMCP` (official) | `fastmcp` package by PrefectHQ | If you need advanced features: component versioning, granular auth, OpenTelemetry. For a personal tool, official SDK is sufficient. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Ollama | Requires a running daemon — violates "runs on any machine" constraint. User may not have Ollama installed or running. | `fastembed` (in-process, no daemon) |
| `sqlite-vss` | Archived by the author in 2024. Replaced by sqlite-vec. | `sqlite-vec` |
| `sentence-transformers` (alone) | Pulls in PyTorch (~2GB on some platforms). Heavy install breaks "simple setup" constraint. Slow cold start on CPU. | `fastembed` (ONNX Runtime, ~50MB) |
| `openai` embeddings API | Sends data to OpenAI servers — violates privacy constraint. Costs money. Requires internet. | `fastembed` (local) |
| ChromaDB | 500MB+ install, overkill for thousands of entries, separate data format from SQLite. | `sqlite-vec` |
| DuckDB | Columnar analytics engine — wrong access pattern for row-oriented entry storage. | SQLite stdlib |
| libsql / Turso | Adds sync infrastructure before sync is a requirement. Premature optimization. | SQLite stdlib (migrate to libsql in v2 when sync is needed) |
| SSE transport | Deprecated in MCP spec June 2025. | stdio for local; Streamable HTTP for remote |
| `print()` in stdio server | Corrupts JSON-RPC stream. Silent failure. | `logging` to stderr |
| `all-MiniLM-L6-v2` | ~56% Top-1 accuracy in recent benchmarks — significantly behind modern models. | `nomic-embed-text-v1.5` |
| `fastmcp` (PrefectHQ package) | Separate project from official SDK. Adds dependency, versioning risk, and documentation split. v3 features are not needed for a personal tool. | `mcp.server.fastmcp.FastMCP` (same API, already in official `mcp` package) |
## Version Compatibility
| Package | Version | Python | Notes |
|---------|---------|--------|-------|
| `mcp` | 1.27.0 | >=3.10 | Use `mcp[cli]` for development inspector |
| `fastembed` | 0.8.0 | >=3.10 | Requires onnxruntime; pulls it automatically |
| `sqlite-vec` | 0.1.9 | >=3.8 | Pre-built wheels for Linux/macOS/Windows — no compilation |
| `alembic` | 1.15+ | >=3.8 | Use batch mode for SQLite ALTER operations |
| `pydantic` | 2.x | >=3.8 | MCP SDK uses Pydantic v2; do not mix v1 |
| `lancedb` | 0.30.2 | >=3.10 | Alpha stability — defer to v2 if needed |
## Sources
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk) — current version 1.27.0, FastMCP integration, stdio transport, logging warnings (HIGH confidence)
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/1.7.1/) — version history (HIGH confidence)
- [Build an MCP server — official docs](https://modelcontextprotocol.io/docs/develop/build-server) — uv setup, Python requirements, logging gotcha (HIGH confidence)
- [fastembed PyPI](https://pypi.org/project/fastembed/) — version 0.8.0, Python >=3.10, ONNX Runtime (HIGH confidence)
- [fastembed supported models](https://qdrant.github.io/fastembed/examples/Supported_Models/) — exact model name strings verified (HIGH confidence)
- [sqlite-vec PyPI](https://pypi.org/project/sqlite-vec/) — version 0.1.9, March 2026 (HIGH confidence)
- [sqlite-vec GitHub](https://github.com/asg017/sqlite-vec) — architecture, Python usage (HIGH confidence)
- [LanceDB PyPI](https://pypi.org/project/lancedb/) — version 0.30.2, Alpha status (HIGH confidence)
- [FastMCP 2.0 announcement](https://www.jlowin.dev/blog/fastmcp-2) — clarifies split between community fastmcp and official SDK (MEDIUM confidence)
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) — registration commands, config scopes (HIGH confidence)
- [FastMCP Claude Code integration](https://gofastmcp.com/integrations/claude-code) — uvx registration pattern (MEDIUM confidence)
- Embedding benchmark comparisons — nomic vs MiniLM accuracy figures are from multiple blog sources (MEDIUM confidence — official MTEB leaderboard should be verified before finalizing model choice)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

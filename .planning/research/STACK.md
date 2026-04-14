# Stack Research

**Domain:** Local-first MCP server with embedded RAG (personal knowledge base for AI clients)
**Researched:** 2026-04-14
**Confidence:** HIGH (most choices verified against official docs and PyPI; embedding model benchmark is MEDIUM)

---

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

---

## Detailed Rationale by Dimension

### 1. MCP Python SDK — `mcp` package, FastMCP via official SDK

**Package:** `mcp` on PyPI. Install with `uv add "mcp[cli]"`.

**Current version:** 1.27.0 (April 2026). Actively maintained by Anthropic.

**Key fact:** FastMCP 1.0 was absorbed into the official SDK and is available as `mcp.server.fastmcp.FastMCP`. This is the high-level decorator-based API. There is a separate community project (`fastmcp` package by PrefectHQ) at v3.0 with additional features — but for a personal tool, the official SDK's FastMCP is sufficient and has zero extra dependencies.

**Server structure:**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("brain")

@mcp.tool()
async def capture_rule(content: str, scope: str = "global") -> str:
    """Capture a personal coding rule or preference."""
    ...

@mcp.tool()
async def search_knowledge(query: str, type: str = "all") -> list[dict]:
    """Search the knowledge base semantically."""
    ...

if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport — correct for local MCP servers
```

**Transport:** Use `stdio` for local servers (default when `mcp.run()` is called without args). This is how Claude Code, Claude Desktop, and Cursor all launch local MCP servers — via a subprocess with stdin/stdout. Do NOT use SSE (deprecated in June 2025 spec) or Streamable HTTP for a local daemon.

**CRITICAL logging gotcha:** Never use `print()` in a stdio MCP server — it corrupts the JSON-RPC stream. Use `logging` configured to write to `stderr` or a file.

### 2. Local Storage — SQLite

**Choice:** Python stdlib `sqlite3` + WAL mode + `alembic` for migrations.

**Why SQLite over DuckDB:** DuckDB is an analytics engine optimized for columnar aggregations. Brain's access pattern is row-oriented (fetch entry by ID, filter by tag/scope, insert single entries). SQLite is purpose-built for this. DuckDB adds ~30MB binary with no benefit.

**Why SQLite over libsql/Turso:** libsql is SQLite + sync. Brain v1 explicitly defers sync. Adding libsql now couples the schema to Turso's sync protocol before that constraint exists. Use SQLite directly; migrate to libsql when sync is needed (it's wire-compatible).

**Schema approach:** WAL mode (`PRAGMA journal_mode=WAL`) for concurrent reads during search. One database file at `~/.brain/brain.db`. Schema versioned with Alembic from the first migration.

**Why migrations from day 1:** Users will install v1 and upgrade to v2+. Without Alembic, a schema change requires manual `DROP TABLE` or silent data loss. The cost of adding Alembic now is one `alembic init` command; the cost of not adding it is a broken upgrade path.

### 3. Vector Index — `sqlite-vec`

**Choice:** `sqlite-vec` 0.1.9 (March 2026, stable releases since August 2024).

**Why sqlite-vec over alternatives:**

| Option | Verdict | Reason |
|--------|---------|--------|
| `sqlite-vec` | RECOMMENDED | Pure C, no deps, ships as Python package, co-located with SQLite DB, brute-force is fast enough for <10K entries |
| `sqlite-vss` | AVOID | Predecessor to sqlite-vec, archived by author, replaced by sqlite-vec |
| ChromaDB | AVOID for v1 | Heavy dependencies (hnswlib, clickhouse-connect), embeds fine but installs ~500MB; overkill for a personal tool with thousands of entries |
| LanceDB | Consider for v2 | Excellent embedded library (0.30.2, March 2026), no server required, but uses Lance columnar format — a separate data file from SQLite. Good if you need million-scale or multimodal embeddings later. Alpha stability classification. |
| Qdrant embedded | AVOID | Requires Rust binary, heavier footprint |

**sqlite-vec setup:**

```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect("brain.db")
sqlite_vec.load(conn)
# Creates virtual table: CREATE VIRTUAL TABLE vec_entries USING vec0(embedding float[768])
```

**Scale justification:** Brain v1 scope is "hundreds to low thousands of entries." sqlite-vec's brute-force search handles 10K 768-dim vectors in <10ms on CPU. No ANN index needed at this scale.

### 4. Embedding Runner — `fastembed`

**Choice:** `fastembed` 0.8.0 (March 2026, maintained by Qdrant team, Apache 2.0).

**Why fastembed over alternatives:**

| Option | Verdict | Reason |
|--------|---------|--------|
| `fastembed` | RECOMMENDED | ONNX Runtime (not PyTorch), ~50MB install, runs in-process, model cached after first download, no daemon |
| `sentence-transformers` | AVOID for this use case | Requires PyTorch (~2GB install on some platforms), slower cold start, more memory. Excellent library but wrong tool when the constraint is "no heavy deps, runs anywhere." |
| `llama.cpp` Python bindings | AVOID | Designed for LLM inference, not embeddings; requires C++ compilation on install, fragile on some platforms |
| Candle (Rust/Python) | AVOID | Immature Python bindings, harder to install, less community testing |
| Ollama | EXPLICITLY EXCLUDED | Requires running a separate daemon — violates the "no external daemon" constraint. Good tool, wrong fit. |

**Key technical distinction:** fastembed uses the ONNX Runtime for inference — not PyTorch. This means:
- Install size: ~50MB (onnxruntime) vs ~2GB (torch on some platforms)
- Cold start: milliseconds vs seconds
- No CUDA setup required; CPU inference is the fast path by design
- Models are pre-quantized to INT8/FP16 for CPU

**Model download behavior:** First run downloads the model to `~/.cache/fastembed/`. Subsequent runs use cached model. This is correct behavior for "installs once, runs anywhere."

### 5. Default Embedding Model — `nomic-ai/nomic-embed-text-v1.5`

**Choice:** `nomic-ai/nomic-embed-text-v1.5` via fastembed.

**Exact Python string:** `"nomic-ai/nomic-embed-text-v1.5"` (confirmed in fastembed's supported models list).

**Why this model:**

| Model | Dims | Size | Quality | CPU Speed | Verdict |
|-------|------|------|---------|-----------|---------|
| `nomic-ai/nomic-embed-text-v1.5` | 768 | ~270MB | Excellent (86%+ MTEB) | Good | RECOMMENDED |
| `nomic-ai/nomic-embed-text-v1.5-Q` | 768 | ~70MB quantized | Very Good | Better | Alternative if size matters |
| `BAAI/bge-small-en-v1.5` | 384 | ~130MB | Good | Excellent | Use if CPU speed is critical |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | ~90MB | Acceptable (56% Top-5 in recent benchmarks) | Fastest | Do not recommend — quality gap is significant |

**Why nomic over bge-small:** Brain's use case mixes code snippets, architectural decisions, and bug lessons — these are heterogeneous, domain-specific texts. nomic-embed-text v1.5 was trained with an 8192-token context window and Matryoshka Representation Learning, making it substantially better for mixed-content retrieval than smaller models. The quality difference in Top-1 accuracy (~30% for MiniLM vs 86%+ for nomic) matters when the brain is asked to surface the right rule from a library of hundreds.

**Important:** nomic-embed-text requires a task prefix for proper retrieval. Use `"search_document: "` prefix when storing, and `"search_query: "` prefix when querying.

**Fallback:** `"nomic-ai/nomic-embed-text-v1.5-Q"` (quantized, ~70MB) is a strong fallback for machines with very limited disk or slow downloads. Quality is still excellent.

### 6. Packaging and MCP Registration

**Package manager:** `uv` — not pip.

**Why uv:** Official MCP documentation uses `uv` exclusively. All MCP server community projects use `uv`. `uvx brain-server` installs-and-runs without venv management. Lockfile ensures reproducible installs across machines.

**pyproject.toml entry point:**

```toml
[project.scripts]
brain-server = "brain.server:main"
brain = "brain.cli:main"
```

**Registration — Claude Code (recommended, user scope):**

```bash
claude mcp add brain-server -s user -- uvx brain-server
```

Stores in `~/.claude.json`, available across all projects. No per-project `.mcp.json` needed for a personal tool.

**Registration — Claude Desktop:**

```json
{
  "mcpServers": {
    "brain": {
      "command": "uvx",
      "args": ["brain-server"]
    }
  }
}
```

Config at `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS).

**Registration — Cursor/Windsurf:** Same JSON format in their respective MCP config files.

**Local dev registration (before publishing to PyPI):**

```bash
# Install from local source
uv tool install --editable /path/to/brain

# Or register with absolute path
claude mcp add brain-server -s user -- uv run --project /path/to/brain brain-server
```

---

## Installation

```bash
# Create project
uv init brain
cd brain

# Core dependencies
uv add "mcp[cli]" fastembed sqlite-vec alembic sqlalchemy pydantic

# Dev dependencies
uv add --dev pytest pytest-asyncio

# Build distribution
uv build
# → dist/brain-0.1.0-py3-none-any.whl

# Install as tool (for registration)
uv tool install dist/brain-0.1.0-py3-none-any.whl
```

---

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

---

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

---

## Version Compatibility

| Package | Version | Python | Notes |
|---------|---------|--------|-------|
| `mcp` | 1.27.0 | >=3.10 | Use `mcp[cli]` for development inspector |
| `fastembed` | 0.8.0 | >=3.10 | Requires onnxruntime; pulls it automatically |
| `sqlite-vec` | 0.1.9 | >=3.8 | Pre-built wheels for Linux/macOS/Windows — no compilation |
| `alembic` | 1.15+ | >=3.8 | Use batch mode for SQLite ALTER operations |
| `pydantic` | 2.x | >=3.8 | MCP SDK uses Pydantic v2; do not mix v1 |
| `lancedb` | 0.30.2 | >=3.10 | Alpha stability — defer to v2 if needed |

**Compatibility note:** `mcp` SDK 1.27.0 requires Pydantic v2. If any other dependency pins Pydantic v1, there will be a conflict. Check `uv tree` after installing.

---

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

---

*Stack research for: brain — local-first MCP knowledge server with embedded RAG*
*Researched: 2026-04-14*

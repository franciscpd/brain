# Phase 2: Knowledge CRUD + Scoping + MCP Core — Brainstorming

**Date:** 2026-04-14
**Input:** `02-CONTEXT.md` (33 decisions, locked)
**Status:** Ready for planning
**Output target:** `PLAN.md` (via `/gsd-plan-phase 2` or `writing-plans` skill)

---

## 1. Purpose of this document

`02-CONTEXT.md` locks *what* to build (33 decisions covering tool surface, scoping, error contract, re-embedding, etc.). This brainstorm locks *how* to build it: module layout, service composition, migration strategy, concurrency model, and test strategy. It is consumed by the planner — each section below should be directly actionable as plan tasks.

Non-goals of this brainstorm: re-opening CONTEXT decisions, picking exact function signatures, writing code.

---

## 2. Starting state (Phase 1 facts that shape Phase 2)

Verified by grep against `src/brain_mcp/` and the Alembic migration:

- `src/brain_mcp/db/connection.py` provides `connect(db_path)` returning a `sqlite3.Connection` with WAL, `busy_timeout`, `foreign_keys=ON`, `isolation_level=None`, `sqlite-vec` loaded, and a `transaction()` context manager. **All Phase 2 DB access goes through this — no raw `sqlite3.connect`.**
- `src/brain_mcp/db/schema.py` holds minimal Pydantic models (`KnowledgeItemBase`, `Rule`, `Snippet`, `Decision`, `BugLesson`). Currently only the `kind` discriminator is declared per subclass. Phase 2 must expand these with the kind-specific fields enumerated in §5.
- Migration `0001_initial.py` already created:
  - `knowledge_items` (shared columns: id, kind, title, content, tags, scope_type, scope_value, created_at, updated_at, embedding_model_id, sync_id, device_id, synced_at)
  - Extension tables: `rules(item_id, priority)`, `snippets(item_id, language, usage_context)`, `decisions`, `bug_lessons`
  - `vec_rowid_map`, `knowledge_vec` (sqlite-vec virtual table), `knowledge_fts` (FTS5 virtual table) + update trigger `knowledge_items_au`
- Phase 1 does **not** yet have a `topic` column on `rules` or a `content_hash` column on `knowledge_items`. Phase 2 must add these in migration `0002` (§4).
- `src/brain_mcp/embedding/service.py` has `EmbeddingService` with lazy-loaded fastembed, task prefixes (`search_document:` / `search_query:`), and model-id tagging. Phase 2 calls `embed_document` for writes and `embed_query` for the search stub.
- `src/brain_mcp/errors.py` has a `BrainError` base with `code` + `details` fields. Phase 2 adds `SecretDetectedError`, `NotFoundError`, `ScopeError`, `ValidationError` as subclasses — all mapping 1:1 to the JSON error contract from D-25.
- `src/brain_mcp/logging.py` exposes `configure_logging(stderr_only=True)`. The MCP server **must** call this before doing anything else. The existing Phase 1 stderr-only test should be extended to cover the server entry point.
- `src/brain_mcp/paths.py` exposes `BrainPaths` (brain home, db path, model cache). Phase 2 consumes it in the server lifespan and CLI wrappers.
- Phase 1 `tests/` already uses a fake embedder to avoid the 270MB model download in CI. Phase 2 reuses this pattern for service and MCP tests.
- 46 tests green as of Phase 1 close. Phase 2 should end with ~76 green (projected ~30 new).

---

## 3. Module layout

New modules added under `src/brain_mcp/`:

```
src/brain_mcp/
├── db/                              # Phase 1 (existing) — extend, do not restructure
│   ├── connection.py                #   (existing)
│   ├── schema.py                    #   EXPAND: full kind-specific fields + validators
│   └── migrations/
│       └── versions/
│           ├── 0001_initial.py      #   (existing)
│           └── 0002_phase2.py       # NEW — topic + content_hash columns
├── embedding/                       # Phase 1 (existing) — consume only
├── scanner/                         # NEW
│   └── secrets.py                   #   SecretScanner wrapping detect-secrets
├── scope/                           # NEW
│   ├── project_id.py                #   resolve_project_id(mcp_roots, cwd)
│   └── resolver.py                  #   ScopeResolver (filter + override)
├── service/                         # NEW
│   └── knowledge.py                 #   KnowledgeService (CRUD + embed + scan)
├── mcp/                             # NEW
│   ├── context.py                   #   BrainContext dataclass (lifespan state)
│   ├── errors.py                    #   BrainError -> JSON contract translator
│   ├── server.py                    #   FastMCP app + lifespan + main()
│   ├── tools.py                     #   tool handlers
│   └── resources.py                 #   session briefing Resource
├── cli/                             # Phase 1 (existing) — unchanged
├── errors.py                        # EXPAND with new subclasses
├── logging.py                       # (existing, no change)
└── paths.py                         # (existing, no change)
```

**Rationale for this layout:**

- `scanner/`, `scope/`, `service/`, and `mcp/` each own a single responsibility and expose a narrow public API. Every module can be understood in isolation and tested without booting the MCP server.
- No module imports from `mcp/` except `mcp/` itself — services and the scanner are reusable from the CLI (Phase 4: `brain save`) and tests.
- The `mcp/` package does **not** do any business logic. It is thin glue: lifespan wiring, request → service call, error translation. This keeps MCP-specific concerns (the `isError` contract, tool descriptions, Resource URI pattern) out of the domain code.

New `pyproject.toml` entry point: `brain-server = "brain_mcp.mcp.server:main"`. Keep the existing `brain = "brain_mcp.cli:app"` untouched.

---

## 4. Data layer changes — migration `0002_phase2.py`

Two schema changes, both via Alembic **batch mode** (required for SQLite `ALTER`):

### 4.1 `rules.topic`

```sql
ALTER TABLE rules ADD COLUMN topic TEXT NULL;
CREATE INDEX idx_rules_topic ON rules(topic) WHERE topic IS NOT NULL;
```

- Purpose: drives the read-time override from D-13. A partial index keeps the cost of lookups low even when most rules are topic-less.
- Nullable because existing rules have no topic and un-topiced rules continue to stack (D-14).
- Downgrade: drop index, drop column.

### 4.2 `knowledge_items.content_hash`

```sql
ALTER TABLE knowledge_items ADD COLUMN content_hash TEXT NULL;
```

- Purpose: drives content-hash-triggered re-embedding from D-17. `NULL` means "hash not yet computed" — treated as dirty on update so the first update after migration re-embeds (acceptable and rare, since Phase 2 is where creates start happening).
- No index — only read when updating, always by `id` (primary key already covers lookup).
- Downgrade: drop column.

### 4.3 Test

`tests/test_migration_0002.py`:
- apply on fresh DB (upgrade from 0001 → 0002, assert columns exist)
- upgrade is idempotent (second run is a no-op)
- downgrade removes both columns cleanly
- re-upgrade after downgrade works

---

## 5. Domain model expansion — `db/schema.py`

Current Pydantic classes get kind-specific fields plus normalizing validators. Fields chosen to match REQUIREMENTS.md KNOW-01..04 exactly.

| Kind | Fields added (beyond `KnowledgeItemBase`) |
|---|---|
| `Rule` | `priority: int = 50`, `topic: str \| None = None` |
| `Snippet` | `language: str`, `usage_context: str \| None = None` |
| `Decision` | `decision_context: str`, `rationale: str`, `alternatives: str \| None = None` |
| `BugLesson` | `symptom: str`, `root_cause: str`, `fix: str`, `prevention: str \| None = None` |

`KnowledgeItemBase` continues to carry: `id`, `kind`, `title`, `content`, `tags`, `scope_type`, `scope_value`, `created_at`, `updated_at`, `embedding_model_id`, `sync_id`, `device_id`, `synced_at`, and (new) `content_hash`.

### Meaning of `content` per kind

`KnowledgeItemBase.content` is the **primary searchable text** for the item. The mapping from REQUIREMENTS.md fields to `content` per kind is:

| Kind | `content` holds | Extension fields (stored separately) |
|---|---|---|
| `Rule` | The rule text itself (KNOW-01 "content") | `priority`, `topic` |
| `Snippet` | The code snippet (KNOW-02 "code") | `language`, `usage_context` |
| `Decision` | The decision statement itself (KNOW-03 "decision") | `decision_context`, `rationale`, `alternatives` |
| `BugLesson` | A canonical body built by the serializer from `symptom` + `fix` (KNOW-04 has no standalone "content"; we synthesize one for vec/FTS search) | `symptom`, `root_cause`, `fix`, `prevention` |

The FTS5 and vec tables from Phase 1 index `knowledge_items.content`. Defining `content` as the canonical searchable body per kind keeps that indexing meaningful for all four types. For `BugLesson`, the service's `serialize_for_embedding` helper is also what populates `content` at create time from the extension fields, so the hash and the indexed text stay consistent.

### Validators

- **Tag normalizer** (D-19) — `@field_validator('tags', mode='before')` on `KnowledgeItemBase`:
  - accept `list[str]` or `None`
  - for each tag: `strip()`, `lower()`, replace `_` and whitespace runs with `-`, drop empties
  - dedup preserving the first occurrence, then `sorted()` so JSON storage is canonical
- **Language normalizer** (D-20) — `Snippet.language`: `strip().lower()`; reject empty.
- **Topic normalizer** (D-13) — `Rule.topic`: if present, `strip().lower()` + hyphenize same as tags.
- **Scope validator** on `KnowledgeItemBase` — `@model_validator(mode='after')`:
  - `scope_type='global'` → `scope_value` must be None
  - `scope_type='project'` → `scope_value` must be a non-empty slug
  - `scope_type='language'` → `scope_value` must be a non-empty slug
  - On violation, raise Pydantic `ValidationError` which the service translates to `BrainError(ValidationError)`.

### `KnowledgeItemPatch`

New model for partial updates: every field `Optional`, no defaults, used by `KnowledgeService.update`. Immutable fields (`id`, `kind`, `created_at`) are rejected in the patch — if present, raise `ValidationError`. The model does **not** inherit from the full item; it is a deliberate separate type so extra fields can't leak through.

---

## 6. Service layer

### 6.1 `SecretScanner` (`scanner/secrets.py`)

Thin wrapper over `detect-secrets`. One instance per process, reused (constructing a `SecretsCollection` is non-trivial).

Public API:

```python
class SecretScanner:
    def __init__(self) -> None: ...                                  # loads default plugin set
    def scan(self, text: str) -> list[SecretHit]: ...                # returns plugin_name + line hint, NO value
    def assert_clean(self, text: str, *, field: str) -> None: ...    # raises SecretDetectedError
```

Critical invariants:
- `SecretHit` records `plugin_name` and `line` only. The scanner **never** stores or returns the secret value.
- `SecretDetectedError` carries `details={"hits": [{"plugin": ..., "line": ...}, ...]}` and the `field` (`content` / `fix` / `code` / etc.) that was scanned. Nothing more.
- Plugin set: `detect-secrets` defaults (AWS, JWT, private key, Slack, keyword, base64 high-entropy, Azure, GitHub, etc.). If a plugin turns out to false-positive frequently on real snippets during Phase 2 testing, it is disabled at the scanner constructor level — not at the request level. Allowlisting is deferred to Phase 5.

### 6.2 `ProjectIdResolver` (`scope/project_id.py`)

Single pure function, no state. This is intentionally not a class — it is a resolver, not a service.

```python
def resolve_project_id(
    *,
    mcp_roots: list[str] | None,
    cwd: Path,
) -> str:
```

Resolution order (from D-08 / D-09):
1. If `mcp_roots` is non-empty, use the first root; return `_slugify(root.name)`.
2. Walk from `cwd` up through parents; if a directory containing `.git` is found, return `_slugify(dir.name)`.
3. Otherwise return `_slugify(cwd.name)`.

`_slugify`: `strip().lower()`, whitespace and `_` → `-`, drop any character outside `[a-z0-9-]`, collapse `--+` to `-`, trim leading/trailing `-`.

Edge cases handled:
- `mcp_roots=[]` behaves like `None` (falls through).
- `cwd` at filesystem root: returns slug of the root name (typically empty slug — `_slugify` returns `"unknown"` as a final fallback rather than empty string).
- `.git` as a file (worktree) is treated the same as a directory.

Tested with a parametrized matrix.

### 6.3 `ScopeResolver` (`scope/resolver.py`)

Stateless helper with two static methods:

```python
class ScopeResolver:
    @staticmethod
    def build_filter(
        *,
        project_id: str | None,
        language: str | None,
    ) -> tuple[str, dict[str, Any]]: ...

    @staticmethod
    def apply_rule_override(
        rules: list[Rule],
        *,
        project_id: str | None,
    ) -> list[Rule]: ...
```

**`build_filter`** returns a SQL fragment and a params dict that the service splices into its `WHERE` clause. The fragment is always parenthesized so callers can `AND` it to other filters safely. If both `project_id` and `language` are `None`, it collapses to `scope_type = 'global'`.

**`apply_rule_override`** walks the list once, builds a `set` of `(topic)` pairs seen for `scope_type='project'`, then filters out any `scope_type='global'` rule whose topic is in that set. Rules without `topic` (both sides) are always kept — they never override and are never overridden (D-14). Order is preserved. Cost: O(n).

### 6.4 `KnowledgeService` (`service/knowledge.py`)

Facade that tool handlers call. Dependencies injected via constructor — no globals, no singletons.

```python
class KnowledgeService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        embedder: EmbeddingService,
        scanner: SecretScanner,
        scope_resolver: ScopeResolver,
    ) -> None: ...

    def create(self, item: KnowledgeItem) -> KnowledgeItem: ...
    def get(self, item_id: str) -> KnowledgeItem: ...
    def update(self, item_id: str, patch: KnowledgeItemPatch) -> KnowledgeItem: ...
    def delete(self, item_id: str) -> None: ...

    def list(
        self,
        *,
        kind: KnowledgeKind | None,
        scope_type: ScopeType | None,
        scope_value: str | None,
        tags: list[str] | None,
        project_id: str | None,
        limit: int = 50,
        offset: int = 0,
    ) -> KnowledgeList: ...

    def search(
        self,
        *,
        query: str,
        kind: KnowledgeKind | None,
        project_id: str | None,
    ) -> KnowledgeList: ...
```

#### Create flow

1. Scan relevant text fields through `SecretScanner.assert_clean`. For each kind:
   - `Rule`: `content`
   - `Snippet`: `content` (which holds the code)
   - `Decision`: `content`, `rationale`
   - `BugLesson`: `symptom`, `root_cause`, `fix`, `prevention` (if present)
2. Pydantic validates (validators from §5 run automatically; scope + field validators raise on violation).
3. `bctx.conn.transaction()`:
   - `INSERT INTO knowledge_items (...)` with `created_at = updated_at = now_utc_iso()`, `sync_id = new_uuid4()`, `content_hash = sha256(embed_text)` (where `embed_text` is the serialized content that goes to the embedder).
   - `INSERT INTO <extension_table>` with kind-specific fields.
   - Compute `vector = embedder.embed_document(embed_text)` (the embedder is still lazy — this is the call that may trigger the one-time model download).
   - `INSERT INTO vec_rowid_map` and `INSERT INTO knowledge_vec`.
   - FTS5 `AI` trigger from Phase 1 indexes content automatically — no explicit FTS insert needed.
4. Return the stored `KnowledgeItem` with all computed fields populated.

The phrase **"serialized content that goes to the embedder"** matters: a `BugLesson` has multiple text fields, and we need a deterministic serialization so `content_hash` matches `embed_text`. Planner decides the exact serialization, but it must be deterministic and stable across updates (same fields in same order, same separators).

#### Update flow

1. Load current row. If not found → `NotFoundError`.
2. Validate patch (reject immutable fields).
3. If `content`-equivalent fields changed, scan the new values before accepting them.
4. Merge patch over the current item. Compute new `embed_text` using the same serializer. Compare `sha256(new_embed_text)` against stored `content_hash`.
5. `transaction()`:
   - `UPDATE knowledge_items SET ... updated_at=now, sync_id=new_uuid4() [, content_hash=new_hash]`
   - `UPDATE <extension_table> SET ...`
   - If hash changed: `embedder.embed_document(new_embed_text)` → delete old vec row via `vec_rowid_map` → insert new vec row → update `vec_rowid_map`. FTS5 update trigger handles FTS.
6. Return updated item.

Metadata-only updates (tags, priority, topic, scope) never touch the embedder.

#### Delete flow

`DELETE FROM knowledge_items WHERE id=?`. The extension row and `vec_rowid_map` row cascade via FK. A trigger from Phase 1 (or explicit service-level cleanup — planner verifies) removes the `knowledge_vec` row referenced by the `vec_rowid_map` entry. FTS5 `AD` trigger handles FTS.

If no row matches → `NotFoundError`.

#### List flow

1. Build scope filter via `ScopeResolver.build_filter(project_id, language=scope_value if scope_type=='language' else None)`.
2. If an explicit `scope_type` / `scope_value` is passed, AND it on top of the scope filter (e.g., the caller wants only `scope_type='project'` rows even though the hard filter would allow global).
3. Build tag filter. Tags are stored in `knowledge_items.tags` as a JSON-serialized sorted list (e.g., `["async","python"]`). Use `json_each` if needed, or simpler: `tags LIKE '%"python"%' AND tags LIKE '%"async"%'` (AND semantics). Planner picks the approach; both are correct given canonical sorted storage.
4. `SELECT knowledge_items.*, <ext>.* FROM knowledge_items LEFT JOIN <ext> ON item_id=id WHERE <scope> AND <kind> AND <tags> ORDER BY updated_at DESC` — over-fetch deliberately (without `LIMIT`) up to a hard cap (500) so override can be applied before pagination.
5. Hydrate to Pydantic models (picking the right subclass by `kind`).
6. If `kind='rule'` (or no `kind`, and results contain rules), run `ScopeResolver.apply_rule_override(rules, project_id=project_id)`.
7. Apply `[offset : offset + limit]` slice.
8. Return `KnowledgeList(items=..., returned=len(slice), total_after_override=len(before_slice))`. We intentionally do not return a pre-override total — that would leak suppressed rules into the UI.

Clamp `limit` to `[1, 500]` inside the service.

#### Search flow (Phase 2 stub)

1. Build scope filter via `ScopeResolver`.
2. `WHERE (title LIKE '%<q>%' OR content LIKE '%<q>%') AND <scope>` with parameterized binding (never string concat the query).
3. Return up to 50 items ordered by `updated_at DESC`.

Phase 3 replaces the body with hybrid RRF without changing the signature. Tool clients see no difference.

### 6.5 Error taxonomy additions

In `errors.py`:

```python
class SecretDetectedError(BrainError):
    code = "SECRET_DETECTED"

class NotFoundError(BrainError):
    code = "NOT_FOUND"

class ValidationError(BrainError):
    code = "VALIDATION_ERROR"

class ScopeError(BrainError):
    code = "SCOPE_INVALID"
```

All carry `details: dict[str, Any]` and `message: str`. The MCP layer never sees a naked Python exception in the happy path — only `BrainError` subclasses — so the translator in §7 can be trivial.

---

## 7. MCP server layer

### 7.1 `BrainContext` (`mcp/context.py`)

Immutable dataclass passed through FastMCP's lifespan. Small, so constructing a `KnowledgeService` per request is cheap.

```python
@dataclass(frozen=True)
class BrainContext:
    conn: sqlite3.Connection
    embedder: EmbeddingService
    scanner: SecretScanner
    scope_resolver: ScopeResolver
    paths: BrainPaths
    lock: asyncio.Lock

    def service(self) -> KnowledgeService:
        return KnowledgeService(self.conn, self.embedder, self.scanner, self.scope_resolver)
```

The `asyncio.Lock` is the concurrency control from the earlier clarifying question — tool handlers take it before touching DB or embedder. Single-user workload; lock overhead is invisible.

### 7.2 Lifespan (`mcp/server.py`)

```python
@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[BrainContext]:
    configure_logging(stderr_only=True)
    paths = BrainPaths.from_env()
    if not paths.db_path.exists():
        raise BrainError(
            "Database not found. Run 'brain init' to create ~/.brain/brain.db.",
            code="DB_NOT_INITIALIZED",
        )
    conn = connect(paths.db_path)
    try:
        ctx = BrainContext(
            conn=conn,
            embedder=EmbeddingService(paths=paths),
            scanner=SecretScanner(),
            scope_resolver=ScopeResolver(),
            paths=paths,
            lock=asyncio.Lock(),
        )
        yield ctx
    finally:
        conn.close()

app = FastMCP("brain", lifespan=lifespan)

def main() -> None:
    try:
        app.run()
    except BrainError as e:
        # Lifespan failure: write to stderr, exit non-zero.
        logging.getLogger("brain_mcp").error(f"startup failed: {e}")
        sys.exit(2)
```

Notes:
- `configure_logging` runs inside the lifespan so even the "DB not initialized" error goes to stderr, never stdout. Stdout is reserved for the MCP JSON-RPC stream.
- The embedder is constructed eagerly (object) but the model is **not** downloaded until the first `embed_*` call — that is Phase 1's design.
- `main()` swallows `BrainError` with a clear stderr message and exits non-zero, so `brain-server` failure is visible to the user's MCP client (Claude Code, Inspector) as a clean stderr line instead of an opaque crash.
- No implicit auto-init: `brain init` is the only way to create the DB. The server error message explicitly tells the user what to run.

### 7.3 Tool handlers (`mcp/tools.py`)

All six tools follow the same pattern: take the lock, resolve project id, build the service, call it, translate errors.

```python
@app.tool(description=CAPTURE_DESC)
async def brain_capture(
    ctx: Context,
    kind: Literal["rule", "snippet", "decision", "bug_lesson"],
    title: str,
    content: str,
    scope_type: Literal["global", "project", "language"] = "global",
    scope_value: str | None = None,
    tags: list[str] | None = None,
    # kind-specific optionals:
    priority: int | None = None,
    topic: str | None = None,
    language: str | None = None,
    usage_context: str | None = None,
    decision_context: str | None = None,
    rationale: str | None = None,
    alternatives: str | None = None,
    symptom: str | None = None,
    root_cause: str | None = None,
    fix: str | None = None,
    prevention: str | None = None,
) -> dict:
    bctx: BrainContext = ctx.request_context.lifespan_context
    async with bctx.lock:
        try:
            project_id = resolve_project_id(mcp_roots=ctx.roots, cwd=Path.cwd())
            if scope_type == "project" and scope_value is None:
                scope_value = project_id
            item = _build_item_for_kind(kind, ...)
            saved = bctx.service().create(item)
            return saved.model_dump(mode="json")
        except BrainError as e:
            return _error_response(e)
```

Points worth capturing for the planner:

- The **capture tool is unified** (D-01). All kind-specific fields live on the single signature as optionals. `_build_item_for_kind` validates that the right fields were provided for the chosen kind and constructs the Pydantic subclass — any missing required field → `ValidationError` → JSON contract.
- **Project-scoped saves default to the current project.** If the user says "save this as a project rule" and passes `scope_type='project'` without `scope_value`, the handler fills it in with the resolved `project_id`. Callers can still pass an explicit `scope_value` to target a different project (unlikely, but supported — useful for admin flows).
- `brain_get`, `brain_update`, `brain_delete`, `brain_list`, `brain_search` follow the identical lock → service → translate shape. Each is ~15 lines.
- Tool descriptions are written as **LLM decision criteria** (MCP-06), not human reference. Each description answers "when should I call this?" in one or two sentences — e.g., `brain_capture`: "Save a new piece of knowledge so it survives across sessions. Use when the user says 'save this rule', 'remember this', 'add a snippet', 'log this decision', or 'write down this bug fix'. `kind` picks the type."

Final tool surface — **6 tools**. Headroom of 2 under the MCP-06 ceiling of 8 for future phases.

### 7.4 Error translator (`mcp/errors.py`)

```python
def error_response(err: BrainError) -> dict:
    return {
        "isError": True,
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {"code": err.code, "message": str(err), "details": err.details},
                    ensure_ascii=False,
                ),
            }
        ],
    }
```

- Every `BrainError` subclass defines `code` as a class attribute; the translator does not branch by type.
- `details` is always a `dict[str, Any]` — pre-populated by the service layer with whatever structured info the AI might act on (e.g., `{"hits": [{"plugin": "AWSKeyDetector", "line": 3}]}` for a secret detection).
- **Unexpected exceptions (not `BrainError`) are not caught here.** They propagate to FastMCP, which turns them into protocol `INTERNAL_ERROR`s and logs the full traceback to stderr. The server keeps running; the offending tool call fails with a generic error; the user sees the stderr log if they inspect logs. This preserves the "no silent failures" rule.

### 7.5 Session briefing Resource (`mcp/resources.py`)

```python
@app.resource("brain://session/{project_id}/context")
async def session_context(project_id: str, ctx: Context) -> str:
    bctx: BrainContext = ctx.request_context.lifespan_context
    async with bctx.lock:
        svc = bctx.service()
        global_rules = svc.list(
            kind=KnowledgeKind.RULE, scope_type=ScopeType.GLOBAL,
            project_id=project_id, limit=200,
        )
        project_rules = svc.list(
            kind=KnowledgeKind.RULE, scope_type=ScopeType.PROJECT,
            scope_value=project_id, project_id=project_id, limit=200,
        )
        return render_briefing_markdown(global_rules.items, project_rules.items)
```

`render_briefing_markdown` is a pure function in `mcp/resources.py` that emits a short Markdown doc:

```
# Brain: session context for <project_id>

## Global rules
- <title>: <content>
  (priority: <n>)

## Project rules (<project_id>)
- <title>: <content>
  (priority: <n>, topic: <topic>)
```

Phase 2 intentionally keeps this minimal: only rules, no decisions, no token budget, no recency weighting. All those enhancements land in Phase 3 (SESS-03). The Resource exists, returns correct data, respects scope hard-filter and the override from D-13 (because it calls `svc.list` which applies override internally).

No MCP Prompt in v1 (D-32).

---

## 8. Concurrency model

Locked answer from the brainstorm Q: single `asyncio.Lock` stored on `BrainContext`, taken by every tool handler and the session Resource before doing any work.

**Rationale:**
- FastMCP tool handlers are async, but the DB connection and the fastembed model are both synchronous and not thread-safe.
- Single user = single concurrent request in practice; the lock is almost always uncontended.
- One global lock is trivially correct. No lost updates, no sqlite "database is locked" errors, no risk of fastembed being called twice in parallel.
- Connection-per-request + embedder-only lock was rejected: zero observable benefit for a single-user local tool, measurable complexity cost.
- `asyncio.to_thread` alone does not solve the race — it still needs locks, and just moves work to a worker thread without solving the design question.

**Failure mode considered:** if a tool handler crashes mid-work while holding the lock, `async with` releases it on exception unwinding. Safe.

---

## 9. Test strategy

All tests live under `tests/`, mirroring `src/brain_mcp/` layout. Targets:

### 9.1 Unit (no DB, no MCP, no lock)

- `tests/scanner/test_secret_scanner.py`
  - known-AWS-key hit, known-JWT hit, known-private-key hit
  - clean content (a Python function, prose Markdown) → no hits
  - assert that errors never carry the secret value
  - plugin identification correct
- `tests/scope/test_project_id.py`
  - matrix of (`mcp_roots`, `.git` presence, `cwd`) scenarios
  - worktree `.git` file handled same as directory
  - fallback to `"unknown"` if everything else fails
- `tests/scope/test_resolver.py`
  - `build_filter` with and without `project_id` / `language`
  - `apply_rule_override`: project hides global with same topic, keeps global with different topic, keeps topic-less global
  - order preservation test
- `tests/db/test_schema_validators.py`
  - tag normalization (all lowercase, hyphenize, dedup, sort, idempotent on already-canonical input)
  - language normalization
  - topic normalization
  - scope validator matrix

### 9.2 Service integration (real SQLite, tmp_path, fake embedder)

- `tests/service/test_knowledge_service_crud.py`
  - create + get + delete for each kind
  - round-trip of all fields including JSON tags
  - delete cascades to extension table and `vec_rowid_map`
- `tests/service/test_knowledge_service_reembed.py`
  - content change triggers re-embed (fake embedder counts calls)
  - metadata-only update (tags, priority, topic) does NOT re-embed
  - `content_hash` stored after create, updated after re-embed
- `tests/service/test_knowledge_service_list.py`
  - scope hard filter (project A invisible to project B)
  - override: project rule with topic hides global rule with same topic
  - override: topic-less rules are always returned
  - tag AND filter
  - limit/offset; limit clamp to 500
  - order by `updated_at DESC`
- `tests/service/test_knowledge_service_search.py`
  - stub: title match, content match, scope respect

### 9.3 MCP end-to-end (FastMCP in-process)

Use FastMCP's in-process test harness (construct the app with the lifespan, call tools directly through the app's dispatch API — no stdio). Fake embedder continues to be injected into the lifespan via a helper fixture.

- `tests/mcp/test_server_lifespan.py`
  - server fails fast when DB missing, error message points at `brain init`
  - `configure_logging(stderr_only=True)` ran (assert no stdout handlers)
- `tests/mcp/test_server_capture.py`
  - happy path for each kind
  - SECRET_DETECTED blocks write; nothing persisted in DB
  - VALIDATION_ERROR on missing required fields for kind
- `tests/mcp/test_server_crud.py`
  - create → get → update → delete full lifecycle for rule (representative)
  - NOT_FOUND on get/update/delete of missing id
- `tests/mcp/test_server_list_and_search.py`
  - list respects scope + pagination
  - search stub returns structured result shape
- `tests/mcp/test_server_resource.py`
  - session briefing includes correct rules
  - override applied in the briefing
- `tests/mcp/test_server_error_contract.py`
  - every `BrainError` subclass round-trips into the `{code, message, details}` JSON shape
- `tests/mcp/test_tool_count.py`
  - `len(registered_tools) <= 8`

### 9.4 Migration

- `tests/db/test_migration_0002.py`
  - upgrade adds `rules.topic` and `knowledge_items.content_hash`
  - idempotent (running `upgrade head` twice)
  - downgrade removes them cleanly
  - re-upgrade works after downgrade

### 9.5 Scale

Projected new tests: ~30. Phase 1 ended at 46 green. Phase 2 target: **~76 green**, all fast, all offline (fake embedder, tmp SQLite).

---

## 10. Success criteria → test mapping

Direct map from the Phase 2 success criteria in ROADMAP.md §"Phase 2":

| # | Criterion | Test(s) |
|---|---|---|
| SC1 | Rule saved as `scope=project, project=brain` returned in `brain` context, never in another project | `tests/service/test_knowledge_service_list.py::test_scope_hard_filter`, `tests/mcp/test_server_list_and_search.py` |
| SC2 | Write path rejects secrets in ANY path (MCP or CLI) | `tests/mcp/test_server_capture.py::test_secret_blocks_capture`, `tests/scanner/test_secret_scanner.py` |
| SC3 | `brain_search` from MCP Inspector returns structured results | `tests/mcp/test_server_list_and_search.py::test_search_stub`, plus a manual Inspector session run at end of phase (documented in VERIFY.md) |
| SC4 | MCP server emits nothing to stdout | `tests/mcp/test_server_lifespan.py::test_stderr_only`, reusing Phase 1 logging assertion helpers |
| SC5 | Tool schema count ≤ 8 | `tests/mcp/test_tool_count.py` |

---

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `detect-secrets` false-positives block legitimate snippets during Phase 2 testing | Plugin-level disable at scanner constructor, allowlist deferred to Phase 5. Document any disabled plugin in the scanner module docstring with rationale. |
| FTS5 update trigger from Phase 1 races with explicit vec replacement on re-embed | Do all vec and FTS writes inside a single `transaction()`. FTS trigger fires on the `knowledge_items` UPDATE and sees the already-committed new row. Planner verifies trigger order in migration 0001. |
| Content serialization for hash drift between create and update | Single `serialize_for_embedding(item)` helper used in both create and update paths. Unit-tested with golden outputs. |
| Tool description over/underflow relative to MCP-06 ("LLM decision criteria, not human docs") | Descriptions go through a brief review against MCP-06 gate prompts during the plan or execute phase. Flag if any description reads like user documentation instead of a when-to-call prompt. |
| `BrainContext` lock held while embedder downloads the model on first call (~270MB, tens of seconds on first use) | Accept. This is a one-time event; the alternative (pre-download) violates "local-first, first run communicates download"  (EMB-06) and would happen at server start instead of first capture. User sees a stderr log line and a single slow first call; subsequent calls are fast. |
| Reading through existing Phase 1 migration without touching it causes subtle incompatibilities (e.g., FTS trigger assumes specific columns) | Migration 0002 is strictly additive. No column renames, no table drops, no trigger changes. Trigger behavior verified by the migration test (insert, update with content, observe FTS row). |

---

## 12. Out of scope (explicit)

Anything not on this list stays out of Phase 2.

- Hybrid retrieval (RET-01..06) — Phase 3. `brain_search` is a structured stub.
- Session briefing token budget, decision inclusion, recency weighting (SESS-03) — Phase 3.
- SessionStart hook shim for Claude Code (SESS-02) — Phase 3.
- CLI `brain save` command (CAPT-02) — Phase 4.
- Auto-capture Stop hook (AUTO-*) — Phase 4.
- Contradiction warning on write (LIFE-01) — Phase 5. Not the same as override.
- Curation CLI (`brain list/edit/delete/stats/reindex`) — Phase 5.
- Secret allowlist / per-request overrides — Phase 5.
- `uv tool install`, MCP registration docs, README quickstart — Phase 5.
- Sync-stable project ids (git remote based) — v2.
- MCP Prompt alternative to the Resource — v1 rejection; revisit only if a client lacks Resource support.

---

## 13. Ready-for-planning checklist

- [x] Module layout locked (§3)
- [x] Migration 0002 columns and index locked (§4)
- [x] Domain model fields and validators locked (§5)
- [x] Service interfaces and flows locked (§6)
- [x] MCP server wiring, tool surface, error contract locked (§7)
- [x] Concurrency model locked (§8)
- [x] Test strategy and projected counts locked (§9)
- [x] Success criteria mapped to concrete tests (§10)
- [x] Risks enumerated with mitigations (§11)
- [x] Out of scope explicit (§12)

Planner should read this document and `02-CONTEXT.md` together. CONTEXT locks *what*, this doc locks *how*. Anything not fixed by either is legitimately Claude's discretion during planning.

---

*Phase: 02-knowledge-crud-scoping-mcp-core*
*Brainstorm written: 2026-04-14*

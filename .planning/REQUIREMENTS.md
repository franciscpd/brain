# Requirements: brain

**Defined:** 2026-04-14
**Core Value:** Nunca mais precisar repetir manualmente as mesmas regras, preferências e padrões de código para a IA em cada novo projeto.

## v1 Requirements

Requirements para o release inicial. Cada um mapeia para uma fase do roadmap.

### Storage & Schema (STOR)

- [ ] **STOR-01**: Banco SQLite local criado em path configurável (default `~/.brain/brain.db`), em WAL mode com `busy_timeout` definido
- [ ] **STOR-02**: Schema `knowledge_items` com campos compartilhados (id UUID, kind, scope_type, scope_value, tags, content, created_at, updated_at, embedding_model_id, sync_id, synced_at, device_id)
- [ ] **STOR-03**: Tabelas de extensão específicas para cada tipo (`rules`, `snippets`, `decisions`, `bugs`) ligadas 1:1 ao `knowledge_items`
- [ ] **STOR-04**: Virtual table `sqlite-vec` (`knowledge_vec`) + bridge table (`vec_rowid_map`) para busca KNN por cosine distance
- [ ] **STOR-05**: Índice FTS5 sobre `content` + campos relevantes para busca textual exata e BM25
- [ ] **STOR-06**: Migrações gerenciadas via Alembic desde a migração inicial (batch mode para compatibilidade com SQLite)
- [ ] **STOR-07**: Schema preparado para sync futuro (PKs como UUIDs, timestamps ISO 8601 UTC, device_id, sync_id) — sem implementar sync

### Embedding Service (EMB)

- [ ] **EMB-01**: Embedding service embutido usando `fastembed` com modelo `nomic-ai/nomic-embed-text-v1.5` — sem dependência de Ollama ou API externa
- [ ] **EMB-02**: Modelo carregado lazy (primeira chamada), cache em `~/.brain/models/` via `FASTEMBED_CACHE_PATH`
- [ ] **EMB-03**: Chunker AST-aware para snippets de código (respeita fronteiras de função/classe), fallback para chunker por token count para texto livre
- [ ] **EMB-04**: Task prefixes aplicados corretamente (`search_document: ` no write, `search_query: ` no read) conforme exigência do nomic-embed
- [ ] **EMB-05**: Todo vetor gravado com `embedding_model_id` associado — upgrade de modelo no futuro reindexará apenas entradas afetadas
- [ ] **EMB-06**: Primeira execução comunica ao usuário o download do modelo (~270MB) de forma clara

### Knowledge CRUD (KNOW)

- [ ] **KNOW-01**: Criar, ler, atualizar e deletar **regras pessoais** (type: `rule`) com campos: título, conteúdo, tags, escopo, prioridade
- [ ] **KNOW-02**: Criar, ler, atualizar e deletar **snippets/soluções reutilizáveis** (type: `snippet`) com campos: título, código, linguagem, contexto de uso, tags, escopo
- [ ] **KNOW-03**: Criar, ler, atualizar e deletar **decisões arquiteturais** (type: `decision`) com campos: título, contexto, decisão, rationale, alternativas consideradas, escopo
- [ ] **KNOW-04**: Criar, ler, atualizar e deletar **lições de bugs/erros** (type: `bug_lesson`) com campos: título, sintoma, causa raiz, correção, prevenção, tags, escopo
- [ ] **KNOW-05**: Listar entries por tipo, filtrados por escopo (global/project/language) e tags
- [ ] **KNOW-06**: Todo write passa por scanner de secrets (`detect-secrets` ou equivalente) — write é bloqueado se credenciais forem detectadas

### Scoping (SCOPE)

- [ ] **SCOPE-01**: Três tipos de escopo suportados: `global` (vale em qualquer contexto), `project` (vale apenas no projeto identificado), `language` (vale para linguagem específica)
- [ ] **SCOPE-02**: Filtros de recuperação aplicam escopo como filtro duro (não só ranking) — regras de project A nunca vazam para project B
- [ ] **SCOPE-03**: Regras `global` podem ser sobrescritas por regras `project` do mesmo tópico (override via tag/topic)
- [ ] **SCOPE-04**: Identificação de projeto atual via MCP roots ou working directory como fallback documentado

### MCP Server (MCP)

- [ ] **MCP-01**: Servidor MCP stdio funcional usando SDK oficial (`mcp` com FastMCP), sem `print()` no stream JSON-RPC
- [ ] **MCP-02**: Lifespan pattern para inicialização de DB e lazy-load do modelo de embeddings
- [ ] **MCP-03**: MCP Tools expostos para captura (uma tool por tipo de conhecimento ou uma tool unificada com parâmetro `kind`)
- [ ] **MCP-04**: MCP Tool `brain_search` para busca sob demanda pela IA — com descrição clara o suficiente para a IA saber quando chamar
- [ ] **MCP-05**: MCP Resource ou Prompt expondo regras relevantes ao projeto atual, para injeção no início da sessão
- [ ] **MCP-06**: Descrições de tools seguem boas práticas (critérios de decisão para LLM, não documentação humana) — meta de < 8 tools no total para minimizar overhead de schema

### Retrieval (RET)

- [ ] **RET-01**: Busca estruturada por tipo + tags + escopo + substring textual (rápida, exata)
- [ ] **RET-02**: Busca semântica via `sqlite-vec` KNN para snippets/decisões/bugs
- [ ] **RET-03**: Retrieval híbrido: FTS5 (BM25) + vector search com fusão de resultados (RRF ou weighted sum)
- [ ] **RET-04**: Recency decay aplicado ao ranking (entradas recentes com leve boost; valores por tipo configuráveis)
- [ ] **RET-05**: Regras são recuperadas principalmente por lookup estruturado (não dependem de RAG vetorial para o caminho principal)
- [ ] **RET-06**: Limite configurável de resultados e tamanho máximo de payload — evita poisoning do context window do cliente

### Session Context Injection (SESS)

- [ ] **SESS-01**: Endpoint/resource que retorna briefing contextual do projeto atual (regras globais + regras do projeto + decisões relevantes)
- [ ] **SESS-02**: Injeção no início da sessão Claude Code via SessionStart hook ou MCP Resource (o que o cliente suportar — escolha documentada por cliente)
- [ ] **SESS-03**: Briefing formatado em Markdown conciso, respeitando orçamento de tokens configurável
- [ ] **SESS-04**: Validação manual em Claude Code CLI de que regras são carregadas e respeitadas pela IA

### Capture — Manual (CAPT)

- [ ] **CAPT-01**: Captura manual via MCP tools — a IA pode salvar uma regra/snippet/decisão/bug quando o usuário pede
- [ ] **CAPT-02**: CLI command `brain save` para captura direta do usuário sem passar pela IA (`brain save rule "use ruff format"`)
- [ ] **CAPT-03**: Workflow de captura leva <10 segundos entre intenção e confirmação ("zero atrito")

### Capture — Automática (AUTO)

- [ ] **AUTO-01**: Hook Stop do Claude Code extrai candidatos (regras declaradas, snippets úteis, decisões tomadas, bugs resolvidos) do transcript da sessão
- [ ] **AUTO-02**: Candidatos passam por quality gate (secret scan + dedup semântico + relevância mínima) antes de serem salvos
- [ ] **AUTO-03**: Auto-capture é opt-in por projeto — desabilitado por padrão até o usuário confiar na destilação
- [ ] **AUTO-04**: Usuário pode revisar candidatos antes da persistência em modo "confirm before save"

### Lifecycle & Quality (LIFE)

- [ ] **LIFE-01**: Detecção de contradição no write — se nova regra conflita com regra existente no mesmo escopo, alertar o usuário (não auto-resolver)
- [ ] **LIFE-02**: CLI command `brain list/edit/delete` para curadoria manual
- [ ] **LIFE-03**: CLI command `brain stats` mostra contagens por tipo, escopo, tamanho do índice
- [ ] **LIFE-04**: CLI command `brain reindex` regera embeddings (útil ao trocar de modelo futuramente)

### Packaging & Install (PKG)

- [ ] **PKG-01**: Projeto empacotado com `pyproject.toml` + `uv`, entrypoint console_script (`brain-server`, `brain`)
- [ ] **PKG-02**: Instalação via `uv tool install brain-server` ou `pip install brain-server`
- [ ] **PKG-03**: Comando de registro MCP documentado para Claude Code, Claude Desktop, Cursor/Windsurf, e SDK direto
- [ ] **PKG-04**: README com quickstart: instalar → registrar → salvar primeira regra → ver regra ser usada em nova sessão

## v2 Requirements

Deferred para releases futuros. Reconhecidos mas fora do escopo atual.

### Sync & Multi-Device (SYNC)

- **SYNC-01**: Sync entre múltiplas máquinas do mesmo usuário (schema já preparado)
- **SYNC-02**: Resolução de conflitos em sync (last-write-wins vs merge)
- **SYNC-03**: Modo cliente conectando a brain server remoto

### Collaboration (COLL)

- **COLL-01**: Compartilhamento read-only de conhecimento entre devs de um time
- **COLL-02**: Export/import de conjuntos de regras curados

### Advanced Capture (ADV)

- **ADV-01**: Auto-capture usando PostToolUse hooks com heurísticas mais finas
- **ADV-02**: Sugestões proativas ao usuário ("salvar esta regra?") baseadas em padrões repetidos
- **ADV-03**: Mineração automática de repositórios existentes para extrair regras implícitas

### Cloud Embeddings (CLOUD)

- **CLOUD-01**: Opção de usar OpenAI/Voyage embeddings para qualidade máxima (configurável, não default)
- **CLOUD-02**: Modelo especializado em código (`nomic-embed-code`, `voyage-code-3`) como alternativa ao general-purpose

### UX (UX)

- **UX-01**: Interface web/TUI para curadoria visual do conhecimento
- **UX-02**: Diff visual ao detectar contradição entre regras

## Out of Scope

Exclusões explícitas. Documentadas para prevenir scope creep.

| Feature | Reason |
|---------|--------|
| Documentação de projeto (README, docs de API) | Isso mora no repositório; brain não substitui docs formais |
| Sistema de tickets/tasks (Linear/Jira) | Brain não gerencia trabalho pendente, só conhecimento consolidado |
| Memória de conversação / resumos de sessão | Brain é para padrões acionáveis, não para recordação de chats |
| Base de conhecimento genérica (Notion/Obsidian) | Foco estrito em código/desenvolvimento |
| Sync em cloud no v1 | Schema preparado, mas implementação fica para v2 |
| Multi-usuário / compartilhamento de time no v1 | Escopo v1 é estritamente pessoal |
| Integração com GSD | Brain é cross-tool; GSD é workflow de projeto |
| Cloud embeddings no v1 | Local-first é decisão; cloud vira opção futura |
| Interface web/GUI no v1 | v1 é MCP + CLI; UI é pós-v1 |
| TTL/expiração automática de conhecimento | Regras pessoais não expiram; expiração baseada em tempo é anti-padrão para este uso |
| Auto-capture ligado por padrão | Quality gates precisam amadurecer; começa opt-in |

## Traceability

Será populado pelo gsd-roadmapper após criação do ROADMAP.md.

| Requirement | Phase | Status |
|-------------|-------|--------|
| _(pending roadmap)_ | — | Pending |

**Coverage:**
- v1 requirements: 48 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 48 ⚠️

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after initial definition*

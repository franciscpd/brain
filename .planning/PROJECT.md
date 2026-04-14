# brain

## What This Is

`brain` é um servidor MCP local-first que funciona como um "cérebro" compartilhado para Claude e outras IAs — armazenando e recuperando padrões de código (regras pessoais, snippets, decisões, lições de bugs) via RAG, de modo que o conhecimento acumulado em um projeto seja automaticamente reutilizável em todos os outros.

É uma ferramenta pessoal de desenvolvedor: um só usuário, múltiplas IAs clientes, conhecimento que atravessa projetos.

## Core Value

**Nunca mais precisar repetir manualmente as mesmas regras, preferências e padrões de código para a IA em cada novo projeto.** Se o brain fizer isso bem, tudo o mais é bônus.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Servidor MCP funcional expondo tools de captura e recuperação de conhecimento
- [ ] Armazenamento local-first (SQLite + vector store embutido) pronto para sync futuro
- [ ] Embeddings locais embutidos (sem dependência de Ollama/API externa) — funciona em qualquer máquina após instalação
- [ ] Captura e recuperação de **regras pessoais** (prioridade #1 — ataca a dor principal)
- [ ] Captura e recuperação de **snippets/soluções reutilizáveis**
- [ ] Captura e recuperação de **decisões arquiteturais**
- [ ] Captura e recuperação de **lições de bugs/erros**
- [ ] Captura híbrida: automática (via hooks do Claude Code) + manual (via comandos/tools explícitos)
- [ ] Recuperação híbrida: contexto relevante injetado no início da sessão + busca sob demanda via tool call
- [ ] Funciona como cliente MCP em Claude Code (CLI), Claude Desktop, Cursor/Windsurf e SDK direto
- [ ] Escopo do conhecimento isolável por projeto/global (regras globais vs contextuais)
- [ ] Experiência de captura sem atrito — salvar algo leva segundos

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Documentação de projeto (README, docs de API)** — isso mora no repositório, brain não substitui docs formais
- **Sistema de tickets/tasks (Linear/Jira)** — brain não gerencia trabalho pendente, só conhecimento consolidado
- **Memória de conversação/resumos de sessão** — brain não guarda histórico de chats; existe para padrões acionáveis, não para recordação contextual
- **Base de conhecimento genérica (Notion/Obsidian)** — foco estrito em código e desenvolvimento; não é lugar para anotações de vida/pesquisa/reuniões
- **Sync em nuvem no v1** — schema preparado para sync, mas a implementação fica para depois de validar uso pessoal
- **Multi-usuário / compartilhamento de time** — escopo v1 é estritamente pessoal
- **Integração com GSD (get-shit-done)** — brain é cross-tool e independente; GSD é workflow de um projeto. Manter separados.
- **Cloud embeddings (OpenAI/Voyage) no v1** — custo e qualidade não justificam dependência externa para uso pessoal; pode virar opção futura
- **Interface web/GUI** — v1 é MCP + CLI. Qualquer UI é posterior.

## Context

**Motivação:** O usuário percebe que repete as mesmas instruções para a IA em cada novo projeto ("use TypeScript strict", "não use `any`", convenções de commit, estrutura de diretórios, etc). Cada projeto novo começa do zero em termos de contexto de preferências. Quando acontece um bug que já foi resolvido antes em outro projeto, a IA não tem como lembrar. Quando uma solução elegante aparece, ela fica presa no projeto onde nasceu.

**Ecossistema técnico:**
- MCP (Model Context Protocol) já é suportado nativamente por Claude Code, Claude Desktop, Cursor, Windsurf e outros IDEs — um servidor MCP serve todos esses clientes com o mesmo código
- RAG com embeddings locais amadureceu em 2024-2025: modelos como `nomic-embed-text` rodam em CPU com qualidade excelente
- Bibliotecas como `fastembed` permitem rodar embeddings sem servidor Ollama separado (modelo carregado no próprio processo)
- SDK MCP oficial para Python é maduro e bem documentado

**Experiência prévia relevante:**
- Usuário já usa Claude Code intensivamente em múltiplos projetos
- Já sente na prática a dor de repetir CLAUDE.md similares
- Quer ferramenta de uso diário, não experimento acadêmico

## Constraints

- **Tech stack**: Python — SDK MCP oficial maduro, ecossistema ML/embeddings completo (fastembed, sentence-transformers), instalação simples via pip/uv
- **Embeddings**: Locais embutidos, sem dependência de Ollama ou API externa — requisito: "funciona em qualquer máquina"
- **Armazenamento**: Local-first (SQLite + vector index embutido); schema deve ser versionado e preparado para sync futuro
- **Privacidade**: Nenhum dado sai da máquina do usuário no v1 — requisito de confiança e de zero custo operacional
- **Escopo v1**: Estritamente pessoal (um usuário) — centenas a poucos milhares de entradas; otimização para multi-usuário fica para depois
- **Compatibilidade MCP**: Deve seguir protocolo MCP padrão para funcionar em Claude Code, Desktop, Cursor, Windsurf e SDK sem código específico por cliente
- **Setup**: Instalação e configuração devem ser simples o bastante para uso diário — idealmente `pip install` + comando de registro MCP

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Local-first com SQLite + embeddings embutidos | Privacidade, zero custo, funciona offline, combina com escopo pessoal; sync pode ser adicionado sem mudar modelo de dados | — Pending |
| Python como linguagem de implementação | SDK MCP oficial maduro + ecossistema ML/embeddings mais completo + instalação trivial via pip/uv | — Pending |
| Embeddings locais embutidos via fastembed/Candle (não Ollama) | Zero dependência externa — usuário instala e roda, sem precisar ter Ollama rodando | — Pending |
| nomic-embed-text como modelo default | Sweet spot comunidade RAG 2025: ~270MB, qualidade excelente para código+texto, roda em CPU | — Pending |
| 4 tipos de conhecimento distintos (regras, snippets, decisões, bugs) | Cada tipo tem padrão de uso diferente; modelar explicitamente evita "bag genérica de textos" | — Pending |
| Regras estruturadas + RAG vetorial em camadas | Regras são poucas e curadas — recuperação exata/tags basta; RAG agrega valor para os outros 3 tipos | — Pending |
| Captura híbrida (automática via hooks + manual via comandos) | Captura automática pega o que passa despercebido; manual garante curadoria intencional | — Pending |
| Recuperação híbrida (contexto inicial + tool call sob demanda) | Contexto inicial elimina fricção para regras globais; tool call deixa IA buscar quando realmente precisa | — Pending |
| Brain independente do GSD | Brain é cross-tool, GSD é workflow de projeto — misturar escopos prejudicaria ambos | — Pending |
| v1 pessoal; sync/multi-user é pós-v1 | Validar valor de uso pessoal antes de pagar complexidade de sync | — Pending |

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

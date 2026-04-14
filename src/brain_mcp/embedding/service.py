"""EmbeddingService with type-dispatched embedder routing.

Phase 1 ships a single default embedder; every KnowledgeKind routes to it.
The dispatch table is here on day one so a future code-specialized model for
KnowledgeKind.SNIPPET is a one-line change, not a refactor of callers.
"""

from typing import Protocol

from brain_mcp.db.schema import KnowledgeKind


class Embedder(Protocol):
    """Abstract embedder — implemented by FastEmbedEmbedder and test fakes."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    @property
    def model_id(self) -> str: ...
    @property
    def dimension(self) -> int: ...


class EmbeddingService:
    """Type-dispatched embedding facade over one or more Embedder implementations."""

    def __init__(self, default_embedder: Embedder) -> None:
        self._default = default_embedder
        self._dispatch: dict[KnowledgeKind, Embedder] = {
            KnowledgeKind.RULE: default_embedder,
            KnowledgeKind.SNIPPET: default_embedder,
            KnowledgeKind.DECISION: default_embedder,
            KnowledgeKind.BUG_LESSON: default_embedder,
        }

    def _route(self, kind: KnowledgeKind) -> Embedder:
        return self._dispatch.get(kind, self._default)

    def embed_document(
        self, text: str, *, kind: KnowledgeKind
    ) -> tuple[list[float], str]:
        embedder = self._route(kind)
        prefixed = f"search_document: {text}"
        vector = embedder.embed_documents([prefixed])[0]
        return vector, embedder.model_id

    def embed_query(
        self, text: str, *, kind: KnowledgeKind
    ) -> tuple[list[float], str]:
        embedder = self._route(kind)
        prefixed = f"search_query: {text}"
        vector = embedder.embed_query(prefixed)
        return vector, embedder.model_id

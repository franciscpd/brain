"""Tests for brain_mcp.embedding.service — type dispatch and task prefixes."""

from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.service import EmbeddingService


class RecordingEmbedder:
    dimension = 768
    model_id = "recording-v1"

    def __init__(self) -> None:
        self.embed_document_calls: list[list[str]] = []
        self.embed_query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_document_calls.append(list(texts))
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embed_query_calls.append(text)
        return [0.0] * self.dimension


def test_embed_document_applies_search_document_prefix() -> None:
    recorder = RecordingEmbedder()
    service = EmbeddingService(default_embedder=recorder)
    vec, model_id = service.embed_document("always ruff format", kind=KnowledgeKind.RULE)
    assert model_id == "recording-v1"
    assert len(vec) == 768
    assert recorder.embed_document_calls == [["search_document: always ruff format"]]


def test_embed_query_applies_search_query_prefix() -> None:
    recorder = RecordingEmbedder()
    service = EmbeddingService(default_embedder=recorder)
    _vec, model_id = service.embed_query("ruff", kind=KnowledgeKind.RULE)
    assert model_id == "recording-v1"
    assert recorder.embed_query_calls == ["search_query: ruff"]


def test_dispatch_routes_every_kind_to_default_in_phase_1() -> None:
    recorder = RecordingEmbedder()
    service = EmbeddingService(default_embedder=recorder)
    for kind in KnowledgeKind:
        service.embed_document(f"{kind.value} body", kind=kind)
    assert len(recorder.embed_document_calls) == len(KnowledgeKind)

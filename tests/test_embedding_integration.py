"""End-to-end integration test for the real fastembed model.

Marked `slow` — downloads the real quantized nomic-embed-text-v1.5 model
(~70MB) on first run. Skipped by default; run with `pytest -m slow`.
"""

from pathlib import Path

import pytest

from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.models import DEFAULT_MODEL, FastEmbedEmbedder
from brain_mcp.embedding.service import EmbeddingService


@pytest.mark.slow
def test_real_fastembed_roundtrip(tmp_path: Path) -> None:
    embedder = FastEmbedEmbedder(DEFAULT_MODEL, cache_dir=tmp_path / "models")
    service = EmbeddingService(default_embedder=embedder)

    doc_vec, doc_model_id = service.embed_document(
        "use ruff format before every commit",
        kind=KnowledgeKind.RULE,
    )
    query_vec, query_model_id = service.embed_query(
        "format rule",
        kind=KnowledgeKind.RULE,
    )

    assert doc_model_id == DEFAULT_MODEL.fastembed_id
    assert query_model_id == DEFAULT_MODEL.fastembed_id
    assert len(doc_vec) == 768
    assert len(query_vec) == 768
    assert any(abs(x) > 0.0 for x in doc_vec)
    assert any(abs(x) > 0.0 for x in query_vec)

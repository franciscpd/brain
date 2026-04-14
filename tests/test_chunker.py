"""Tests for brain_mcp.embedding.chunker."""

import pytest

from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.chunker import Chunk, WholeTextChunker


@pytest.mark.parametrize("kind", list(KnowledgeKind))
def test_whole_text_chunker_returns_single_chunk(kind: KnowledgeKind) -> None:
    chunker = WholeTextChunker()
    chunks = chunker.chunk("hello world", kind=kind)
    assert chunks == [Chunk(text="hello world", index=0)]


def test_whole_text_chunker_preserves_large_input() -> None:
    text = "a" * 10_000
    chunker = WholeTextChunker()
    chunks = chunker.chunk(text, kind=KnowledgeKind.SNIPPET)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].index == 0

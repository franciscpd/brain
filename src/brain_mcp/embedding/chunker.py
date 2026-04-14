"""Chunker interface and the default WholeTextChunker implementation.

The WholeTextChunker produces exactly one chunk per entry. AST-aware chunking
is a deferred work item for a later phase; the interface stays the same.
"""

from dataclasses import dataclass
from typing import Protocol

from brain_mcp.db.schema import KnowledgeKind


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int


class Chunker(Protocol):
    """Splits knowledge content into embedding-ready chunks."""

    def chunk(self, text: str, *, kind: KnowledgeKind) -> list[Chunk]: ...


class WholeTextChunker:
    """Single-chunk strategy: the entire content becomes one embedding."""

    def chunk(self, text: str, *, kind: KnowledgeKind) -> list[Chunk]:
        return [Chunk(text=text, index=0)]

"""Embedding layer — chunker, embedder, and type-dispatched service."""

from brain_mcp.embedding.chunker import Chunk, Chunker, WholeTextChunker
from brain_mcp.embedding.models import DEFAULT_MODEL, FULL_MODEL, FastEmbedEmbedder
from brain_mcp.embedding.service import Embedder, EmbeddingService

__all__ = [
    "DEFAULT_MODEL",
    "FULL_MODEL",
    "Chunk",
    "Chunker",
    "Embedder",
    "EmbeddingService",
    "FastEmbedEmbedder",
    "WholeTextChunker",
]

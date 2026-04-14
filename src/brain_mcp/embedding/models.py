"""Embedding model specs and the lazy-loaded FastEmbedEmbedder wrapper.

DEFAULT_MODEL is the quantized nomic-embed-text-v1.5 (~70MB). FULL_MODEL is
the full-precision variant (~274MB), opt-in via `brain init --full-model`.

FastEmbedEmbedder implements the Embedder protocol (see service.py) and loads
the model lazily on first embed call. The model cache directory is passed in
so tests can point at a tmp_path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastembed import TextEmbedding

from brain_mcp.errors import EmbeddingError


@dataclass(frozen=True)
class EmbeddingModelSpec:
    fastembed_id: str
    dimension: int
    variant: Literal["quantized", "full"]


DEFAULT_MODEL = EmbeddingModelSpec(
    fastembed_id="nomic-ai/nomic-embed-text-v1.5-Q",
    dimension=768,
    variant="quantized",
)

FULL_MODEL = EmbeddingModelSpec(
    fastembed_id="nomic-ai/nomic-embed-text-v1.5",
    dimension=768,
    variant="full",
)


class FastEmbedEmbedder:
    """Lazy-loaded fastembed wrapper implementing the Embedder protocol."""

    def __init__(self, spec: EmbeddingModelSpec, cache_dir: Path) -> None:
        self._spec = spec
        self._cache_dir = cache_dir
        self._model: TextEmbedding | None = None

    def _ensure_loaded(self) -> TextEmbedding:
        if self._model is None:
            try:
                self._model = TextEmbedding(
                    model_name=self._spec.fastembed_id,
                    cache_dir=str(self._cache_dir),
                )
            except Exception as e:
                raise EmbeddingError(
                    f"Failed to load embedding model {self._spec.fastembed_id}: {e}"
                ) from e
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_loaded()
        return [list(vec) for vec in model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        model = self._ensure_loaded()
        return list(next(iter(model.query_embed(text))))

    @property
    def model_id(self) -> str:
        return self._spec.fastembed_id

    @property
    def dimension(self) -> int:
        return self._spec.dimension

"""Exception hierarchy for brain-mcp.

All errors inherit from BrainError. CLI top-level handlers catch BrainError
and present friendly messages; internal code raises and lets exceptions bubble.
"""


class BrainError(Exception):
    """Base class for all brain-mcp errors."""


class ConfigError(BrainError):
    """Configuration or environment setup error."""


class SchemaError(BrainError):
    """Database schema error (missing table, invalid state, extension load failure)."""


class MigrationError(BrainError):
    """Alembic migration failure."""


class EmbeddingError(BrainError):
    """Embedding service failure (model load, inference, etc.)."""


class VectorStoreError(BrainError):
    """sqlite-vec or vector storage failure."""

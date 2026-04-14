"""Exception hierarchy for brain-mcp.

All errors inherit from BrainError. CLI top-level handlers catch BrainError
and present friendly messages; internal code raises and lets exceptions bubble.
"""


class BrainError(Exception):
    """Base class for all brain-mcp errors."""

    code: str = "BRAIN_ERROR"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.details: dict = details if details is not None else {}

    def with_code(self, code: str) -> "BrainError":
        """Override the error code on this instance (fluent style)."""
        self.code = code
        return self


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


class SecretDetectedError(BrainError):
    """Raised when secret scanning detects sensitive content in a knowledge entry."""

    code = "SECRET_DETECTED"


class NotFoundError(BrainError):
    """Raised when a requested knowledge entry does not exist."""

    code = "NOT_FOUND"


class ValidationError(BrainError):
    """Raised when input fails schema or business-rule validation."""

    code = "VALIDATION_ERROR"


class ScopeError(BrainError):
    """Raised when a scope specification is invalid or incomplete."""

    code = "SCOPE_INVALID"

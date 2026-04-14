from __future__ import annotations

from brain_mcp.errors import (
    BrainError,
    NotFoundError,
    ScopeError,
    SecretDetectedError,
    ValidationError,
)


def test_secret_detected_has_code_and_details() -> None:
    err = SecretDetectedError(
        "Secret detected in content",
        details={"hits": [{"plugin": "AWSKeyDetector", "line": 3}]},
    )
    assert isinstance(err, BrainError)
    assert err.code == "SECRET_DETECTED"
    assert err.details["hits"][0]["plugin"] == "AWSKeyDetector"


def test_not_found_error() -> None:
    err = NotFoundError("missing id xyz", details={"id": "xyz"})
    assert err.code == "NOT_FOUND"
    assert isinstance(err, BrainError)


def test_validation_error() -> None:
    err = ValidationError("missing required field", details={"field": "title"})
    assert err.code == "VALIDATION_ERROR"


def test_scope_error() -> None:
    err = ScopeError(
        "scope=language requires scope_value",
        details={"scope_type": "language"},
    )
    assert err.code == "SCOPE_INVALID"


def test_with_code_helper_overrides_class_code() -> None:
    err = BrainError("generic", details={}).with_code("CUSTOM")
    assert err.code == "CUSTOM"

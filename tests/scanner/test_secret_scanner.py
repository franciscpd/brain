from __future__ import annotations

import pytest

from brain_mcp.errors import SecretDetectedError
from brain_mcp.scanner.secrets import SecretScanner


@pytest.fixture(scope="module")
def scanner() -> SecretScanner:
    return SecretScanner()


def test_clean_python_snippet_passes(scanner: SecretScanner) -> None:
    scanner.assert_clean(
        "def add(a, b):\n    return a + b",
        field="content",
    )  # no raise


def test_aws_key_is_detected(scanner: SecretScanner) -> None:
    fake_aws_key = "AKIA" + "I" * 16
    with pytest.raises(SecretDetectedError) as ei:
        scanner.assert_clean(
            f"export AWS_ACCESS_KEY_ID={fake_aws_key}",
            field="content",
        )
    err = ei.value
    assert err.code == "SECRET_DETECTED"
    # Critical invariant: the secret value must NEVER appear in error message or details.
    assert fake_aws_key not in str(err)
    assert fake_aws_key not in str(err.details)
    # Hits list identifies a plugin.
    assert err.details["hits"]
    assert all("plugin" in h for h in err.details["hits"])


def test_private_key_is_detected(scanner: SecretScanner) -> None:
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBA...\n-----END RSA PRIVATE KEY-----"
    with pytest.raises(SecretDetectedError):
        scanner.assert_clean(pem, field="content")


def test_scan_returns_hits_list_for_inspection(scanner: SecretScanner) -> None:
    fake_aws_key = "AKIA" + "J" * 16
    hits = scanner.scan(f"KEY={fake_aws_key}")
    assert hits, "scan should return at least one hit"
    for hit in hits:
        assert "plugin" in hit
        assert "line" in hit

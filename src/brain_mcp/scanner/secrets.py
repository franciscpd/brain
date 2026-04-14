"""detect-secrets wrapper for brain-mcp write paths.

Never stores, logs, or returns secret VALUES — only plugin name + line hint.
"""

from __future__ import annotations

import os
import tempfile
from typing import TypedDict

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings

from brain_mcp.errors import SecretDetectedError


class SecretHit(TypedDict):
    plugin: str
    line: int


class SecretScanner:
    """Single instance per process, reused across requests."""

    def scan(self, text: str) -> list[SecretHit]:
        # SecretsCollection.scan_string does not exist in detect-secrets 1.5.0;
        # using scan_file via a temp file as the only available scan API.
        collection = SecretsCollection()
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(text)
            tmp_path = f.name
        try:
            with default_settings():
                collection.scan_file(tmp_path)
        finally:
            os.unlink(tmp_path)
        hits: list[SecretHit] = []
        for _filename, secret in collection:
            hits.append({"plugin": secret.type, "line": int(secret.line_number or 0)})
        return hits

    def assert_clean(self, text: str, *, field: str) -> None:
        hits = self.scan(text)
        if hits:
            raise SecretDetectedError(
                f"Secret detected in field '{field}'",
                details={"field": field, "hits": hits},
            )

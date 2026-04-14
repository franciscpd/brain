"""Canonical text representation + hash for knowledge items.

The serialized text is what gets embedded (FTS5 + sqlite-vec). The hash is
computed on the same string, so update-time hash comparison tracks changes
in embedding input exactly — metadata-only updates (tags, priority) never
change the hash.
"""

from __future__ import annotations

import hashlib

from brain_mcp.db.schema import (
    BugLesson,
    Decision,
    KnowledgeItemBase,
    Rule,
    Snippet,
)


def serialize_for_embedding(item: KnowledgeItemBase) -> str:
    """Return the canonical string used for embedding + content_hash."""
    body = _body_for_kind(item)
    return f"{item.title}\n\n{body}"


def content_hash_for(item: KnowledgeItemBase) -> str:
    """SHA-256 hex digest of the serialized embedding text."""
    return hashlib.sha256(serialize_for_embedding(item).encode()).hexdigest()


def _body_for_kind(item: KnowledgeItemBase) -> str:
    if isinstance(item, Rule):
        return item.content
    if isinstance(item, Snippet):
        return f"language: {item.language}\n\n{item.content}"
    if isinstance(item, Decision):
        lines = [item.content]
        if item.context:
            lines.append(f"context: {item.context}")
        if item.rationale:
            lines.append(f"rationale: {item.rationale}")
        if item.alternatives:
            lines.append(f"alternatives: {item.alternatives}")
        return "\n\n".join(lines)
    if isinstance(item, BugLesson):
        lines = [
            f"symptom: {item.symptom}",
            f"root_cause: {item.root_cause}",
            f"fix: {item.fix}",
        ]
        if item.prevention:
            lines.append(f"prevention: {item.prevention}")
        return "\n\n".join(lines)
    raise TypeError(f"unknown kind: {type(item)}")

"""String normalization primitives for brain-mcp domain models."""

from __future__ import annotations

import re

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


def slugify(value: str) -> str:
    """Lowercase, replace runs of non-alphanumerics with '-', trim dashes."""
    lowered = value.strip().lower()
    hyphenized = _NON_SLUG.sub("-", lowered)
    collapsed = _MULTI_DASH.sub("-", hyphenized)
    return collapsed.strip("-")


def normalize_tag(tag: str) -> str:
    return slugify(tag)


def normalize_topic(topic: str | None) -> str | None:
    if topic is None:
        return None
    normalized = slugify(topic)
    return normalized or None


def normalize_language(lang: str) -> str:
    return lang.strip().lower()

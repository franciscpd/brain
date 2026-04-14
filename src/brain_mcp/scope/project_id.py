"""Resolve a stable project identifier from MCP roots or filesystem."""

from __future__ import annotations

from pathlib import Path

from brain_mcp.db.normalize import slugify


def resolve_project_id(
    *,
    mcp_roots: list[str] | None,
    cwd: Path,
) -> str:
    """Resolution order:

    1. If ``mcp_roots`` is non-empty, return slugify(first_root.name).
    2. Walk from cwd upward; if a directory contains .git (dir or file),
       return slugify(that_dir.name).
    3. Return slugify(cwd.name).
    4. If everything slugifies to empty, return "unknown".
    """
    if mcp_roots:
        first = Path(mcp_roots[0])
        return slugify(first.name) or "unknown"

    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".git").exists():
            return slugify(candidate.name) or "unknown"

    return slugify(cwd.name) or "unknown"

"""SQLite connection factory with project-standard PRAGMAs and sqlite-vec loaded.

Every database connection in brain-mcp goes through connect(). Tests and
production code share the same pragmas and the same extension setup.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlite_vec

from brain_mcp.errors import SchemaError


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL, pragmas, and sqlite-vec extension loaded."""
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_path,
        isolation_level=None,  # autocommit; explicit transactions via transaction()
        check_same_thread=False,  # MCP server may dispatch from worker threads
    )
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (sqlite3.OperationalError, AttributeError) as e:
        raise SchemaError(
            f"Failed to load sqlite-vec extension: {e}. "
            "Ensure sqlite3 was built with extension support."
        ) from e

    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Explicit transaction context over an autocommit connection."""
    conn.execute("BEGIN")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

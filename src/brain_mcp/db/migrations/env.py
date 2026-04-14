"""Alembic environment wired to brain_mcp.db.connect().

Instead of letting Alembic open a raw SQLAlchemy engine, we open a sqlite3
connection via our factory (so pragmas and sqlite-vec are loaded) and wrap
it in a SQLAlchemy engine via the `creator` pattern.
"""

from __future__ import annotations

import sqlite3

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from brain_mcp.db.connection import connect
from brain_mcp.paths import db_path as resolve_db_path

config = context.config


def _make_engine(conn_holder: dict[str, sqlite3.Connection]) -> Engine:
    db = resolve_db_path()

    def creator() -> sqlite3.Connection:
        # Called by SQLAlchemy's connection pool. Return a fresh configured conn.
        # We cache one for the migration run so that sqlite-vec state persists.
        if "conn" not in conn_holder:
            conn_holder["conn"] = connect(db)
        return conn_holder["conn"]

    return create_engine("sqlite://", creator=creator)


def run_migrations_offline() -> None:
    """Offline mode — rarely used but supported by Alembic."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode — real database connection via brain_mcp.db.connect()."""
    conn_holder: dict[str, sqlite3.Connection] = {}
    engine = _make_engine(conn_holder)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                render_as_batch=True,  # SQLite ALTER limitations
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        cached = conn_holder.get("conn")
        if cached is not None:
            cached.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

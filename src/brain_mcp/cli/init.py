"""`brain init` command — creates DB, runs migrations, downloads model, self-checks."""

from __future__ import annotations

import sqlite3
import struct
import uuid
from datetime import UTC, datetime

import typer

from brain_mcp.db.connection import connect
from brain_mcp.db.migrations import run_upgrade_head
from brain_mcp.db.schema import KnowledgeKind
from brain_mcp.embedding.models import DEFAULT_MODEL, FULL_MODEL, FastEmbedEmbedder
from brain_mcp.embedding.service import EmbeddingService
from brain_mcp.errors import SchemaError
from brain_mcp.paths import (
    brain_home,
    db_path,
    device_id_path,
    model_cache_dir,
)


def init_command(
    full_model: bool = typer.Option(
        False,
        "--full-model",
        help="Use full-precision model (~274MB) instead of quantized (~70MB).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Regenerate device_id even if one already exists (migrations and model load are always idempotent).",
    ),
) -> None:
    """Initialize brain: create database, run migrations, download embedding model."""
    home = brain_home()
    db = db_path()
    cache = model_cache_dir()
    device_file = device_id_path()

    typer.echo(f"Initializing brain at {home}")
    home.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    if device_file.exists() and not force:
        device_id = device_file.read_text().strip()
    else:
        device_id = uuid.uuid4().hex
        device_file.write_text(device_id)
    typer.echo(f"  device_id: {device_id[:8]}...")

    typer.echo(f"  database:  {db}")
    run_upgrade_head()
    typer.echo("    schema applied (alembic head)")

    spec = FULL_MODEL if full_model else DEFAULT_MODEL
    typer.echo(f"  model:     {spec.fastembed_id} ({spec.variant})")
    typer.echo(f"    downloading / loading from {cache} ...")
    embedder = FastEmbedEmbedder(spec, cache_dir=cache)
    _ = embedder.embed_query("brain init warm-up probe")
    typer.echo(f"    model loaded (dimension={spec.dimension})")

    typer.echo("  self-check:")
    conn = connect(db)
    try:
        _self_check(conn, EmbeddingService(embedder), device_id)
        typer.echo("    schema, vec, fts all writable")
    finally:
        conn.close()

    typer.echo("")
    typer.echo("brain is ready.")
    typer.echo(f"  home:      {home}")
    typer.echo(f"  database:  {db}")
    typer.echo(f"  model:     {spec.fastembed_id}")


def _self_check(conn: sqlite3.Connection, embedding_service: EmbeddingService, device_id: str) -> None:
    """Insert a probe row end-to-end, then roll back so the DB stays empty."""
    probe_id = uuid.uuid4().hex
    now = datetime.now(tz=UTC).isoformat()
    text = "brain init self-check probe"

    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO knowledge_items "
            "(id, kind, title, content, scope_type, scope_value, "
            "created_at, updated_at, sync_id, device_id) "
            "VALUES (?, 'rule', 'probe', ?, 'global', NULL, ?, ?, ?, ?)",
            (probe_id, text, now, now, uuid.uuid4().hex, device_id),
        )
        conn.execute(
            "INSERT INTO rules (item_id, priority) VALUES (?, 50)", (probe_id,)
        )

        row = conn.execute(
            "SELECT rowid FROM knowledge_items WHERE id = ?", (probe_id,)
        ).fetchone()
        internal_rowid = row[0]

        fts_row = conn.execute(
            "SELECT title FROM knowledge_fts WHERE rowid = ?", (internal_rowid,)
        ).fetchone()
        if fts_row is None:
            raise SchemaError("FTS trigger did not populate knowledge_fts")

        vector, model_id = embedding_service.embed_document(text, kind=KnowledgeKind.RULE)
        blob = struct.pack(f"{len(vector)}f", *vector)
        cursor = conn.execute(
            "INSERT INTO knowledge_vec (embedding) VALUES (?)", (blob,)
        )
        vec_rowid = cursor.lastrowid
        conn.execute(
            "INSERT INTO vec_rowid_map "
            "(vec_rowid, item_id, chunk_index, embedding_model_id, created_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (vec_rowid, probe_id, model_id, now),
        )
    finally:
        conn.execute("ROLLBACK")

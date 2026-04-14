"""initial schema: knowledge_items, extension tables, knowledge_vec, FTS5.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-14
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- parent table ---
    op.execute(
        """
        CREATE TABLE knowledge_items (
            id          TEXT PRIMARY KEY,
            kind        TEXT NOT NULL CHECK (kind IN ('rule','snippet','decision','bug_lesson')),
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            scope_type  TEXT NOT NULL CHECK (scope_type IN ('global','project','language')),
            scope_value TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            sync_id     TEXT NOT NULL,
            device_id   TEXT NOT NULL,
            synced_at   TEXT
        )
        """
    )
    op.execute("CREATE INDEX idx_knowledge_kind ON knowledge_items(kind)")
    op.execute("CREATE INDEX idx_knowledge_scope ON knowledge_items(scope_type, scope_value)")
    op.execute("CREATE INDEX idx_knowledge_updated_at ON knowledge_items(updated_at)")

    # --- extension tables ---
    op.execute(
        """
        CREATE TABLE rules (
            item_id  TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            priority INTEGER NOT NULL DEFAULT 50
        )
        """
    )
    op.execute(
        """
        CREATE TABLE snippets (
            item_id       TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            language      TEXT NOT NULL,
            usage_context TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE decisions (
            item_id      TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            rationale    TEXT NOT NULL,
            alternatives TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE bug_lessons (
            item_id    TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
            symptom    TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            fix        TEXT NOT NULL,
            prevention TEXT
        )
        """
    )

    # --- tags ---
    op.execute(
        """
        CREATE TABLE knowledge_tags (
            item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            tag     TEXT NOT NULL,
            PRIMARY KEY (item_id, tag)
        )
        """
    )
    op.execute("CREATE INDEX idx_tags_tag ON knowledge_tags(tag)")

    # --- sqlite-vec virtual table ---
    op.execute(
        """
        CREATE VIRTUAL TABLE knowledge_vec USING vec0(
            embedding float[768]
        )
        """
    )

    # --- vec bridge ---
    op.execute(
        """
        CREATE TABLE vec_rowid_map (
            vec_rowid          INTEGER PRIMARY KEY,
            item_id            TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            chunk_index        INTEGER NOT NULL DEFAULT 0,
            embedding_model_id TEXT NOT NULL,
            created_at         TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX idx_vec_map_item ON vec_rowid_map(item_id)")
    op.execute("CREATE INDEX idx_vec_map_model ON vec_rowid_map(embedding_model_id)")

    # --- FTS5 contentless ---
    op.execute(
        """
        CREATE VIRTUAL TABLE knowledge_fts USING fts5(
            title,
            content,
            content='knowledge_items',
            content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )

    # --- FTS sync triggers ---
    op.execute(
        """
        CREATE TRIGGER knowledge_items_ai AFTER INSERT ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER knowledge_items_ad AFTER DELETE ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content)
            VALUES('delete', old.rowid, old.title, old.content);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER knowledge_items_au AFTER UPDATE ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content)
            VALUES('delete', old.rowid, old.title, old.content);
            INSERT INTO knowledge_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END
        """
    )


def downgrade() -> None:
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS knowledge_items_au")
    op.execute("DROP TRIGGER IF EXISTS knowledge_items_ad")
    op.execute("DROP TRIGGER IF EXISTS knowledge_items_ai")
    # Drop virtual tables
    op.execute("DROP TABLE IF EXISTS knowledge_fts")
    op.execute("DROP TABLE IF EXISTS vec_rowid_map")
    op.execute("DROP TABLE IF EXISTS knowledge_vec")
    # Drop concrete tables
    op.execute("DROP TABLE IF EXISTS knowledge_tags")
    op.execute("DROP TABLE IF EXISTS bug_lessons")
    op.execute("DROP TABLE IF EXISTS decisions")
    op.execute("DROP TABLE IF EXISTS snippets")
    op.execute("DROP TABLE IF EXISTS rules")
    op.execute("DROP TABLE IF EXISTS knowledge_items")

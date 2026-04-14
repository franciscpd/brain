"""phase 2: rules.topic, knowledge_items.content_hash, decisions.context.

Revision ID: 0002_phase2
Revises: 0001_initial
Create Date: 2026-04-14
"""

from __future__ import annotations

from alembic import op

revision = "0002_phase2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE rules ADD COLUMN topic TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rules_topic "
        "ON rules(topic) WHERE topic IS NOT NULL"
    )
    op.execute("ALTER TABLE knowledge_items ADD COLUMN content_hash TEXT")
    op.execute("ALTER TABLE decisions ADD COLUMN context TEXT")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_rules_topic")
    # SQLite DROP COLUMN requires batch mode in Alembic.
    with op.batch_alter_table("decisions") as batch:
        batch.drop_column("context")
    with op.batch_alter_table("knowledge_items") as batch:
        batch.drop_column("content_hash")
    with op.batch_alter_table("rules") as batch:
        batch.drop_column("topic")

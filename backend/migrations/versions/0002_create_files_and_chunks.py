"""Create files and chunks tables.

Revision ID: 0002_create_files_and_chunks
Revises: 0001_sprint_2_core
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "0002_create_files_and_chunks"
down_revision: str | None = "0001_sprint_2_core"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def uuid_type() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    generated_uuid = sa.text("gen_random_uuid()")
    utc_now = sa.text("CURRENT_TIMESTAMP")

    # Create files table
    op.create_table(
        "files",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("channel_id", uuid_type(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("uploaded_by", uuid_type(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ingestion_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utc_now),
    )
    op.create_index("ix_files_channel_id", "files", ["channel_id"])

    # Create chunks table
    op.create_table(
        "chunks",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("file_id", uuid_type(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", uuid_type(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
    )
    op.create_index("ix_chunks_file_id", "chunks", ["file_id"])
    op.create_index("ix_chunks_channel_id", "chunks", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_channel_id", table_name="chunks")
    op.drop_index("ix_chunks_file_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_files_channel_id", table_name="files")
    op.drop_table("files")

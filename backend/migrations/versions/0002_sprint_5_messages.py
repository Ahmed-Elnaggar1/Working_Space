"""Create Sprint 5 messages table.

Revision ID: 0002_sprint_5_messages
Revises: 0001_sprint_2_core
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_sprint_5_messages"
down_revision: str | None = "0001_sprint_2_core"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def uuid_type() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    generated_uuid = sa.text("gen_random_uuid()")
    utc_now = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "messages",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("channel_id", uuid_type(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", uuid_type(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utc_now),
    )
    op.create_index("ix_messages_channel_created_at", "messages", ["channel_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_channel_created_at", table_name="messages")
    op.drop_table("messages")

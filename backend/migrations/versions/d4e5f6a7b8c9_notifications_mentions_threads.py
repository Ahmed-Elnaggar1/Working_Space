"""notifications_mentions_threads

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-06 20:58:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. messages.parent_message_id
    op.add_column(
        "messages",
        sa.Column("parent_message_id", app.models.GUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_parent_message_id",
        "messages",
        "messages",
        ["parent_message_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_messages_parent_message_id",
        "messages",
        ["parent_message_id"],
        unique=False,
    )

    # 2. mentions table
    op.create_table(
        "mentions",
        sa.Column("id", app.models.GUID(), nullable=False),
        sa.Column("message_id", app.models.GUID(), nullable=False),
        sa.Column("mentioned_user_id", app.models.GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["mentioned_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "mentioned_user_id", name="uq_mentions_message_user"
        ),
    )
    op.create_index(
        "ix_mentions_mentioned_user_id",
        "mentions",
        ["mentioned_user_id"],
        unique=False,
    )

    # 3. notifications table
    op.create_table(
        "notifications",
        sa.Column("id", app.models.GUID(), nullable=False),
        sa.Column("user_id", app.models.GUID(), nullable=False),
        sa.Column("actor_id", app.models.GUID(), nullable=False),
        sa.Column("channel_id", app.models.GUID(), nullable=False),
        sa.Column("message_id", app.models.GUID(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column(
            "is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["channels.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "type IN ('mention', 'thread_reply')",
            name="ck_notifications_type_valid",
        ),
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_user_created_at",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_mentions_mentioned_user_id", table_name="mentions")
    op.drop_table("mentions")

    op.drop_index("ix_messages_parent_message_id", table_name="messages")
    op.drop_constraint(
        "fk_messages_parent_message_id", "messages", type_="foreignkey"
    )
    op.drop_column("messages", "parent_message_id")

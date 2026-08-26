"""Create Sprint 2 core tables.

Revision ID: 0001_sprint_2_core
Revises:
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_sprint_2_core"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def uuid_type() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    generated_uuid = sa.text("gen_random_uuid()")
    utc_now = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "users",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utc_now),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", uuid_type(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utc_now),
    )

    op.create_table(
        "channels",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("workspace_id", uuid_type(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utc_now),
        sa.UniqueConstraint("workspace_id", "name", name="uq_channels_workspace_name"),
    )
    op.create_index("ix_channels_workspace_id", "channels", ["workspace_id"])

    op.create_table(
        "memberships",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("user_id", uuid_type(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel_id", uuid_type(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member', 'read_only')", name="ck_memberships_role"),
        sa.UniqueConstraint("user_id", "channel_id", name="uq_memberships_user_channel"),
    )
    op.create_index("ix_memberships_user_channel", "memberships", ["user_id", "channel_id"])
    op.create_index("ix_memberships_channel_role", "memberships", ["channel_id", "role"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", uuid_type(), primary_key=True, server_default=generated_uuid),
        sa.Column("user_id", uuid_type(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_index("ix_memberships_channel_role", table_name="memberships")
    op.drop_index("ix_memberships_user_channel", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_channels_workspace_id", table_name="channels")
    op.drop_table("channels")
    op.drop_table("workspaces")
    op.drop_table("users")

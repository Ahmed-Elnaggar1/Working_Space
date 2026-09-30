"""add file validation fields

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("ingestion_retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("files", "ingestion_retry_count", server_default=None)


def downgrade() -> None:
    op.drop_column("files", "ingestion_retry_count")
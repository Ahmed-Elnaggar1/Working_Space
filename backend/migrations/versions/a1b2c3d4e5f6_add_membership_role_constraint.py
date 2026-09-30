"""add membership role constraint

Revision ID: a1b2c3d4e5f6
Revises: 15642d764bc9
Create Date: 2026-09-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "15642d764bc9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_memberships_role_valid",
        "memberships",
        "role IN ('owner', 'admin', 'member', 'read_only')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_memberships_role_valid", "memberships", type_="check")

"""Add admin_secret_usage table for multi-worker admin secret tracking

Revision ID: 003
Revises: 002
Create Date: 2026-02-08 14:24:00.000000

Replaces process-level flag with database-backed tracking for admin secret consumption.
This ensures one-time use enforcement works correctly in multi-worker deployments.
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create admin_secret_usage table for multi-worker safe tracking."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_secret_usage (
            id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            consumed BOOLEAN NOT NULL DEFAULT false,
            consumed_at TIMESTAMPTZ
        )
    """
    )


def downgrade() -> None:
    """Drop admin_secret_usage table."""
    op.execute("DROP TABLE IF EXISTS admin_secret_usage")

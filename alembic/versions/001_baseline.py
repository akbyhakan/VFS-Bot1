"""Baseline migration - existing schema

Revision ID: 001
Revises: 
Create Date: 2026-02-08 14:22:00.000000

This migration marks the current database schema as the baseline.
All existing tables are already created by the application's _create_tables() method.
This migration does nothing but serves as a starting point for future migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Mark current schema as baseline - no changes needed."""
    pass


def downgrade() -> None:
    """Cannot downgrade from baseline."""
    pass

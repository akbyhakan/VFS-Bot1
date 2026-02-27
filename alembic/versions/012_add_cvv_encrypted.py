"""Add cvv_encrypted column to payment_card table

Revision ID: 012
Revises: 011
Create Date: 2026-02-27 20:00:00.000000

Re-adds the cvv_encrypted column removed in migration 002.
CVV is now stored encrypted for personal use — automated payment support.
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cvv_encrypted column to payment_card table."""
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'cvv_encrypted'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN cvv_encrypted TEXT DEFAULT NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove cvv_encrypted column from payment_card table."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'cvv_encrypted'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN cvv_encrypted;
            END IF;
        END $$;
    """)

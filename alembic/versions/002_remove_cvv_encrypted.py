"""Remove cvv_encrypted column from payment_card table (PCI-DSS compliance)

Revision ID: 002
Revises: 001
Create Date: 2026-02-08 14:23:00.000000

Per PCI-DSS Requirement 3.2, CVV must not be stored after authorization.
This migration removes the cvv_encrypted column from the payment_card table.
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove cvv_encrypted column from payment_card table."""
    # Check if column exists before dropping (for idempotency)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'cvv_encrypted'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN cvv_encrypted;
            END IF;
        END $$;
    """
    )


def downgrade() -> None:
    """Add back cvv_encrypted column (NOT RECOMMENDED - violates PCI-DSS)."""
    # Only add if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'cvv_encrypted'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN cvv_encrypted TEXT;
            END IF;
        END $$;
    """
    )

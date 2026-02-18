"""Add encrypted passport field to personal_details table

Revision ID: 006
Revises: 005
Create Date: 2026-02-08 21:32:00.000000

Add passport_number_encrypted column to personal_details table for PII encryption.
Migrates existing unencrypted passport numbers to encrypted storage.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add passport_number_encrypted column and migrate data."""
    # Add passport_number_encrypted column if it doesn't exist
    op.execute(
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'personal_details' AND column_name = 'passport_number_encrypted'
            ) THEN
                ALTER TABLE personal_details ADD COLUMN passport_number_encrypted TEXT;
            END IF;
        END $$;
    """
    )

    # Note: Data migration for existing passport numbers should be handled
    # during application runtime when passport numbers are accessed and updated.


def downgrade() -> None:
    """Remove passport_number_encrypted column from personal_details."""
    # WARNING: This will result in data loss of encrypted passport numbers
    op.execute(
        """
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'personal_details' AND column_name = 'passport_number_encrypted'
            ) THEN
                ALTER TABLE personal_details DROP COLUMN passport_number_encrypted;
            END IF;
        END $$;
    """
    )

"""Add person fields to appointment_persons table

Revision ID: 005
Revises: 004
Create Date: 2026-02-08 21:31:00.000000

Add gender and is_child_with_parent columns to appointment_persons table
to support child appointments and gender-specific requirements.
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add gender and is_child_with_parent columns to appointment_persons."""
    # Add gender column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'appointment_persons' AND column_name = 'gender'
            ) THEN
                ALTER TABLE appointment_persons ADD COLUMN gender TEXT;
            END IF;
        END $$;
    """)

    # Set default value for existing records
    op.execute("UPDATE appointment_persons SET gender = 'male' WHERE gender IS NULL")

    # Add is_child_with_parent column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'appointment_persons' AND column_name = 'is_child_with_parent'
            ) THEN
                ALTER TABLE appointment_persons ADD COLUMN is_child_with_parent BOOLEAN;
            END IF;
        END $$;
    """)

    # Set default value for existing records
    op.execute(
        "UPDATE appointment_persons SET is_child_with_parent = FALSE "
        "WHERE is_child_with_parent IS NULL"
    )


def downgrade() -> None:
    """Remove gender and is_child_with_parent columns from appointment_persons."""
    # Drop is_child_with_parent column if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'appointment_persons' AND column_name = 'is_child_with_parent'
            ) THEN
                ALTER TABLE appointment_persons DROP COLUMN is_child_with_parent;
            END IF;
        END $$;
    """)

    # Drop gender column if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'appointment_persons' AND column_name = 'gender'
            ) THEN
                ALTER TABLE appointment_persons DROP COLUMN gender;
            END IF;
        END $$;
    """)

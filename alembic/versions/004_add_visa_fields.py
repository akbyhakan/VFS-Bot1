"""Add visa fields to appointment_requests table

Revision ID: 004
Revises: 003
Create Date: 2026-02-08 21:30:00.000000

Add visa_category and visa_subcategory columns to appointment_requests table
to support multi-country visa appointment tracking.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add visa_category and visa_subcategory columns to appointment_requests."""
    # Add visa_category column if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'appointment_requests' AND column_name = 'visa_category'
            ) THEN
                ALTER TABLE appointment_requests ADD COLUMN visa_category TEXT;
            END IF;
        END $$;
    """)
    
    # Set default value for existing records
    op.execute("UPDATE appointment_requests SET visa_category = '' WHERE visa_category IS NULL")
    
    # Add visa_subcategory column if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'appointment_requests' AND column_name = 'visa_subcategory'
            ) THEN
                ALTER TABLE appointment_requests ADD COLUMN visa_subcategory TEXT;
            END IF;
        END $$;
    """)
    
    # Set default value for existing records
    op.execute("UPDATE appointment_requests SET visa_subcategory = '' WHERE visa_subcategory IS NULL")


def downgrade() -> None:
    """Remove visa_category and visa_subcategory columns from appointment_requests."""
    # Drop visa_subcategory column if it exists
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'appointment_requests' AND column_name = 'visa_subcategory'
            ) THEN
                ALTER TABLE appointment_requests DROP COLUMN visa_subcategory;
            END IF;
        END $$;
    """)
    
    # Drop visa_category column if it exists
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'appointment_requests' AND column_name = 'visa_category'
            ) THEN
                ALTER TABLE appointment_requests DROP COLUMN visa_category;
            END IF;
        END $$;
    """)

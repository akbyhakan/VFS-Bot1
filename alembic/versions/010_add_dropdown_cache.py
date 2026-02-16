"""Add vfs_dropdown_cache table for storing VFS dropdown data

Revision ID: 010
Revises: 009
Create Date: 2026-02-16 10:53:00.000000

Add table to cache VFS dropdown data (centres, categories, subcategories)
fetched from VFS website to improve performance and reduce VFS site load.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create vfs_dropdown_cache table."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS vfs_dropdown_cache (
            id SERIAL PRIMARY KEY,
            country_code VARCHAR(3) NOT NULL,
            dropdown_data JSONB NOT NULL,
            last_synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE(country_code)
        );
        
        -- Create index on country_code for faster lookups
        CREATE INDEX IF NOT EXISTS idx_vfs_dropdown_cache_country 
            ON vfs_dropdown_cache(country_code);
        
        -- Create index on last_synced_at for finding stale data
        CREATE INDEX IF NOT EXISTS idx_vfs_dropdown_cache_synced 
            ON vfs_dropdown_cache(last_synced_at);
    """)


def downgrade() -> None:
    """Drop vfs_dropdown_cache table."""
    op.execute("""
        DROP TABLE IF EXISTS vfs_dropdown_cache CASCADE;
    """)

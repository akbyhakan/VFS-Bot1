"""Add account pool tables

Revision ID: 008
Revises: 007
Create Date: 2026-02-15 14:54:00.000000

This migration creates the VFS account pool and usage logging tables
to support the shared account pool architecture with LRU + cooldown strategy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create account pool tables."""
    
    # Create vfs_account_pool table
    op.execute("""
        CREATE TABLE IF NOT EXISTS vfs_account_pool (
            id BIGSERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'available' NOT NULL,
            last_used_at TIMESTAMPTZ,
            cooldown_until TIMESTAMPTZ,
            quarantine_until TIMESTAMPTZ,
            consecutive_failures INTEGER DEFAULT 0 NOT NULL,
            total_uses INTEGER DEFAULT 0 NOT NULL,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            CONSTRAINT check_status CHECK (status IN ('available', 'in_use', 'cooldown', 'quarantine'))
        )
    """)
    
    # Create account_usage_log table
    op.execute("""
        CREATE TABLE IF NOT EXISTS account_usage_log (
            id BIGSERIAL PRIMARY KEY,
            account_id BIGINT NOT NULL REFERENCES vfs_account_pool(id) ON DELETE CASCADE,
            mission_code TEXT NOT NULL,
            session_number INTEGER NOT NULL,
            request_id BIGINT REFERENCES appointment_requests(id) ON DELETE SET NULL,
            result TEXT NOT NULL,
            error_message TEXT,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            CONSTRAINT check_result CHECK (result IN ('success', 'no_slot', 'login_fail', 'error', 'banned'))
        )
    """)
    
    # Create indexes for performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_vfs_account_pool_status 
        ON vfs_account_pool(status) 
        WHERE is_active = TRUE
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_vfs_account_pool_cooldown 
        ON vfs_account_pool(cooldown_until) 
        WHERE is_active = TRUE AND status = 'cooldown'
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_vfs_account_pool_quarantine 
        ON vfs_account_pool(quarantine_until) 
        WHERE is_active = TRUE AND status = 'quarantine'
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_vfs_account_pool_last_used 
        ON vfs_account_pool(last_used_at) 
        WHERE is_active = TRUE
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_account_usage_log_account_id 
        ON account_usage_log(account_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_account_usage_log_session 
        ON account_usage_log(session_number, started_at)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_account_usage_log_result 
        ON account_usage_log(result, created_at)
    """)
    
    # Add trigger to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_vfs_account_pool_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_update_vfs_account_pool_updated_at
        BEFORE UPDATE ON vfs_account_pool
        FOR EACH ROW
        EXECUTE FUNCTION update_vfs_account_pool_updated_at()
    """)


def downgrade() -> None:
    """Drop account pool tables."""
    
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trigger_update_vfs_account_pool_updated_at ON vfs_account_pool")
    op.execute("DROP FUNCTION IF EXISTS update_vfs_account_pool_updated_at()")
    
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_account_usage_log_result")
    op.execute("DROP INDEX IF EXISTS idx_account_usage_log_session")
    op.execute("DROP INDEX IF EXISTS idx_account_usage_log_account_id")
    op.execute("DROP INDEX IF EXISTS idx_vfs_account_pool_last_used")
    op.execute("DROP INDEX IF EXISTS idx_vfs_account_pool_quarantine")
    op.execute("DROP INDEX IF EXISTS idx_vfs_account_pool_cooldown")
    op.execute("DROP INDEX IF EXISTS idx_vfs_account_pool_status")
    
    # Drop tables
    op.execute("DROP TABLE IF EXISTS account_usage_log")
    op.execute("DROP TABLE IF EXISTS vfs_account_pool")

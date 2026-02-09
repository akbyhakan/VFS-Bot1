"""Baseline migration - existing schema

Revision ID: 001
Revises: 
Create Date: 2026-02-08 14:22:00.000000

This migration creates the complete initial database schema.
All tables, indexes, triggers, and functions are defined here.
This replaces the _create_tables() method from database.py.
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
    """Create complete database schema with all tables, indexes, and triggers."""
    
    # Create users table
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            centre TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    # Create personal_details table
    op.execute("""
        CREATE TABLE IF NOT EXISTS personal_details (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            passport_number TEXT NOT NULL,
            passport_expiry TEXT,
            gender TEXT,
            mobile_code TEXT,
            mobile_number TEXT,
            email TEXT NOT NULL,
            nationality TEXT,
            date_of_birth TEXT,
            address_line1 TEXT,
            address_line2 TEXT,
            state TEXT,
            city TEXT,
            postcode TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Create appointments table
    op.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            centre TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            appointment_date TEXT,
            appointment_time TEXT,
            status TEXT DEFAULT 'pending',
            reference_number TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Create logs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id BIGSERIAL PRIMARY KEY,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            user_id BIGINT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    """)
    
    # Create payment_card table
    op.execute("""
        CREATE TABLE IF NOT EXISTS payment_card (
            id BIGSERIAL PRIMARY KEY,
            card_holder_name TEXT NOT NULL,
            card_number_encrypted TEXT NOT NULL,
            expiry_month TEXT NOT NULL,
            expiry_year TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    # Create admin_secret_usage table
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_secret_usage (
            id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            consumed BOOLEAN NOT NULL DEFAULT false,
            consumed_at TIMESTAMPTZ
        )
    """)
    
    # Create appointment_requests table
    op.execute("""
        CREATE TABLE IF NOT EXISTS appointment_requests (
            id BIGSERIAL PRIMARY KEY,
            country_code TEXT NOT NULL,
            visa_category TEXT NOT NULL,
            visa_subcategory TEXT NOT NULL,
            centres TEXT NOT NULL,
            preferred_dates TEXT NOT NULL,
            person_count INTEGER NOT NULL CHECK(person_count >= 1 AND person_count <= 6),
            status TEXT DEFAULT 'pending',
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    # Create appointment_persons table
    op.execute("""
        CREATE TABLE IF NOT EXISTS appointment_persons (
            id BIGSERIAL PRIMARY KEY,
            request_id BIGINT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            gender TEXT NOT NULL,
            nationality TEXT NOT NULL DEFAULT 'Turkey',
            birth_date TEXT NOT NULL,
            passport_number TEXT NOT NULL,
            passport_issue_date TEXT NOT NULL,
            passport_expiry_date TEXT NOT NULL,
            phone_code TEXT NOT NULL DEFAULT '90',
            phone_number TEXT NOT NULL,
            email TEXT NOT NULL,
            is_child_with_parent BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (request_id) REFERENCES appointment_requests (id) ON DELETE CASCADE
        )
    """)
    
    # Create audit_log table
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            action TEXT NOT NULL,
            user_id BIGINT,
            username TEXT,
            ip_address TEXT,
            user_agent TEXT,
            details TEXT,
            timestamp TEXT NOT NULL,
            success BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    """)
    
    # Create appointment_history table
    op.execute("""
        CREATE TABLE IF NOT EXISTS appointment_history (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            centre TEXT NOT NULL,
            mission TEXT NOT NULL,
            category TEXT,
            slot_date TEXT,
            slot_time TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER DEFAULT 1,
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # Create user_webhooks table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_webhooks (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL UNIQUE,
            webhook_token VARCHAR(64) UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # Create proxy_endpoints table
    op.execute("""
        CREATE TABLE IF NOT EXISTS proxy_endpoints (
            id BIGSERIAL PRIMARY KEY,
            server TEXT NOT NULL,
            port INTEGER NOT NULL,
            username TEXT NOT NULL,
            password_encrypted TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            last_used TIMESTAMPTZ,
            failure_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(server, port, username)
        )
    """)
    
    # Create token_blacklist table
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_blacklist (
            jti VARCHAR(64) PRIMARY KEY,
            exp TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    # Create schema_migrations table
    op.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointment_history_user_status ON appointment_history(user_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_webhooks_token ON user_webhooks(webhook_token)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_proxy_endpoints_active ON proxy_endpoints(is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_token_blacklist_exp ON token_blacklist(exp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_personal_details_user_id ON personal_details(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)")
    
    # Create trigger function for auto-updating updated_at column
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Create triggers for tables with updated_at column
    # Using explicit SQL statements for safety (no string interpolation)
    op.execute("""
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        DROP TRIGGER IF EXISTS update_personal_details_updated_at ON personal_details;
        CREATE TRIGGER update_personal_details_updated_at
            BEFORE UPDATE ON personal_details
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        DROP TRIGGER IF EXISTS update_payment_card_updated_at ON payment_card;
        CREATE TRIGGER update_payment_card_updated_at
            BEFORE UPDATE ON payment_card
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        DROP TRIGGER IF EXISTS update_appointment_requests_updated_at ON appointment_requests;
        CREATE TRIGGER update_appointment_requests_updated_at
            BEFORE UPDATE ON appointment_requests
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        DROP TRIGGER IF EXISTS update_appointment_history_updated_at ON appointment_history;
        CREATE TRIGGER update_appointment_history_updated_at
            BEFORE UPDATE ON appointment_history
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        DROP TRIGGER IF EXISTS update_proxy_endpoints_updated_at ON proxy_endpoints;
        CREATE TRIGGER update_proxy_endpoints_updated_at
            BEFORE UPDATE ON proxy_endpoints
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop all tables in reverse order (respecting foreign key dependencies)."""
    # Drop tables in reverse order to respect FK dependencies
    op.execute("DROP TABLE IF EXISTS schema_migrations CASCADE")
    op.execute("DROP TABLE IF EXISTS token_blacklist CASCADE")
    op.execute("DROP TABLE IF EXISTS proxy_endpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS user_webhooks CASCADE")
    op.execute("DROP TABLE IF EXISTS appointment_history CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS appointment_persons CASCADE")
    op.execute("DROP TABLE IF EXISTS appointment_requests CASCADE")
    op.execute("DROP TABLE IF EXISTS admin_secret_usage CASCADE")
    op.execute("DROP TABLE IF EXISTS payment_card CASCADE")
    op.execute("DROP TABLE IF EXISTS logs CASCADE")
    op.execute("DROP TABLE IF EXISTS appointments CASCADE")
    op.execute("DROP TABLE IF EXISTS personal_details CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    
    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")

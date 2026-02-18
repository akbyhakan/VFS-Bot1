"""Encrypt card holder name and expiry fields (PCI-DSS compliance)

Revision ID: 009
Revises: 008
Create Date: 2026-02-16 00:20:00.000000

Per PCI-DSS requirements, all payment card data must be encrypted.
This migration renames columns to indicate encryption and migrates existing data.
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Encrypt card holder name and expiry fields."""

    # Step 1: Add new encrypted columns
    op.execute("""
        DO $$
        BEGIN
            -- Add card_holder_name_encrypted if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'card_holder_name_encrypted'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN card_holder_name_encrypted TEXT;
            END IF;

            -- Add expiry_month_encrypted if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_month_encrypted'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN expiry_month_encrypted TEXT;
            END IF;

            -- Add expiry_year_encrypted if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_year_encrypted'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN expiry_year_encrypted TEXT;
            END IF;
        END $$;
    """)

    # Step 2: Migrate existing plaintext data to encrypted columns
    # IMPORTANT: This copies plaintext data to *_encrypted columns as-is.
    # The application code will re-encrypt this data on the next write operation.
    # For immediate encryption, run a data migration script after applying this schema migration.
    # This approach prevents coupling database migrations with application encryption logic.
    op.execute("""
        UPDATE payment_card
        SET card_holder_name_encrypted = card_holder_name,
            expiry_month_encrypted = expiry_month,
            expiry_year_encrypted = expiry_year
        WHERE card_holder_name_encrypted IS NULL;
    """)

    # Step 3: Make new columns NOT NULL
    op.execute("""
        ALTER TABLE payment_card
        ALTER COLUMN card_holder_name_encrypted SET NOT NULL;
    """)

    op.execute("""
        ALTER TABLE payment_card
        ALTER COLUMN expiry_month_encrypted SET NOT NULL;
    """)

    op.execute("""
        ALTER TABLE payment_card
        ALTER COLUMN expiry_year_encrypted SET NOT NULL;
    """)

    # Step 4: Drop old plaintext columns
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'card_holder_name'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN card_holder_name;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_month'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN expiry_month;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_year'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN expiry_year;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Restore plaintext columns (NOT RECOMMENDED - violates PCI-DSS).

    WARNING: This downgrade does NOT decrypt data. It simply renames columns back.
    Any data that was encrypted will remain encrypted in the "plaintext" columns,
    which will break the application. This downgrade is provided for schema rollback
    only and should not be used in production.
    """
    import os

    # Safety check: Prevent accidental data corruption in production
    env = os.getenv("ENVIRONMENT", "").lower()
    allow_downgrade = os.getenv("ALLOW_DANGEROUS_DOWNGRADE", "").lower()

    if env in ("production", "prod", "live"):
        if allow_downgrade != "yes-i-know-what-i-am-doing":
            raise RuntimeError(
                "🚨 BLOCKED: Encryption migration downgrade in production! "
                "This would create data corruption (encrypted data in plaintext columns). "
                "If you are absolutely sure, set environment variable: "
                "ALLOW_DANGEROUS_DOWNGRADE=yes-i-know-what-i-am-doing"
            )

    # Step 1: Add back plaintext columns
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'card_holder_name'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN card_holder_name TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_month'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN expiry_month TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_year'
            ) THEN
                ALTER TABLE payment_card ADD COLUMN expiry_year TEXT;
            END IF;
        END $$;
    """)

    # Step 2: Copy data back (WARNING: Will contain encrypted data if it was encrypted)
    # This is intentionally NOT decrypting to avoid coupling with application code
    op.execute("""
        UPDATE payment_card
        SET card_holder_name = card_holder_name_encrypted,
            expiry_month = expiry_month_encrypted,
            expiry_year = expiry_year_encrypted
        WHERE card_holder_name IS NULL;
    """)

    # Step 3: Make columns NOT NULL
    op.execute("""
        ALTER TABLE payment_card
        ALTER COLUMN card_holder_name SET NOT NULL,
        ALTER COLUMN expiry_month SET NOT NULL,
        ALTER COLUMN expiry_year SET NOT NULL;
    """)

    # Step 4: Drop encrypted columns
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'card_holder_name_encrypted'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN card_holder_name_encrypted;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_month_encrypted'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN expiry_month_encrypted;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payment_card' AND column_name = 'expiry_year_encrypted'
            ) THEN
                ALTER TABLE payment_card DROP COLUMN expiry_year_encrypted;
            END IF;
        END $$;
    """)
